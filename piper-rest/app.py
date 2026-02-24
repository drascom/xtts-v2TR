import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Piper TTS REST", version="1.0.0")

MODELS_DIR = Path(os.getenv("PIPER_MODELS_DIR", "/app/data/models"))
OUTPUT_DIR = Path(os.getenv("PIPER_OUTPUT_DIR", "/app/data/output"))
MODEL_PATH_ENV = os.getenv("PIPER_MODEL_PATH", "")
MODEL_URL = os.getenv("PIPER_MODEL_URL", "")
MODEL_CONFIG_URL = os.getenv("PIPER_MODEL_CONFIG_URL", "")
DEFAULT_SPEAKER = os.getenv("PIPER_DEFAULT_SPEAKER", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
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

    with requests.get(url, stream=True, timeout=120, headers=headers) as resp:
        resp.raise_for_status()
        with target.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)


def _resolve_model_path() -> Path:
    if MODEL_PATH_ENV:
        model = Path(MODEL_PATH_ENV)
        if not model.is_absolute():
            model = MODELS_DIR / model
        if model.exists():
            return model
        raise RuntimeError(f"Configured model path not found: {model}")

    models = sorted(MODELS_DIR.glob("*.onnx"))
    if models:
        return models[0]

    if MODEL_URL:
        file_name = Path(MODEL_URL.split("?")[0]).name or "model.onnx"
        model = MODELS_DIR / file_name
        _download_file(MODEL_URL, model)

        if MODEL_CONFIG_URL:
            config_name = Path(MODEL_CONFIG_URL.split("?")[0]).name or f"{file_name}.json"
            _download_file(MODEL_CONFIG_URL, MODELS_DIR / config_name)

        return model

    raise RuntimeError(
        "No model found. Provide PIPER_MODEL_PATH, place a .onnx in PIPER_MODELS_DIR, or set PIPER_MODEL_URL."
    )


def _build_cmd(model_path: Path, output_file: Path, req: TTSRequest) -> list[str]:
    cmd = ["piper", "--model", str(model_path), "--output_file", str(output_file)]

    speaker_id = req.speaker_id
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


def _synthesize_to_path(req: TTSRequest, out_path: Path) -> Path:
    model_path = _resolve_model_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = _build_cmd(model_path, out_path, req)
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
                "stderr": proc.stderr[-4000:],
                "stdout": proc.stdout[-4000:],
            },
        )

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="Output WAV was not created")

    return out_path


@app.on_event("startup")
def startup_check() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict:
    model_name = None
    try:
        model_name = _resolve_model_path().name
        status = "ok"
    except Exception as exc:
        status = "error"
        model_name = str(exc)

    return {
        "status": status,
        "model": model_name,
        "models_dir": str(MODELS_DIR),
        "output_dir": str(OUTPUT_DIR),
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
        _synthesize_to_path(req, out_path)
        return FileResponse(path=str(out_path), media_type="audio/wav", filename="output.wav")
    except Exception:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        raise


@app.post("/tts_to_file")
def tts_to_file(req: TTSFileRequest):
    safe_name = Path(req.file_name).name
    out_path = OUTPUT_DIR / safe_name
    _synthesize_to_path(req, out_path)
    return {"message": "ok", "output_path": str(out_path)}
