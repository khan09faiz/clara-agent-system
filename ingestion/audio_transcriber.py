"""Transcribes audio and video call recordings to plain text using the OpenAI Whisper API."""

from pathlib import Path

import openai


SUPPORTED_EXTENSIONS = {".m4a", ".mp3", ".mp4", ".wav"}


class TranscriptionError(Exception):
    """Raised when the Whisper API call fails or a network error occurs."""

    def __init__(self, message: str, file_path: str) -> None:
        self.file_path = file_path
        super().__init__(message)


def transcribe_audio(file_path: str, api_key: str) -> str:
    """Transcribe an audio/video file using OpenAI Whisper and return raw text."""
    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    client = openai.OpenAI(api_key=api_key)

    try:
        with open(file_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        return response.text
    except Exception as exc:
        raise TranscriptionError(
            f"Transcription failed for '{file_path}': {exc}",
            file_path=file_path,
        ) from exc
