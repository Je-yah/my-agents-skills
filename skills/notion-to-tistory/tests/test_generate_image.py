import io
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_image

# 유효한 JPEG 매직바이트로 시작하는 샘플
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


class FakeResp(io.BytesIO):
    def __init__(self, data, content_type="image/jpeg"):
        super().__init__(data)
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _resp(data, ctype="image/jpeg"):
    return lambda *a, **k: FakeResp(data, ctype)


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
    monkeypatch.setattr(generate_image.urllib.request, "urlopen", _resp(JPEG))
    assert generate_image.fetch_image("https://x") == JPEG


def test_fetch_image_non_image_content_type_exits_3(monkeypatch):
    monkeypatch.setattr(generate_image.urllib.request, "urlopen", _resp(b"<html>err</html>", "text/html"))
    with pytest.raises(SystemExit) as e:
        generate_image.fetch_image("https://x")
    assert e.value.code == 3


def test_fetch_image_empty_bytes_exits_3(monkeypatch):
    # C1: 빈 바이트 + image Content-Type → 깨진 파일 저장 방지
    monkeypatch.setattr(generate_image.urllib.request, "urlopen", _resp(b"", "image/jpeg"))
    with pytest.raises(SystemExit) as e:
        generate_image.fetch_image("https://x")
    assert e.value.code == 3


def test_fetch_image_fake_image_bytes_exits_3(monkeypatch):
    # C2: image Content-Type이지만 매직바이트가 아니면 거부
    monkeypatch.setattr(generate_image.urllib.request, "urlopen", _resp(b"<html>loading</html>", "image/jpeg"))
    with pytest.raises(SystemExit) as e:
        generate_image.fetch_image("https://x")
    assert e.value.code == 3


def test_fetch_image_too_large_exits_3(monkeypatch):
    # W1: 상한 초과 응답 거부
    monkeypatch.setattr(generate_image, "MAX_BYTES", 16)
    monkeypatch.setattr(generate_image.urllib.request, "urlopen", _resp(JPEG + b"\x00" * 64))
    with pytest.raises(SystemExit) as e:
        generate_image.fetch_image("https://x")
    assert e.value.code == 3


def test_fetch_image_402_rate_limit_waits_and_retries(monkeypatch):
    calls = {"n": 0}
    slept = {"s": 0}

    def fake_urlopen(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            body = b'{"error":{"code":"FREE_LIMIT","message":"Free limit reached. Retry after 3s"}}'
            raise urllib.error.HTTPError("u", 402, "Payment Required", {}, io.BytesIO(body))
        return FakeResp(JPEG, "image/jpeg")

    monkeypatch.setattr(generate_image.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(generate_image.time, "sleep", lambda s: slept.__setitem__("s", s))
    assert generate_image.fetch_image("https://x") == JPEG
    assert calls["n"] == 2
    assert slept["s"] >= 3


def test_fetch_image_402_persists_exits_4(monkeypatch):
    def always_402(*a, **k):
        raise urllib.error.HTTPError(
            "u", 402, "Payment Required", {}, io.BytesIO(b'{"error":{"message":"Retry after 1s"}}'))
    monkeypatch.setattr(generate_image.urllib.request, "urlopen", always_402)
    monkeypatch.setattr(generate_image.time, "sleep", lambda s: None)
    with pytest.raises(SystemExit) as e:
        generate_image.fetch_image("https://x")
    assert e.value.code == 4


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
    monkeypatch.setattr(generate_image, "fetch_image", lambda url: JPEG)
    assert generate_image.main(["--prompt", "로봇", "--out", str(out)]) == 0
    assert out.read_bytes() == JPEG


def test_main_creates_parent_dir(tmp_path, monkeypatch):
    out = tmp_path / "nested" / "images" / "01.png"
    monkeypatch.setattr(generate_image, "fetch_image", lambda url: JPEG)
    assert generate_image.main(["--prompt", "x", "--out", str(out), "--aspect", "4:3"]) == 0
    assert out.read_bytes() == JPEG
