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
import re
import coqpit.coqpit as coqpit_module

p = pathlib.Path(coqpit_module.__file__)
s = p.read_text(encoding="utf-8")

pattern = r"if\s+issubclass\(field_type,\s*Serializable\):"
replacement = "if isinstance(field_type, type) and issubclass(field_type, Serializable):"

patched, count = re.subn(pattern, replacement, s)
s = patched
count_total = count

union_pattern = r"""def is_union\(arg_type: Any\) -> bool:\n(?:    .*\n)+?        return False\n"""
union_replacement = """def is_union(arg_type: Any) -> bool:
    \"\"\"Check if the input type is `Union` (supports typing.Union and PEP 604 `A | B`).\"\"\"
    import types
    from typing import get_origin

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
        return safe_issubclass(arg_type.__origin__, Union)
    except AttributeError:
        return False
"""
patched2, count2 = re.subn(union_pattern, union_replacement, s, flags=re.MULTILINE)
s = patched2
count_total += count2

if count_total > 0:
    p.write_text(s, encoding="utf-8")
    print(f"Patched {p} ({count_total} total replacement(s))")
else:
    print(f"No patch needed in {p} (already patched or code changed)")
PY

# Expose the container ports
EXPOSE 8020

# Run xtts_api_server when the container starts
CMD ["bash", "-c", "python3 -m xtts_api_server --listen -p 8020 -t 'http://localhost:8020' -sf 'xtts-server/speakers' -o 'xtts-server/output' -mf 'xtts-server/models' --deepspeed"]
