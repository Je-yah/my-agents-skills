import base64
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_image


def _completed(returncode, stdout=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_get_api_key_missing(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(44))
    with pytest.raises(SystemExit) as e:
        generate_image.get_api_key()
    assert e.value.code == 2


def test_get_api_key_found(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(0, "test-key\n"))
    assert generate_image.get_api_key() == "test-key"


def test_build_request_contains_prompt_and_aspect():
    req = generate_image.build_request("로봇 삽화", "16:9")
    assert req["contents"][0]["parts"][0]["text"] == "로봇 삽화"
    assert req["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"


def test_extract_image_bytes_ok():
    data = base64.b64encode(b"png-bytes").decode()
    resp = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": data}}]}}]}
    assert generate_image.extract_image_bytes(resp) == b"png-bytes"


def test_extract_image_bytes_no_image():
    resp = {"candidates": [{"content": {"parts": [{"text": "죄송합니다"}]}}]}
    with pytest.raises(SystemExit) as e:
        generate_image.extract_image_bytes(resp)
    assert e.value.code == 3


def test_main_writes_file(tmp_path, monkeypatch):
    out = tmp_path / "thumb.png"
    data = base64.b64encode(b"png-bytes").decode()
    body = json.dumps(
        {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": data}}]}}]}
    ).encode()
    monkeypatch.setattr(generate_image, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(
        generate_image.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(body)
    )
    assert generate_image.main(["--prompt", "로봇 삽화", "--out", str(out)]) == 0
    assert out.read_bytes() == b"png-bytes"
