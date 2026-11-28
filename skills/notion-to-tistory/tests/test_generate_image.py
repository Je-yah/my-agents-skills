import io
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_image


class FakeResp(io.BytesIO):
    def __init__(self, data, content_type="image/jpeg"):
        super().__init__(data)
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_build_image_url_encodes_prompt_and_16_9():
    url = generate_image.build_image_url("blue robot", "16:9")
    assert url.startswith("https://image.pollinations.ai/prompt/")
    assert "blue%20robot" in url
    assert "width=1280" in url and "height=720" in url
    assert "nologo=true" in url


def test_build_image_url_square_and_4_3():
    assert "width=1024&height=1024" in generate_image.build_image_url("x", "1:1")
    u = generate_image.build_image_url("x", "4:3")
    assert "width=1024" in u and "height=768" in u


def test_fetch_image_returns_bytes(monkeypatch):
    monkeypatch.setattr(generate_image.urllib.request, "urlopen",
                        lambda *a, **k: FakeResp(b"img-bytes", "image/jpeg"))
    assert generate_image.fetch_image("https://x") == b"img-bytes"


def test_fetch_image_non_image_exits_3(monkeypatch):
    monkeypatch.setattr(generate_image.urllib.request, "urlopen",
                        lambda *a, **k: FakeResp(b"<html>err</html>", "text/html"))
    with pytest.raises(SystemExit) as e:
        generate_image.fetch_image("https://x")
    assert e.value.code == 3


def test_fetch_image_http_error_exits_4(monkeypatch):
    def _raise(*a, **k):
        raise urllib.error.HTTPError("u", 500, "err", {}, io.BytesIO(b""))
    monkeypatch.setattr(generate_image.urllib.request, "urlopen", _raise)
    with pytest.raises(SystemExit) as e:
        generate_image.fetch_image("https://x")
    assert e.value.code == 4


def test_fetch_image_url_error_exits_4(monkeypatch):
    def _raise(*a, **k):
        raise urllib.error.URLError("timeout")
    monkeypatch.setattr(generate_image.urllib.request, "urlopen", _raise)
    with pytest.raises(SystemExit) as e:
        generate_image.fetch_image("https://x")
    assert e.value.code == 4


def test_main_writes_file(tmp_path, monkeypatch):
    out = tmp_path / "t.png"
    monkeypatch.setattr(generate_image, "fetch_image", lambda url: b"img-bytes")
    assert generate_image.main(["--prompt", "로봇", "--out", str(out)]) == 0
    assert out.read_bytes() == b"img-bytes"


def test_main_creates_parent_dir(tmp_path, monkeypatch):
    out = tmp_path / "nested" / "images" / "01.png"
    monkeypatch.setattr(generate_image, "fetch_image", lambda url: b"img-bytes")
    assert generate_image.main(["--prompt", "x", "--out", str(out), "--aspect", "4:3"]) == 0
    assert out.read_bytes() == b"img-bytes"
