# Test script -download voice model files
# from https://huggingface.co/rhasspy/piper-voices/tree/main

import wave
import pygame
import os
from piper import PiperVoice

# Initialize pygame mixer
pygame.mixer.init()

# en_GB: Alba/Cori
# de: Thorsten/Thorsten emotional für Whisper
# en_US: Amy/Ryan

german_test = "Hallo, Ich bin Sebot, wie kann ich dir helfen?"
english_test = "Hello, I'm Sebot, how can I help you today?"

# Get the project root directory (two levels up from this file)
project_root = os.path.dirname(os.path.dirname(__file__))
audio_dir = os.path.join(project_root, "audio")

# Create audio directory if it doesn't exist
os.makedirs(audio_dir, exist_ok=True)

de_voice = PiperVoice.load(os.path.join(project_root, "voices", "de", "de_DE-thorsten-medium.onnx"))
en_US_voice = PiperVoice.load(os.path.join(project_root, "voices", "en-US", "en_US-amy-medium.onnx"))
en_GB_voice = PiperVoice.load(os.path.join(project_root, "voices", "en-GB", "en_GB-alba-medium.onnx"))

# Generate speech and save to WAV file
with wave.open(os.path.join(audio_dir, "de.wav"), "wb") as wav_file:
    de_voice.synthesize_wav(german_test, wav_file)

with wave.open(os.path.join(audio_dir, "en_US.wav"), "wb") as wav_file:
    en_US_voice.synthesize_wav(english_test, wav_file)

with wave.open(os.path.join(audio_dir, "en_GB.wav"), "wb") as wav_file:
    en_GB_voice.synthesize_wav(english_test, wav_file)

print("Audio generated. Playing...")


# Play German audio first
print("Playing German audio...")
pygame.mixer.music.load(os.path.join(audio_dir, "de.wav"))
pygame.mixer.music.play()

# Wait for German audio to finish
while pygame.mixer.music.get_busy():
    pygame.time.wait(100)

# Play American audio second
print("Playing American audio...")
pygame.mixer.music.load(os.path.join(audio_dir, "en_US.wav"))
pygame.mixer.music.play()

# Wait for American audio to finish
while pygame.mixer.music.get_busy():
    pygame.time.wait(100)

# Play British audio second
print("Playing British audio...")
pygame.mixer.music.load(os.path.join(audio_dir, "en_GB.wav"))
pygame.mixer.music.play()

# Wait for British audio to finish
while pygame.mixer.music.get_busy():
    pygame.time.wait(100)


print("All playback finished.")
pygame.mixer.music.play()
