import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Piper TTS REST", version="1.1.0")

MODELS_DIR = Path(os.getenv("PIPER_MODELS_DIR", "/app/data/models"))
OUTPUT_DIR = Path(os.getenv("PIPER_OUTPUT_DIR", "/app/data/output"))
VOICES_FILE = Path(os.getenv("PIPER_VOICES_FILE", "/app/voices.json"))
DEFAULT_MODEL = os.getenv("PIPER_DEFAULT_MODEL", os.getenv("PIPER_DEFAULT_MODEL_KEY", "tr_dfki_female"))
MODEL_PATH_ENV = os.getenv("PIPER_MODEL_PATH", "")
MODEL_URL = os.getenv("PIPER_MODEL_URL", "")
MODEL_CONFIG_URL = os.getenv("PIPER_MODEL_CONFIG_URL", "")
DEFAULT_SPEAKER = os.getenv("PIPER_DEFAULT_SPEAKER", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")

VOICE_PRESETS: dict[str, dict] = {}


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    model: Optional[str] = None
    speaker_id: Optional[int] = None
    length_scale: Optional[float] = Field(default=None, gt=0)
    noise_scale: Optional[float] = Field(default=None, gt=0)
    noise_w: Optional[float] = Field(default=None, gt=0)


class TTSFileRequest(TTSRequest):
    file_name: str = Field(..., min_length=1)


def _download_file(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    headers = {}
    if HF_TOKEN.strip():
        headers["Authorization"] = f"Bearer {HF_TOKEN.strip()}"

    with requests.get(url, stream=True, timeout=180, headers=headers) as resp:
        resp.raise_for_status()
        with target.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)


def _ensure_model_from_urls(model_url: str, config_url: str = "") -> Path:
    model_name = Path(model_url.split("?")[0]).name or "model.onnx"
    model_path = MODELS_DIR / model_name

    if not model_path.exists():
        _download_file(model_url, model_path)

    if config_url:
        config_name = Path(config_url.split("?")[0]).name or f"{model_name}.json"
        config_path = MODELS_DIR / config_name
        if not config_path.exists():
            _download_file(config_url, config_path)

    return model_path


def _load_voice_presets() -> dict[str, dict]:
    if not VOICES_FILE.exists():
        return {}

    try:
        raw = json.loads(VOICES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in voices file {VOICES_FILE}: {exc}") from exc

    if not isinstance(raw, dict):
        raise RuntimeError(f"Voices file must be an object map: {VOICES_FILE}")

    cleaned: dict[str, dict] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        cleaned[key] = value
    return cleaned


def _resolve_model_from_preset(model: str) -> tuple[Path, Optional[int]]:
    preset = VOICE_PRESETS.get(model)
    if preset is None:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unknown model: {model}",
                "available_models": sorted(VOICE_PRESETS.keys()),
            },
        )

    speaker = preset.get("speaker_id")

    model_path_value = preset.get("model_path", "")
    model_url_value = preset.get("model_url", "")
    config_url_value = preset.get("config_url", "")

    if model_path_value:
        model_path = Path(model_path_value)
        if not model_path.is_absolute():
            model_path = MODELS_DIR / model_path
        if not model_path.exists():
            raise HTTPException(status_code=500, detail=f"Preset model_path not found: {model_path}")
        return model_path, speaker

    if model_url_value:
        return _ensure_model_from_urls(model_url_value, config_url_value), speaker

    raise HTTPException(status_code=500, detail=f"Preset is missing model_path/model_url: {model}")


def _resolve_model_path(req: TTSRequest) -> tuple[Path, Optional[int], str]:
    selected_model = (req.model or DEFAULT_MODEL).strip()

    if selected_model and selected_model in VOICE_PRESETS:
        model_path, preset_speaker = _resolve_model_from_preset(selected_model)
        return model_path, preset_speaker, selected_model

    if req.model and req.model.strip() and req.model not in VOICE_PRESETS:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unknown model: {req.model}",
                "available_models": sorted(VOICE_PRESETS.keys()),
            },
        )

    if MODEL_PATH_ENV:
        model = Path(MODEL_PATH_ENV)
        if not model.is_absolute():
            model = MODELS_DIR / model
        if model.exists():
            return model, None, "env_model_path"
        raise RuntimeError(f"Configured model path not found: {model}")

    models = sorted(MODELS_DIR.glob("*.onnx"))
    if models:
        return models[0], None, "first_local_model"

    if MODEL_URL:
        model = _ensure_model_from_urls(MODEL_URL, MODEL_CONFIG_URL)
        return model, None, "env_model_url"

    raise RuntimeError(
        "No model found. Provide model from /voices, set PIPER_DEFAULT_MODEL, "
        "or provide PIPER_MODEL_PATH/PIPER_MODEL_URL."
    )


