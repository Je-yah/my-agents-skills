"""Pollinations.ai(무료, 키 불필요)로 블로그 썸네일·삽화를 생성한다. 표준 라이브러리만 사용.

무료 커뮤니티 서비스라 키·결제가 필요 없다. 품질을 더 원하면 fetch_image의
엔드포인트만 다른 제공자(예: Hugging Face)로 교체하면 된다.
"""

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://image.pollinations.ai/prompt/"
# 종횡비 → (width, height). Pollinations가 환경에 따라 근사 조정할 수 있으나 비율은 유지된다.
ASPECT = {"16:9": (1280, 720), "1:1": (1024, 1024), "4:3": (1024, 768)}


def build_image_url(prompt: str, aspect: str) -> str:
    w, h = ASPECT[aspect]
    path = urllib.parse.quote(prompt, safe="")
    return f"{BASE}{path}?width={w}&height={h}&nologo=true"


def fetch_image(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:
            ctype = resp.headers.get("Content-Type", "")
            data = resp.read()
    except urllib.error.HTTPError as e:
        print(f"이미지 생성 API 오류 HTTP {e.code} {e.reason}", file=sys.stderr)
        raise SystemExit(4)
    except urllib.error.URLError as e:
        print(f"이미지 생성 API 연결 실패(네트워크·타임아웃): {e.reason}", file=sys.stderr)
        raise SystemExit(4)
    if not ctype.startswith("image/"):
        print(f"이미지가 반환되지 않았습니다(Content-Type: {ctype or '없음'}).", file=sys.stderr)
        raise SystemExit(3)
    return data


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="Pollinations 이미지 생성")
    parser.add_argument("--prompt", required=True, help="이미지 설명(영문 권장)")
    parser.add_argument("--out", required=True, help="출력 이미지 경로")
    parser.add_argument("--aspect", default="16:9", choices=list(ASPECT))
    args = parser.parse_args(argv)

    image = fetch_image(build_image_url(args.prompt, args.aspect))
    parent = os.path.dirname(args.out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(image)
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
