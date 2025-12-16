from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

from PIL import Image


def main() -> None:
    input_path = Path("./qwen-output.json")
    output_path = Path("./qwen-output.jpg")

    payload = json.loads(input_path.read_text(encoding="utf-8"))

    b64_data = payload["output"]["output"]["images"][0]["data"]
    img_bytes = base64.b64decode(b64_data)

    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    img.save(output_path, format="JPEG", quality=95)

    print(f"Saved: {output_path.resolve()}")


if __name__ == "__main__":
    main()