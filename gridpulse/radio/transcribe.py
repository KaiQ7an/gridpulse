"""Team radio to text, locally, with Whisper (faster-whisper, CPU, no account needed).

Transcripts are cached on disk by clip URL, so each clip is only ever
transcribed once and the dashboard can show cached text instantly.
Install the extra first: `pip install -e ".[transcribe]"`.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import requests

from gridpulse.session import CACHE_DIR

AUDIO_DIR = CACHE_DIR / "radio_audio"
TEXT_DIR = CACHE_DIR / "radio_text"
MODEL_DIR = CACHE_DIR / "whisper"
DEFAULT_MODEL = "small.en"

# Whisper takes a short "previous text" as a hint. Naming the driver on the clip and
# some F1 jargon makes it far likelier to write "Lando" and "box, box" than "Landa"
# and "bucks bucks". (Listing the whole grid made it invent names that weren't said.)
F1_JARGON = (
    "Box, box. Push now. Tyres, degradation, deg, undercut, overcut, DRS, safety car, VSC, Plan B, gap, "
    "delta, pit window, P1, copy."
)


def prompt_for(first_name: str | None) -> str:
    who = f" between {first_name} and the race engineer" if first_name else ""
    return f"Formula 1 team radio{who}. {F1_JARGON}"


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _key(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:20]


def cached(url: str) -> dict | None:
    """The stored transcript for a clip (text plus any translations), or None."""
    path = TEXT_DIR / f"{_key(url)}.json"
    return json.loads(path.read_text()) if path.exists() else None


def save(url: str, record: dict) -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    (TEXT_DIR / f"{_key(url)}.json").write_text(json.dumps(record, ensure_ascii=False))


def load_audio(path: Path, rate: int = 16000) -> np.ndarray:
    """Decode an audio file to 16 kHz mono float32, the input Whisper expects."""
    import av

    with av.open(str(path)) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
        chunks = [f.to_ndarray() for frame in container.decode(audio=0) for f in resampler.resample(frame)]
        chunks += [f.to_ndarray() for f in resampler.resample(None)]
    return np.concatenate(chunks, axis=1).flatten().astype(np.float32) / 32768.0


def _audio_file(url: str) -> Path:
    path = AUDIO_DIR / f"{_key(url)}.mp3"
    if not path.exists():
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
    return path


class Transcriber:
    """Loads the Whisper model once, then transcribes clips (using the cache when it can)."""

    def __init__(self, model: str = DEFAULT_MODEL):
        from faster_whisper import WhisperModel

        self.model_name = model
        self.model = WhisperModel(model, device="cpu", compute_type="int8", download_root=str(MODEL_DIR))

    def transcribe(self, url: str, first_name: str | None = None) -> str:
        hit = cached(url)
        if hit and hit.get("text") is not None:
            return hit["text"]
        audio = load_audio(_audio_file(url))
        segments, _ = self.model.transcribe(
            audio, language="en", beam_size=5, vad_filter=True, initial_prompt=prompt_for(first_name),
            condition_on_previous_text=False,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        save(url, {**(hit or {}), "text": text, "model": self.model_name})
        return text
