import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import threading
import time
from collections import deque
import os
import pvporcupine
import pyaudio
import struct
from dotenv import load_dotenv
load_dotenv()


# TODO input audio into the file from the outside (so it is able to run in docker)
# Wake word gate using Porcupine
# TODO fix Upon not speaking to at start keep listening for X seconds till abort, dont go into long pause and end (bot gets stuck in that mode) 
class WakeWordActivation:
    """
    Listens for the Porcupine wake word in a background thread and sets a flag when detected.
    """
    def __init__(self):
        self.detected = threading.Event()
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()

    def _listen(self):
        ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")
        MODEL_FILE_NAME = os.getenv("POCCUPINE_MODEL_FILE_NAME", "")

        # NOTE current wake word is: "Hey Atlas"
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "porcupine-model", MODEL_FILE_NAME)
        porcupine = pvporcupine.create(
            access_key=ACCESS_KEY,
            keyword_paths=[model_path],
            sensitivities=[0.6]
        )
        pa = pyaudio.PyAudio()
        stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length
        )
        print("Listening for wake word...")
        try:
            while not self._stop.is_set():
                pcm = stream.read(
                    porcupine.frame_length,
                    exception_on_overflow=False
                )
                pcm = struct.unpack_from(
                    "h" * porcupine.frame_length,
                    pcm
                )
                keyword_index = porcupine.process(pcm)
                if keyword_index >= 0:
                    print("Wake word detected! Listening...")
                    self.detected.set()
                    self.detected.wait()
                    self.detected.clear()
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
            porcupine.delete()

    def wait_for_wake(self):
        self.detected.wait()
        
    def reset(self):
        self.detected.set()

    def stop(self):
        self._stop.set()
        self.thread.join()

