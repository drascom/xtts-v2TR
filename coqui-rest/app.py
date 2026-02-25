import os
import tempfile
from pathlib import Path
from typing import Optional

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from TTS.api import TTS

app = FastAPI(title="Coqui TTS REST", version="1.0.0")

MODEL_NAME = os.getenv("COQUI_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2")
MODEL_PATH = os.getenv("COQUI_MODEL_PATH", "")
CONFIG_PATH = os.getenv("COQUI_CONFIG_PATH", "")
USE_CUDA = os.getenv("COQUI_USE_CUDA", "false").lower() == "true"
OUTPUT_DIR = Path(os.getenv("COQUI_OUTPUT_DIR", "/app/data/output"))
SPEAKERS_DIR = Path(os.getenv("COQUI_SPEAKERS_DIR", "/app/data/speakers"))
DEFAULT_LANGUAGE = os.getenv("COQUI_DEFAULT_LANGUAGE", "")
DEFAULT_SPEAKER_WAV = os.getenv("COQUI_DEFAULT_SPEAKER_WAV", "")

ENGINE: Optional[TTS] = None


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    speaker: Optional[str] = None
    speaker_wav: Optional[str] = None
    language: Optional[str] = None


class TTSFileRequest(TTSRequest):
    file_name: str = Field(..., min_length=1)


def _resolve_speaker_wav(speaker_wav: Optional[str]) -> Optional[str]:
    if not speaker_wav:
        return None
    wav_path = Path(speaker_wav)
    if wav_path.is_absolute():
        return str(wav_path)
    return str(SPEAKERS_DIR / wav_path)


def _is_xtts_mode() -> bool:
    if MODEL_PATH and CONFIG_PATH:
        return True
    return "xtts" in MODEL_NAME.lower()


def _tts_to_file(req: TTSRequest, out_path: Path) -> None:
    if ENGINE is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    kwargs = {
        "text": req.text,
        "file_path": str(out_path),
    }

    speaker_wav_value = req.speaker_wav or DEFAULT_SPEAKER_WAV
    speaker_wav = _resolve_speaker_wav(speaker_wav_value) if speaker_wav_value else None
    language_value = req.language or DEFAULT_LANGUAGE

    if req.speaker:
        kwargs["speaker"] = req.speaker
    if speaker_wav:
        kwargs["speaker_wav"] = speaker_wav
    if language_value:
        kwargs["language"] = language_value

    if _is_xtts_mode() and "language" not in kwargs:
        raise HTTPException(status_code=400, detail="language is required in XTTS mode (or set COQUI_DEFAULT_LANGUAGE)")
    if _is_xtts_mode() and "speaker_wav" not in kwargs and "speaker" not in kwargs:
        raise HTTPException(
            status_code=400,
            detail="speaker_wav or speaker is required in XTTS mode (or set COQUI_DEFAULT_SPEAKER_WAV)",
        )

    try:
        ENGINE.tts_to_file(**kwargs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {exc}") from exc

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="Output WAV was not created")


@app.on_event("startup")
def startup() -> None:
    global ENGINE
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SPEAKERS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        if MODEL_PATH and CONFIG_PATH:
            ENGINE = TTS(model_path=MODEL_PATH, config_path=CONFIG_PATH, progress_bar=False)
        else:
            ENGINE = TTS(MODEL_NAME, progress_bar=False)
        if USE_CUDA and torch.cuda.is_available():
            ENGINE = ENGINE.to("cuda")
    except Exception as exc:
        if MODEL_PATH and CONFIG_PATH:
            raise RuntimeError(
                f"Failed to initialize model from model_path='{MODEL_PATH}', config_path='{CONFIG_PATH}': {exc}"
            ) from exc
        raise RuntimeError(f"Failed to initialize model '{MODEL_NAME}': {exc}") from exc


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if ENGINE is not None else "error",
        "mode": "xtts_local" if _is_xtts_mode() else "standard",
        "model": MODEL_NAME,
        "model_path": MODEL_PATH,
        "config_path": CONFIG_PATH,
        "default_language": DEFAULT_LANGUAGE,
        "default_speaker_wav": DEFAULT_SPEAKER_WAV,
        "cuda_enabled": USE_CUDA,
        "cuda_available": torch.cuda.is_available(),
    }


@app.get("/voices")
def voices() -> dict:
    if ENGINE is None:
        raise HTTPException(status_code=500, detail="Model not loaded")

    speakers = getattr(ENGINE, "speakers", None)
    languages = getattr(ENGINE, "languages", None)
    return {
        "speakers": speakers or [],
        "languages": languages or [],
    }


@app.get("/models")
def models() -> dict:
    try:
        all_models = TTS().list_models()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {exc}") from exc
    return {"models": all_models}


@app.post("/tts")
def tts(req: TTSRequest):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=str(OUTPUT_DIR)) as tmp:
        out_path = Path(tmp.name)

    try:
        _tts_to_file(req, out_path)
        return FileResponse(path=str(out_path), media_type="audio/wav", filename="output.wav")
    except Exception:
        out_path.unlink(missing_ok=True)
        raise


@app.post("/tts_to_file")
def tts_to_file(req: TTSFileRequest):
    safe_name = Path(req.file_name).name
    out_path = OUTPUT_DIR / safe_name
    _tts_to_file(req, out_path)
    return {"message": "ok", "output_path": str(out_path)}
