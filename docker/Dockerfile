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
# Patch coqpit deserialize bug that can crash on issubclass() with non-class typing fields.
RUN python3 - <<'PY'
import pathlib
import coqpit

p = pathlib.Path(coqpit.__file__)
s = p.read_text(encoding="utf-8")
old = "if issubclass(field_type, Serializable):"
new = "if isinstance(field_type, type) and issubclass(field_type, Serializable):"

if old not in s:
    raise SystemExit(f\"Expected pattern not found in {p}\")

p.write_text(s.replace(old, new), encoding="utf-8")
print(f\"Patched {p}\")
PY

# Expose the container ports
EXPOSE 8020

# Run xtts_api_server when the container starts
CMD ["bash", "-c", "python3 -m xtts_api_server --listen -p 8020 -t 'http://localhost:8020' -sf 'xtts-server/speakers' -o 'xtts-server/output' -mf 'xtts-server/models' --deepspeed"]
