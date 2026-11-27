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
DASHED_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
# 앞뒤가 hex가 아닌 '경계 있는' 32-hex만 매칭(슬러그/호스트의 더 긴 hex 런을 ID로 오인하지 않도록)
BOUNDED_HEX32 = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])")
GRAY_COLORS = {"gray", "gray_background"}
MAX_CHUNKS = 50  # 청크당 100블록 → 최대 5000블록


def extract_page_id(url_or_id: str) -> str:
    """URL·슬러그·raw hex·대시 UUID에서 32-hex 페이지 ID를 뽑아 대시 UUID로 반환.

    URL은 **마지막 경로 세그먼트**에서만 ID를 찾는다(호스트/슬러그의 우연한 hex 배제).
    """
    s = url_or_id.split("?")[0].split("#")[0].rstrip("/")
    segment = s.rsplit("/", 1)[-1]
    m = DASHED_UUID.search(segment)
    if m:
        return m.group(0).lower()
    hits = BOUNDED_HEX32.findall(segment)
    if hits:
        h = hits[-1].lower()
        return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
    print("노션 페이지 ID를 찾을 수 없습니다. 게시 링크를 확인하세요.", file=sys.stderr)
    raise SystemExit(2)


def rich_text(title_prop) -> tuple:
    """Notion rich text 배열 → (plain text, 회색 여부)."""
    if not title_prop:
        return "", False
    parts, gray = [], False
    for run in title_prop:
        if not run:  # 빈 run([]) 방어
            continue
        parts.append(run[0])
        anns = run[1] if len(run) > 1 else []
        for a in anns:
            if a and a[0] == "h" and a[1] in GRAY_COLORS:
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
    visited = set()
    missing = [0]

    def walk(bid, depth):
        if bid in visited:  # C2: 순환참조 가드
            return
        visited.add(bid)
        b = _block_value(record_block, bid)
        if not b:
            missing[0] += 1  # C3: content가 가리키나 블록맵에 없는 자식 → 유실
            return
        btype = b.get("type", "")
        fmt = b.get("format", {}) or {}
        if btype == "image":
            src = fmt.get("display_source") or fmt.get("source")
            if src and str(src).startswith("https://"):  # W2: https만 허용
                images.append(src)
        text, inline_gray = rich_text(b.get("properties", {}).get("title"))
        gray = inline_gray or (fmt.get("block_color") in GRAY_COLORS)
        if text.strip():
            blocks.append({"type": btype, "text": text, "gray": gray, "depth": depth})
        for cid in b.get("content", []):
            walk(cid, depth + 1)

    for cid in root.get("content", []):
        walk(cid, 0)

    return {"title": title, "blocks": blocks, "images": images, "truncated": missing[0] > 0}


def fetch_chunk(page_id: str, cursor: dict, chunk_number: int) -> dict:
    body = json.dumps({
        "pageId": page_id, "limit": 100,
        "cursor": cursor, "chunkNumber": chunk_number, "verticalColumns": False,
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


def fetch_page(page_id: str) -> dict:
    """C3: cursor가 남아있는 동안 청크를 모두 가져와 recordMap.block을 병합."""
    merged = {}
    cursor = {"stack": []}
    capped = True  # break로 끝나면 False, 상한 소진 시 True 유지
    for chunk_number in range(MAX_CHUNKS):
        data = fetch_chunk(page_id, cursor, chunk_number)
        merged.update(data.get("recordMap", {}).get("block", {}))
        cursor = data.get("cursor") or {"stack": []}
        if not cursor.get("stack"):
            capped = False
            break
    return {"recordMap": {"block": merged}, "chunk_capped": capped}


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="공개 Notion 페이지 읽기")
    parser.add_argument("--url", required=True, help="노션 게시 링크 또는 페이지 ID")
    parser.add_argument("--out", help="JSON 출력 경로(생략 시 stdout)")
    args = parser.parse_args(argv)

    page_id = extract_page_id(args.url)
    data = fetch_page(page_id)
    result = parse_record_map(data, page_id)
    result["truncated"] = result["truncated"] or data.get("chunk_capped", False)
    if result["truncated"]:
        print("경고: 일부 블록을 가져오지 못했습니다(페이지 뒷부분 유실 가능).", file=sys.stderr)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
