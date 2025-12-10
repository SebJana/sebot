# Test script -download voice model files
# from https://huggingface.co/rhasspy/piper-voices/tree/main

import wave
import pygame
import time
from piper import PiperVoice

# Initialize pygame mixer
pygame.mixer.init()

# en_GB: Alba/Cori
# de: Thorsten/Thorsten emotional für Whisper
# en_US: Amy/Ryan

german_test = "Hallo, Ich bin Sebot, wie kann ich dir helfen?"
english_test = "Photosynthesis is the biological process by which plants, algae, and some bacteria convert light energy into chemical energy. Using sunlight, carbon dioxide, and water, these organisms produce glucose and oxygen. Chlorophyll, the green pigment in leaves, absorbs sunlight, initiating a series of chemical reactions known as the light-dependent and light-independent (Calvin cycle) reactions. In the light-dependent reactions, water is split, releasing oxygen and producing ATP and NADPH, which are energy carriers. During the Calvin cycle, carbon dioxide is fixed into glucose, providing energy and organic material for growth. Photosynthesis is essential for life, producing oxygen and forming the base of the food chain"

# "Hello, I'm Sebot, how can I help you today?"

print("Loading voice models...")
start_time = time.time()

de_voice = PiperVoice.load("voices/de/de_DE-thorsten-medium.onnx")
en_US_voice = PiperVoice.load("voices/en-US/en_US-amy-medium.onnx")
en_GB_voice = PiperVoice.load("voices/en-GB/en_GB-alba-medium.onnx")

load_time = time.time() - start_time
print(f"Voice models loaded in {load_time:.2f} seconds")

# Generate German speech
print("Generating German audio...")
start_time = time.time()
with wave.open("de.wav", "wb") as wav_file:
    de_voice.synthesize_wav(german_test, wav_file)
german_time = time.time() - start_time
print(f"German audio created in {german_time:.2f} seconds")

# Generate American English speech  
print("Generating American English audio...")
start_time = time.time()
with wave.open("en_US.wav", "wb") as wav_file:
    en_US_voice.synthesize_wav(english_test, wav_file)
american_time = time.time() - start_time
print(f"American English audio created in {american_time:.2f} seconds")

# Generate British English speech
print("Generating British English audio...")
start_time = time.time()
with wave.open("en_GB.wav", "wb") as wav_file:
    en_GB_voice.synthesize_wav(english_test, wav_file)
british_time = time.time() - start_time
print(f"British English audio created in {british_time:.2f} seconds")

total_creation_time = german_time + american_time + british_time
print(f"\nTotal audio creation time: {total_creation_time:.2f} seconds")

print("Audio generated. Playing...")

# Play German audio first
print("Playing German audio...")
pygame.mixer.music.load("de.wav")
pygame.mixer.music.play()

# Wait for German audio to finish
while pygame.mixer.music.get_busy():
    pygame.time.wait(100)

# Play American audio second
print("Playing American audio...")
pygame.mixer.music.load("en_US.wav")
pygame.mixer.music.play()

# Wait for American audio to finish
while pygame.mixer.music.get_busy():
    pygame.time.wait(100)
    
# Play British audio second
print("Playing British audio...")
pygame.mixer.music.load("en_GB.wav")
pygame.mixer.music.play()

# Wait for British audio to finish
while pygame.mixer.music.get_busy():
    pygame.time.wait(100)


print("All playback finished.")
pygame.mixer.music.play()
