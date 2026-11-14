"""Gemini API로 블로그 썸네일·삽화를 생성한다. 표준 라이브러리만 사용."""

import argparse
import base64
import json
import subprocess
import sys
import urllib.request

API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash-image:generateContent"
)
KEYCHAIN_SERVICE = "GEMINI_API_KEY"


def get_api_key() -> str:
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            "Keychain에 GEMINI_API_KEY가 없습니다.\n"
            "1. https://aistudio.google.com/apikey 에서 키를 발급하세요.\n"
            "2. 다음 명령으로 등록하세요 (키는 입력 프롬프트에 붙여넣기):\n"
            "   security add-generic-password -s GEMINI_API_KEY -a gemini -w",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return result.stdout.strip()


def build_request(prompt: str, aspect: str) -> dict:
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect},
        },
    }


def extract_image_bytes(response: dict) -> bytes:
    for candidate in response.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    print("응답에 이미지가 없습니다(세이프티 차단 또는 텍스트만 반환).", file=sys.stderr)
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
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.load(response)

    image = extract_image_bytes(body)
    with open(args.out, "wb") as f:
        f.write(image)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
