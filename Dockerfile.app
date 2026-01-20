# Thin app image for ComfyUI RunPod serverless worker
# Builds quickly when only worker code/workflows/schemas change.

ARG BASE_IMAGE
FROM ${BASE_IMAGE} AS production

WORKDIR /comfyui

COPY src /src

RUN python - <<'PY'
from pathlib import Path

p = Path("/src/start.sh")
b = p.read_bytes()

if b.startswith(b"\xef\xbb\xbf"):
    b = b[3:]

b = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
p.write_bytes(b)
PY

COPY schemas /schemas
COPY workflows /workflows

COPY requirements.txt /src/requirements.txt
RUN pip install -r /src/requirements.txt

RUN chmod +x /src/start.sh

CMD ["/src/start.sh"]
