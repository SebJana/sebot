
# Porcupine Wake Word Model

This folder contains custom Porcupine wake word models for use with the bot activation.

## How to Use

1. Visit [Picovoice Console](https://picovoice.ai/console/) to create and train your own wake word model for your desired phrase.
2. Download the `.ppn` model file for your operating system (e.g., `hey_atlas.ppn`).
3. Place the downloaded `.ppn` file in this `porcupine-model` directory.
4. In your .env, set the `POCCUPINE_MODEL_FILE_NAME` to the relative path of your model file:
	```python
	POCCUPINE_MODEL_FILE_NAME = "hey_atlas.ppn"
	```

## Notes

- Make sure your Picovoice Access Key is valid and set in your script.
- Model files are platform-specific. Download the correct version for your OS.


**Important:** Be sure to review Picovoice's licensing terms for private and organizational use before deploying your model. See their website for details.