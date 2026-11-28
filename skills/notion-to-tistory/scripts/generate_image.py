"""Gemini API로 블로그 썸네일·삽화를 생성한다. 표준 라이브러리만 사용."""

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash-image:generateContent"
)
KEYCHAIN_SERVICE = "GEMINI_API_KEY"


def get_api_key() -> str:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        result = None
    key = result.stdout.strip() if result and result.returncode == 0 else ""
    if not key:
        print(
            "Keychain에 유효한 GEMINI_API_KEY가 없습니다.\n"
            "1. https://aistudio.google.com/apikey 에서 키를 발급하세요.\n"
            "2. 다음 명령으로 등록하세요 (키는 입력 프롬프트에 붙여넣기):\n"
            "   security add-generic-password -s GEMINI_API_KEY -a gemini -w",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return key


def build_request(prompt: str, aspect: str) -> dict:
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect},
        },
    }


def extract_image_bytes(response: dict) -> bytes:
    texts = []
    for candidate in response.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
            if part.get("text"):
                texts.append(part["text"])
    reason = response.get("promptFeedback", {}).get("blockReason", "")
    detail = reason or " ".join(texts) or "원인 불명"
    print(f"응답에 이미지가 없습니다(차단/텍스트만 반환): {detail}", file=sys.stderr)
    raise SystemExit(3)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Gemini 이미지 생성")
    parser.add_argument("--prompt", required=True, help="이미지 설명")
    parser.add_argument("--out", required=True, help="출력 PNG 경로")
    parser.add_argument("--aspect", default="16:9", choices=["16:9", "1:1", "4:3"])
    args = parser.parse_args(argv)

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(build_request(args.prompt, args.aspect)).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": get_api_key()},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.load(response)
    except urllib.error.HTTPError as e:
        hint = {400: "요청 오류(프롬프트 확인)", 403: "키 권한/만료 확인", 429: "쿼터 초과"}.get(
            e.code, ""
        )
        print(f"Gemini API 오류 HTTP {e.code} {e.reason} {hint}".strip(), file=sys.stderr)
        raise SystemExit(4)
    except urllib.error.URLError as e:
        print(f"Gemini API 연결 실패(네트워크·타임아웃): {e.reason}", file=sys.stderr)
        raise SystemExit(4)

    image = extract_image_bytes(body)
    parent = os.path.dirname(args.out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(image)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
