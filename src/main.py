import threading
import time
from streaming_stt import WhisperModel, WakeWordActivation, StreamingSTT
from src.ai_api import classification
import json

def main():
    # Load the model once
    whisper_model_size = "small"
    whisper_model = WhisperModel(
        f"Systran/faster-whisper-{whisper_model_size}",
        device="cpu",
        compute_type="int8"
    )
    stt = StreamingSTT(model=whisper_model)
    activator = WakeWordActivation()
    stt_thread = threading.Thread(target=stt.start_stream, daemon=True)
    stt_thread.start()
    try:
        while True:
            activator.wait_for_wake()
            print("Starting transcription. Speak into your microphone...")
            stt.is_recording = True # Activate the transcription via flag
            # Update the last speech times to now
            now = time.time()
            stt.last_speech_time = now
            stt.last_chunk_time = now
            while True:
                try:
                    time.sleep(0.05)
                    if stt.full_message_queue:
                        msg = stt.full_message_queue.popleft()
                        print("\n" + "=" * 50)
                        print("[QUEUE] Message received:")
                        print("[QUEUE MESSAGE]", msg)
                        try:
                            result = classification(msg)
                            try:
                                parsed = json.loads(result)
                                print("[CLASSIFICATION]", json.dumps(parsed, indent=2, ensure_ascii=False))
                            except Exception:
                                # If not valid JSON, just print raw
                                print("[CLASSIFICATION RAW]", result)
                        except Exception as e:
                            print("[CLASSIFICATION ERROR]", str(e))
                        print("=" * 50 + "\n")
                        stt.is_recording = False
                        break
                except KeyboardInterrupt:
                    print("Stopping transcription after next wake word...")
                    stt.is_recording = False
                    # After breaking, will return to wait_for_wake, then exit
                    raise
    except KeyboardInterrupt:
        print("Stopping transcription...")
    finally:
        activator.stop()


if __name__ == "__main__":
    main()
