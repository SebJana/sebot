"""
StreamingSTT: Real-time streaming speech-to-text (STT) using Whisper.
See 'simple_streaming_stt_README.py' for an overview and usage details.
"""

import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import threading
import time
from collections import deque


# TODO implement wake on word library, to start recording via "Hey Sebot"
class StreamingSTT:
    def __init__(self, model_size="small"):
        """
        Streaming speech-to-text (STT) with real-time partial and final message output.
        Loads a Whisper model and sets up audio streaming parameters.
        """

        # Load the Whisper model for transcription. Model size can be 'tiny', 'small', etc.
        self.model_path = f"whisper-models/models--Systran--faster-whisper-{model_size}"
        self.model = WhisperModel(self.model_path, device="cpu", compute_type="int8")

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
        self.silence_threshold = 0.008  # TODO: Adapt to environment and mic sensitivity
        self.min_audio_length = (
            0.5  # Minimum audio length (seconds) for valid transcription
        )
        self.short_silence_duration = 0.3  # Short pause (seconds) triggers partial message transcription
        self.long_silence_duration = 1.5  # Long pause (seconds) triggers final message

        # State variables for speech detection and timing
        self.is_recording = False
        self.last_speech_time = time.time()  # Last time speech was detected
        self.last_chunk_time = time.time()  # Last time a chunk was processed

        # List of threads currently processing partials
        self.partial_threads = []
        # Lock to protect access to partial_threads
        self.partial_threads_lock = threading.Lock()

        # Queue for full messages (max 10 to prevent unbounded growth, meaning last 10 prompts)
        self.full_message_queue = deque(maxlen=10)

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
                temperature=0.0,
                vad_filter=False,
                language=None,  # Let model decide which language its picking up
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

        # Extract mono audio from input and convert to float32
        audio_chunk = indata[:, 0].astype(np.float32)
        current_time = time.time()
        has_speech = self.detect_voice_activity(audio_chunk)

        if has_speech:
            # Start recording if speech detected
            if not self.is_recording:
                self.is_recording = True
            # Append chunk to buffer (thread-safe)
            with self.buffer_lock:
                self.current_buffer.append(audio_chunk)
            self.last_speech_time = current_time
            self.last_chunk_time = current_time
        else:
            # If not currently recording, ignore silence
            if not self.is_recording:
                return

            # Calculate time since last chunk and last speech
            chunk_time = current_time - self.last_chunk_time
            silence_time = current_time - self.last_speech_time

            # Short pause: process a partial (non-blocking, keeps UI responsive)
            if (
                chunk_time > self.short_silence_duration
                and len(self.current_buffer) > 0
            ):
                self.safe_process_current_buffer()
                self.last_chunk_time = current_time

            # Long pause: treat as end of utterance, process as final message
            if silence_time > self.long_silence_duration:
                print(f"[DEBUG] Long pause detected! silence_time={silence_time:.2f}s")
                self.is_recording = False
                with self.buffer_lock:
                    if self.current_buffer:
                        # Only process audio that came AFTER the last partial
                        # (prevents duplicate transcription)
                        remaining_chunks = list(self.current_buffer)[
                            self.last_partial_index :
                        ]
                        if remaining_chunks:
                            final_audio = np.concatenate(remaining_chunks)
                        else:
                            final_audio = None
                        self.current_buffer.clear()
                        self.last_partial_index = 0
                    else:
                        final_audio = None

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


def main():
    """
    Entry point: starts the streaming STT and prints messages from the queue.
    """

    stt = StreamingSTT(model_size="small")
    print("Starting transcription. Speak into your microphone...")

    # Start the audio stream in a background thread so the main thread can process messages
    threading.Thread(target=stt.start_stream, daemon=True).start()

    try:
        while True:
            # TODO often Thank you. What noise is interpreted as thank you?
            time.sleep(0.05)  # Non-blocking sleep
            # Consume messages from queue without blocking
            if stt.full_message_queue:
                msg = stt.full_message_queue.popleft()
                print("\n" + "=" * 50)
                print("[QUEUE] Message received:")
                print("[QUEUE MESSAGE]", msg)
                print("=" * 50 + "\n")
    except KeyboardInterrupt:
        print("Stopping transcription...")


if __name__ == "__main__":
    main()
