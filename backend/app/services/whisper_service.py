from faster_whisper import WhisperModel

print("[Whisper] Loading model...")

model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("[Whisper] Model loaded")


def transcribe_audio(audio_path):
    segments, info = model.transcribe(audio_path)

    transcript = ""

    for segment in segments:
        transcript += segment.text + " "

    return transcript.strip()