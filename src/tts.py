import os
import wave
import uuid
from playsound3 import playsound
from piper import PiperVoice
import threading

# Project paths
project_root = os.path.dirname(os.path.dirname(__file__))
audio_dir = os.path.join(project_root, "audio")
os.makedirs(audio_dir, exist_ok=True)

# Cache for loaded voices
_voice_cache = {}
_voice_cache_lock = threading.Lock()

# Map logical voice keys to relative voice file paths in the repo
_VOICE_PATHS = {
    "en_US": os.path.join(project_root, "voices", "en-US", "en_US-amy-medium.onnx"),
    "en_GB": os.path.join(project_root, "voices", "en-GB", "en_GB-alba-medium.onnx"),
    "de": os.path.join(project_root, "voices", "de", "de_DE-thorsten-medium.onnx"),
}

def _load_voice(key: str) -> PiperVoice:
    """Load and cache a PiperVoice for the given key."""
    key = key or "en_US"
    with _voice_cache_lock:
        if key in _voice_cache:
            return _voice_cache[key]

        path = _VOICE_PATHS.get(key)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Voice for key '{key}' not found at {path}")

        voice = PiperVoice.load(path)
        _voice_cache[key] = voice
        return voice

def synthesize_to_wav(text: str, voice_key: str, out_path: str):
    """Synthesize text to a WAV file at out_path using the selected voice."""
    voice = _load_voice(voice_key)
    with wave.open(out_path, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)

def play_wav(path: str, wait: bool = True):
    """
    Play a WAV file on the default audio device using playsound3.

    If wait is False, playback happens in the background.
    """
    playsound(path, block=wait)

def speak(text: str, voice: str = "en_US", wait: bool = True) -> str:
    """
    Synthesize `text` using `voice` and play it on the default device.
    If wait is False, playback happens in the background.

    Returns the path to the generated WAV file.
    """
    fname = "tts_recent.wav"
    out_path = os.path.join(audio_dir, fname)

    synthesize_to_wav(text, voice, out_path)
    play_wav(out_path, wait=wait)

    return out_path

__all__ = ["speak", "play_wav"]