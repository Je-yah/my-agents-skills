"""공개 Notion 페이지를 비공식 REST API(loadPageChunk)로 읽는다. 표준 라이브러리만 사용.

MCP 연결 없이 공개(published) notion.site 페이지를 읽기 위한 메인 경로.
비공개 페이지는 이 경로로 읽을 수 없으므로 SKILL.md가 MCP 폴백을 안내한다.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

API_URL = "https://www.notion.so/api/v3/loadPageChunk"
HEX32 = re.compile(r"[0-9a-fA-F]{32}")


def extract_page_id(url_or_id: str) -> str:
    """URL·슬러그·raw hex·대시 UUID에서 32-hex 페이지 ID를 뽑아 대시 UUID로 반환."""
    s = url_or_id.split("?")[0].split("#")[0]
    compact = s.replace("-", "")
    m = None
    for m in HEX32.finditer(compact):
        pass  # 마지막 매치 사용(슬러그 뒤 ID)
    if not m:
        print("노션 페이지 ID를 찾을 수 없습니다. 게시 링크를 확인하세요.", file=sys.stderr)
        raise SystemExit(2)
    h = m.group(0).lower()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def rich_text(title_prop) -> tuple:
    """Notion rich text 배열 → (plain text, 회색 여부)."""
    if not title_prop:
        return "", False
    parts, gray = [], False
    for run in title_prop:
        parts.append(run[0])
        anns = run[1] if len(run) > 1 else []
        for a in anns:
            if a and a[0] == "h" and "gray" in str(a[1]):
                gray = True
    return "".join(parts), gray


def _block_value(record_block: dict, bid: str):
    entry = record_block.get(bid)
    if not entry:
        return None
    return entry.get("value", {}).get("value")


def parse_record_map(data: dict, root_id: str) -> dict:
    record_block = data.get("recordMap", {}).get("block", {})
    root = _block_value(record_block, root_id)
    if not root:
        print(
            "페이지를 읽을 수 없습니다. 공개(published)된 페이지가 아니거나 접근할 수 없습니다.\n"
            "노션에서 페이지를 '웹에 게시'했는지 확인하거나, 비공개 페이지는 Notion MCP로 읽으세요.",
            file=sys.stderr,
        )
        raise SystemExit(3)

    title, _ = rich_text(root.get("properties", {}).get("title"))
    blocks, images = [], []

    def walk(bid, depth):
        b = _block_value(record_block, bid)
        if not b:
            return
        btype = b.get("type", "")
        fmt = b.get("format", {}) or {}
        if btype == "image":
            src = fmt.get("display_source") or fmt.get("source")
            if src:
                images.append(src)
        text, inline_gray = rich_text(b.get("properties", {}).get("title"))
        gray = inline_gray or ("gray" in str(fmt.get("block_color", "")))
        if text.strip():
            blocks.append({"type": btype, "text": text, "gray": gray, "depth": depth})
        for cid in b.get("content", []):
            walk(cid, depth + 1)

    for cid in root.get("content", []):
        walk(cid, 0)

    return {"title": title, "blocks": blocks, "images": images}


def fetch_chunk(page_id: str) -> dict:
    body = json.dumps({
        "pageId": page_id, "limit": 100,
        "cursor": {"stack": []}, "chunkNumber": 0, "verticalColumns": False,
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"Notion API 오류 HTTP {e.code} {e.reason}", file=sys.stderr)
        raise SystemExit(4)
    except urllib.error.URLError as e:
        print(f"Notion API 연결 실패: {e.reason}", file=sys.stderr)
        raise SystemExit(4)


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="공개 Notion 페이지 읽기")
    parser.add_argument("--url", required=True, help="노션 게시 링크 또는 페이지 ID")
    parser.add_argument("--out", help="JSON 출력 경로(생략 시 stdout)")
    args = parser.parse_args(argv)

    page_id = extract_page_id(args.url)
    data = fetch_chunk(page_id)
    result = parse_record_map(data, page_id)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
