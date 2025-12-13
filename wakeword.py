
import os
import pvporcupine
import pyaudio
import struct
from dotenv import load_dotenv
load_dotenv()

# Load sensitive data from environment variables
ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")
MODEL_FILE_NAME = os.getenv("POCCUPINE_MODEL_FILE_NAME", "")

model_path = f"porcupine-model/{MODEL_FILE_NAME}"

porcupine = pvporcupine.create(
    access_key=ACCESS_KEY,
    keyword_paths=[model_path],  # 👈 custom model here
    sensitivities=[0.8]            # 0.0–1.0
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
    while True:
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
            print("🔥 Wake word detected!")
            break

finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
    porcupine.delete()