class StreamingSTT:
    def __init__(self, model):
        """
        Streaming speech-to-text (STT) with real-time partial and final message output.
        Loads a Whisper model and sets up audio streaming parameters.
        """
        if model is not None:
            self.model = model
            
        # Audio stream parameters
        self.SAMPLERATE = 16000
        self.CHUNK_DURATION = 0.5  # seconds per audio chunk
        self.CHUNK_SIZE = int(self.SAMPLERATE * self.CHUNK_DURATION)

        # Buffer for incoming audio chunks (for partial transcription)
        self.current_buffer = deque()
        # Lock to ensure thread-safe access to the buffer
        self.buffer_lock = threading.Lock()
        # List of partial transcriptions (strings)
        self.partials = []
        # Index to track which part of the buffer has already been processed for partials
        self.last_partial_index = 0

        # Silence and timing thresholds
        # TODO: Adapt to environment and mic sensitivity (How?) 
        # Capture and pre-process audio in Rust and send it to container/this file?
        self.silence_threshold = 0.004
        self.min_audio_length = (
            0.5  # Minimum audio length (seconds) for valid transcription
        )
        self.short_silence_duration = 0.5  # Short pause (seconds) triggers partial message transcription
        self.long_silence_duration = 1.25  # Long pause (seconds) triggers final message

        # State variables for speech detection and timing
        self.is_recording = False
        self.last_speech_time = time.time()  # Last time speech was detected
        self.last_chunk_time = time.time()  # Last time a chunk was processed

        # List of threads currently processing partials
        self.partial_threads = []
        # Lock to protect access to partial_threads
        self.partial_threads_lock = threading.Lock()

        # Queue for full messages (max 10 to prevent unbounded growth, meaning last 10 prompts)
        self.full_message_queue = deque(maxlen=20)

    def detect_voice_activity(self, audio_chunk):
        """
        Detects if the audio chunk contains speech based on RMS and peak amplitude.
        Returns True if speech is detected, otherwise False.
        """
        # Calculate root mean square (RMS) and peak amplitude
        rms = np.sqrt(np.mean(audio_chunk**2))
        peak = np.max(np.abs(audio_chunk))
        # Return True if either RMS or peak exceeds threshold (robust to both loud and soft speech)
        return rms > self.silence_threshold or peak > self.silence_threshold * 2

    def transcribe_buffer(self, audio_data):
        """
        Transcribes the given audio data using the Whisper model.
        Returns the transcribed text or an empty string on error/short input.
        """
        # Ignore very short audio (likely noise or silence)
        if len(audio_data) < self.SAMPLERATE * self.min_audio_length:
            return ""
        try:
            # Transcribe using Whisper. VAD is off; handle silence in code here for now.
            segments, _ = self.model.transcribe(
                audio_data,
                beam_size=1,
                best_of=3,
                temperature=0.2,
                vad_filter=False,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                # TODO fix language to english for better performance?
                # German is being translated, but what is the accuracy like?
                # Rather have slower but accurate answers with sebot
                language="en",  # Let model decide which language its picking up
            )
            # Join all non-empty segment texts
            return " ".join(seg.text.strip() for seg in segments if seg.text.strip())
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""

    def _process_partial(self, audio_data):
        """
        Transcribes a partial audio buffer and appends the result to partials.
        Runs in a background thread.
        """
        # Transcribe the audio buffer and append result to partials if not empty
        text = self.transcribe_buffer(audio_data)
        if text:
            self.partials.append(text)
            print(f"[DEBUG] partial {len(self.partials)} → {text}")

    def safe_process_current_buffer(self):
        """
        Safely processes the current audio buffer as a partial transcription.
        Clears the buffer and starts a background thread for processing.
        """
        # Lock buffer to safely extract and clear current audio
        with self.buffer_lock:
            if not self.current_buffer:
                return
            audio_data = np.concatenate(list(self.current_buffer))
            self.current_buffer.clear()

        # Start a background thread to process this partial
        thread = threading.Thread(
            target=self._process_partial, args=(audio_data,), daemon=True
        )
        thread.start()

        # Track the thread so we can wait for all partials before finalizing
        with self.partial_threads_lock:
            self.partial_threads.append(thread)

    def _process_final_message(self, audio_data):
        """
        Waits for all partial threads to finish, processes any remaining audio,
        combines all partials into a full message, and adds it to the queue.
        Runs in a background thread.
        """
        # Wait for all partial-processing threads to finish before finalizing
        with self.partial_threads_lock:
            threads_to_wait = list(self.partial_threads)
            self.partial_threads.clear()
        for t in threads_to_wait:
            t.join()

        # Process any remaining audio not yet transcribed
        last_text = self.transcribe_buffer(audio_data)
        if last_text:
            self.partials.append(last_text)

        # Combine all partials into a single full message
        full_message = " ".join(self.partials)
        self.partials.clear()

        # Push to queue if not empty (thread-safe, as only one final thread runs at a time)
        if full_message:
            self.full_message_queue.append(full_message)

    def audio_callback(self, indata, frames, time_info, status):
        """
        Callback for the audio stream. Handles chunking, voice activity detection,
        and triggers partial/final transcription based on silence duration.
        """
        if status:
            print(status)

        audio_chunk = self._extract_audio_chunk(indata)
        current_time = time.time()
        if not self.is_recording:
            return

        if self.detect_voice_activity(audio_chunk):
            self._handle_speech_detected(audio_chunk, current_time)
        else:
            self._handle_silence(current_time)

    def _extract_audio_chunk(self, indata):
        """Extract mono audio from input and convert to float32."""
        return indata[:, 0].astype(np.float32)

    def _handle_speech_detected(self, audio_chunk, current_time):
        """Handle logic when speech is detected in the audio chunk."""
        with self.buffer_lock:
            self.current_buffer.append(audio_chunk)
        self.last_speech_time = current_time
        self.last_chunk_time = current_time

    def _handle_silence(self, current_time):
        """Handle logic when silence is detected in the audio chunk."""
        chunk_time = current_time - self.last_chunk_time
        silence_time = current_time - self.last_speech_time

        # Short pause: process a partial (non-blocking, keeps UI responsive)
        if chunk_time > self.short_silence_duration and len(self.current_buffer) > 0:
            self.safe_process_current_buffer()
            self.last_chunk_time = current_time

        # Long pause: treat as end of utterance, process as final message
        if silence_time > self.long_silence_duration:
            print(f"[DEBUG] Long pause detected! silence_time={silence_time:.2f}s")
            self.is_recording = False
            final_audio = self._get_final_audio()
            # Always start a thread for final message, even if no new audio (ensures queue is flushed)
            if final_audio is not None:
                threading.Thread(
                    target=self._process_final_message,
                    args=(final_audio,),
                    daemon=True,
                ).start()
            else:
                # Still need to send the message with just partials
                threading.Thread(
                    target=self._process_final_message,
                    args=(np.array([]),),
                    daemon=True,
                ).start()

    def _get_final_audio(self):
        """Extracts the remaining audio after the last partial for final transcription."""
        with self.buffer_lock:
            if self.current_buffer:
                remaining_chunks = list(self.current_buffer)[self.last_partial_index:]
                if remaining_chunks:
                    final_audio = np.concatenate(remaining_chunks)
                else:
                    final_audio = None
                self.current_buffer.clear()
                self.last_partial_index = 0
            else:
                final_audio = None
        return final_audio

    def start_stream(self):
        """
        Starts the audio input stream and continuously listens for speech.
        """
        # Open the audio input stream and continuously listen for speech
        with sd.InputStream(
            channels=1,
            samplerate=self.SAMPLERATE,
            blocksize=self.CHUNK_SIZE,
            dtype="float32",
            callback=self.audio_callback,
            latency="high",
        ):
            while True:
                time.sleep(0.1)