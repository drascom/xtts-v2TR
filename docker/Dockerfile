# Use an official NVIDIA base image with CUDA support
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

# Set label for the docker image description
LABEL description="Docker image for xtts-api-server"

# Install required packages (avoid cache to reduce image size)
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    python3-dev portaudio19-dev libportaudio2 libasound2-dev libportaudiocpp0 \
    git python3 python3-pip make g++ ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install virtualenv
RUN python3 -m pip install --upgrade pip setuptools wheel ninja virtualenv

# Copy the application source code to /app directory and change the workdir to /app
# COPY . /app
# WORKDIR /app

# Install Python dependencies
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
RUN pip install deepspeed
RUN pip install xtts-api-server
# Runtime patch for coqpit on Python 3.10:
# - handle PEP604 unions (e.g. float | list[float])
# - guard issubclass() calls for non-class typing objects
RUN python3 - <<'PY'
import site
from pathlib import Path

sitecustomize_path = Path(site.getsitepackages()[0]) / "sitecustomize.py"
sitecustomize_path.write_text(
    """
import types
from typing import Union, get_origin

try:
    import coqpit.coqpit as _coqpit

    def _patched_is_union(arg_type):
        try:
            origin = get_origin(arg_type)
            if origin is Union:
                return True
        except Exception:
            pass
        try:
            if isinstance(arg_type, types.UnionType):
                return True
        except Exception:
            pass
        try:
            return _coqpit.safe_issubclass(arg_type.__origin__, Union)
        except Exception:
            return False

    def _patched_deserialize(x, field_type):
        if _coqpit.is_dict(field_type):
            return _coqpit._deserialize_dict(x)
        if _coqpit.is_list(field_type):
            return _coqpit._deserialize_list(x, field_type)
        if _coqpit.is_union(field_type):
            return _coqpit._deserialize_union(x, field_type)
        if isinstance(field_type, type) and issubclass(field_type, _coqpit.Serializable):
            return field_type.deserialize_immutable(x)
        if _coqpit.is_primitive_type(field_type):
            return _coqpit._deserialize_primitive_types(x, field_type)
        raise ValueError(f" [!] '{type(x)}' value type of '{x}' does not match '{field_type}' field type.")

    _coqpit.is_union = _patched_is_union
    _coqpit._deserialize = _patched_deserialize
except Exception:
    pass
""".lstrip(),
    encoding="utf-8",
)
print(f"Wrote runtime patch: {sitecustomize_path}")
PY

# Expose the container ports
EXPOSE 8020

# Run xtts_api_server when the container starts
CMD ["bash", "-c", "python3 -m xtts_api_server --listen -p 8020 -t 'http://localhost:8020' -sf 'xtts-server/speakers' -o 'xtts-server/output' -mf 'xtts-server/models' --deepspeed"]
