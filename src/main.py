import threading
import time
from streaming_stt import WhisperModel, WakeWordActivation, StreamingSTT
from llm.api import classification, conversation
from web_search import run_web_search
from tts import speak
import json


def setup_services(whisper_model_size: str = "small"):
    """Initialize and return (whisper_model, stt, activator, stt_thread).

    The caller is responsible for starting/stopping threads and activator.
    """
    whisper_model = WhisperModel(
        f"Systran/faster-whisper-{whisper_model_size}",
        device="cpu",
        compute_type="int8"
    )
    stt = StreamingSTT(model=whisper_model)
    activator = WakeWordActivation()
    stt_thread = threading.Thread(target=stt.start_stream, daemon=True)
    return stt, activator, stt_thread


def process_queue_message(msg: str, stt: StreamingSTT):
    """Process a single transcribed message from the queue.

    Returns True if processing completed and the caller should stop recording.
    """
    print("\n" + "=" * 50)
    print("[QUEUE] Message received:")
    print("[QUEUE MESSAGE]", msg)
    try:
        result = classification(msg)
        try:
            parsed = json.loads(result)
            print("[CLASSIFICATION]", json.dumps(parsed, indent=2, ensure_ascii=False))

            # Is classification the proper JSON return format?
            if isinstance(parsed, dict):
                intent = parsed.get("intent") or {}
                category = intent.get("category")
                # Only run web_search if desired
                if category == "web_search" or category == "web_search_with_wiki":
                    prompt = intent.get("description")
                    web_search_output = run_web_search(prompt, category)
                    # Print a short summary of results
                    print("[WEB SEARCH PROMPT]", web_search_output.get("prompt"))
                    print("[WIKI EXCERPT]", web_search_output.get("wiki"))
                    print("[RESULTS]", "\n".join(web_search_output.get("results", [])))
                
                # Build the prompt to send to the LLM safely
                corrected = parsed.get("corrected_text") or ""
                try:
                    is_unchanged = isinstance(corrected, str) and corrected.lower() == "unchanged"
                except Exception:
                    is_unchanged = False

                if is_unchanged:
                    llm_prompt = msg
                elif isinstance(corrected, str) and corrected:
                    llm_prompt = corrected
                else:
                    llm_prompt = msg

                # Prepare additional_data as a dict
                additional_data = parsed.get("additional_data") or {}
                # Attach web search results if available
                if 'web_search_output' in locals() and web_search_output:
                    additional_data = additional_data or {}
                    additional_data.setdefault("wiki", web_search_output.get("wiki", ""))
                    additional_data.setdefault("recent_searches", web_search_output.get("results", []))

                answer = conversation(prompt=llm_prompt, additional_data=additional_data)
                print("[LLM ANSWER]", answer)
                speak(answer, voice="en_US", wait=False)
                    
        except Exception:
            # If not valid JSON, just print raw
            print("[CLASSIFICATION RAW]", result)
    except Exception as e:
        print("[CLASSIFICATION ERROR]", str(e))
    print("=" * 50 + "\n")
    stt.is_recording = False
    return True

def reset_stt_flags(stt: StreamingSTT):
    # Reset all flags
    stt.is_recording = False
    stt.recording_start_time = None
    stt.last_speech_time = None
    stt.last_chunk_time = None
    stt.in_initial_grace_period = False


def main():
    # Setup services and start background threads
    stt, activator, stt_thread = setup_services()
    stt_thread.start()

    try:
        while True:
            activator.wait_for_wake()
            print("Starting transcription. Speak into your microphone...")
            stt.is_recording = True  # Activate the transcription via flag
            stt.in_initial_grace_period = True  # Enable grace period for this recording session

            # Update the last speech times to now
            now = time.time()
            stt.recording_start_time = now
            stt.last_speech_time = None  # Reset to None so grace period works
            stt.last_chunk_time = now

            # Wait for the transcribed message to appear in the queue
            try:
                while True:
                    time.sleep(0.05)
                    if stt.full_message_queue:
                        reset_stt_flags(stt)
                        # Extract latest message
                        msg = stt.full_message_queue.popleft()
                        # Process the message and stop recording afterwards
                        process_queue_message(msg, stt)
                        break
            except KeyboardInterrupt:
                print("Stopping transcription after next wake word...")
                reset_stt_flags(stt)
                raise
    except KeyboardInterrupt:
        print("Stopping transcription...")
    finally:
        activator.stop()


if __name__ == "__main__":
    main()