def _build_cmd(model_path: Path, output_file: Path, req: TTSRequest, preset_speaker: Optional[int]) -> list[str]:
    cmd = ["piper", "--model", str(model_path), "--output_file", str(output_file)]

    speaker_id = req.speaker_id
    if speaker_id is None and preset_speaker is not None:
        speaker_id = preset_speaker

    if speaker_id is None and DEFAULT_SPEAKER.strip():
        try:
            speaker_id = int(DEFAULT_SPEAKER)
        except ValueError:
            pass

    if speaker_id is not None:
        cmd.extend(["--speaker", str(speaker_id)])

    if req.length_scale is not None:
        cmd.extend(["--length_scale", str(req.length_scale)])
    if req.noise_scale is not None:
        cmd.extend(["--noise_scale", str(req.noise_scale)])
    if req.noise_w is not None:
        cmd.extend(["--noise_w", str(req.noise_w)])

    return cmd


def _synthesize_to_path(req: TTSRequest, out_path: Path) -> tuple[Path, str]:
    model_path, preset_speaker, selected_model = _resolve_model_path(req)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = _build_cmd(model_path, out_path, req, preset_speaker)
    proc = subprocess.run(
        cmd,
        input=req.text,
        text=True,
        capture_output=True,
        check=False,
    )

    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "piper command failed",
                "model": selected_model,
                "stderr": proc.stderr[-4000:],
                "stdout": proc.stdout[-4000:],
            },
        )

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="Output WAV was not created")

    return out_path, selected_model


@app.on_event("startup")
def startup_check() -> None:
    global VOICE_PRESETS
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VOICE_PRESETS = _load_voice_presets()


@app.get("/health")
def health() -> dict:
    model_name = None
    selected_model = DEFAULT_MODEL
    try:
        test_req = TTSRequest(text="health-check", model=DEFAULT_MODEL)
        model_name, _, selected_model = _resolve_model_path(test_req)
        status = "ok"
        model_name = model_name.name
    except Exception as exc:
        status = "error"
        model_name = str(exc)

    return {
        "status": status,
        "default_model": selected_model,
        "model": model_name,
        "voices_count": len(VOICE_PRESETS),
        "models_dir": str(MODELS_DIR),
        "output_dir": str(OUTPUT_DIR),
    }


@app.get("/voices")
def voices() -> dict:
    result = {}
    for key, preset in VOICE_PRESETS.items():
        result[key] = {
            "description": preset.get("description", ""),
            "speaker_id": preset.get("speaker_id"),
            "model_url": preset.get("model_url", ""),
            "model_path": preset.get("model_path", ""),
        }
    return {
        "default_model": DEFAULT_MODEL,
        "voices": result,
    }


@app.get("/models")
def models() -> dict:
    files = sorted([p.name for p in MODELS_DIR.glob("*.onnx")])
    return {"models": files}


@app.post("/tts")
def tts(req: TTSRequest):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=str(OUTPUT_DIR)) as tmp:
        out_path = Path(tmp.name)

    try:
        _, selected_model = _synthesize_to_path(req, out_path)
        return FileResponse(
            path=str(out_path),
            media_type="audio/wav",
            filename=f"{selected_model}.wav",
            headers={"X-Model": selected_model},
        )
    except Exception:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        raise


@app.post("/tts_to_file")
def tts_to_file(req: TTSFileRequest):
    safe_name = Path(req.file_name).name
    out_path = OUTPUT_DIR / safe_name
    _, selected_model = _synthesize_to_path(req, out_path)
    return {"message": "ok", "model": selected_model, "output_path": str(out_path)}
