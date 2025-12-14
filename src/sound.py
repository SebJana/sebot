from playsound3 import playsound
import os
import threading
import time


# Global flag to control thinking sound loop
_thinking_stop_flag = threading.Event()
_thinking_thread = None


def play_thinking():
    """Play the thinking sound 3 times, pause, then repeat (non-blocking)."""
    global _thinking_thread, _thinking_stop_flag
    
    # Stop any existing thinking sound first
    stop_thinking_sound()
    
    _thinking_stop_flag.clear()
    
    def thinking_loop():
        sound_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio", "bot_sounds", "thinking.mp3")
        while not _thinking_stop_flag.is_set():
            # Play 3 times with short pauses
            for _ in range(3):
                if _thinking_stop_flag.is_set():
                    return
                playsound(sound_path)
            # Bigger pause before next loop
            if not _thinking_stop_flag.is_set():
                time.sleep(0.5)
    
    _thinking_thread = threading.Thread(target=thinking_loop, daemon=True)
    _thinking_thread.start()


def stop_thinking_sound():
    """Stop the thinking sound loop."""
    global _thinking_stop_flag, _thinking_thread
    _thinking_stop_flag.set()
    if _thinking_thread is not None:
        _thinking_thread.join(timeout=1.0)


def play_wake_detected():
    """Play the wake word detected sound when the bot is activated (non-blocking)."""
    sound_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio", "bot_sounds", "wake_detected.mp3")
    threading.Thread(target=playsound, args=(sound_path,), daemon=True).start()


def play_wake_off():
    """Play the wake word off sound when the bot is deactivated (non-blocking)."""
    sound_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio", "bot_sounds", "wake_off.mp3")
    threading.Thread(target=playsound, args=(sound_path,), daemon=True).start()
