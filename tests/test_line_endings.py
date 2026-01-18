from __future__ import annotations

from pathlib import Path


def test_start_sh_has_unix_shebang_and_no_bom() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    start_sh = repo_root / "src" / "start.sh"
    content = start_sh.read_bytes()

    assert not content.startswith(b"\xef\xbb\xbf"), "start.sh must not start with a UTF-8 BOM"
    assert content.startswith(b"#!/bin/bash\n"), "start.sh must start with a valid bash shebang"
    assert b"\r" not in content, "start.sh must not contain CRLF/CR line endings"
