import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import fetch_notion


def _blk(block):
    return {"value": {"value": block}}


FIXTURE = {
    "recordMap": {
        "block": {
            "root": _blk({
                "id": "root", "type": "page",
                "properties": {"title": [["My Talk"]]},
                "content": ["b1", "b2", "b3", "img1"],
            }),
            "b1": _blk({"id": "b1", "type": "text", "properties": {"title": [["Hello world"]]}}),
            "b2": _blk({"id": "b2", "type": "bulleted_list", "properties": {"title": [["A point"]]}}),
            "b3": _blk({"id": "b3", "type": "text",
                        "properties": {"title": [["private note", [["h", "gray"]]]]}}),
            "img1": _blk({"id": "img1", "type": "image",
                          "format": {"display_source": "https://img.example/x.png"}}),
        }
    }
}


def test_extract_page_id_from_url():
    url = "https://foo.notion.site/261121-AI-41fea2e0bab98080bd35d3c700e4212c?source=copy_link"
    assert fetch_notion.extract_page_id(url) == "41fea2e0-bab9-8080-bd35-d3c700e4212c"


def test_extract_page_id_raw_hex():
    assert fetch_notion.extract_page_id("41fea2e0bab98080bd35d3c700e4212c") == "41fea2e0-bab9-8080-bd35-d3c700e4212c"


def test_extract_page_id_already_dashed():
    u = "41fea2e0-bab9-8080-bd35-d3c700e4212c"
    assert fetch_notion.extract_page_id(u) == u


def test_extract_page_id_invalid():
    with pytest.raises(SystemExit) as e:
        fetch_notion.extract_page_id("https://foo.notion.site/no-id-here")
    assert e.value.code == 2


def test_extract_page_id_hex_in_host_slug():
    # C1: 호스트/슬러그에 hex가 섞여도 마지막 경로 세그먼트의 32-hex만 써야 한다
    url = ("https://abcdef0123456789abcdef0123456789-team.notion.site/"
           "Page-41fea2e0bab98080bd35d3c700e4212c")
    assert fetch_notion.extract_page_id(url) == "41fea2e0-bab9-8080-bd35-d3c700e4212c"


def test_rich_text_plain():
    assert fetch_notion.rich_text([["abc"]]) == ("abc", False)


def test_rich_text_gray():
    text, gray = fetch_notion.rich_text([["note", [["h", "gray"]]]])
    assert text == "note" and gray is True


def test_rich_text_non_gray_color_not_flagged():
    # N3: "bluegray" 같은 유사 문자열을 회색으로 오탐하면 안 된다
    _, gray = fetch_notion.rich_text([["x", [["h", "blue"]]]])
    assert gray is False


def test_parse_record_map_blocks_ordered_with_gray():
    out = fetch_notion.parse_record_map(FIXTURE, "root")
    assert out["title"] == "My Talk"
    texts = [(b["text"], b["gray"]) for b in out["blocks"]]
    assert texts == [("Hello world", False), ("A point", False), ("private note", True)]


def test_parse_record_map_image_url():
    out = fetch_notion.parse_record_map(FIXTURE, "root")
    assert out["images"] == ["https://img.example/x.png"]


def test_parse_record_map_missing_root_exits_3():
    with pytest.raises(SystemExit) as e:
        fetch_notion.parse_record_map({"recordMap": {"block": {}}}, "root")
    assert e.value.code == 3


def test_parse_image_scheme_whitelist():
    # W2: https만 허용, http/data/file은 제외 (curl SSRF 표면 차단)
    data = {"recordMap": {"block": {
        "root": _blk({"id": "root", "type": "page",
                      "properties": {"title": [["T"]]}, "content": ["i1", "i2", "i3"]}),
        "i1": _blk({"id": "i1", "type": "image", "format": {"display_source": "http://insecure/a.png"}}),
        "i2": _blk({"id": "i2", "type": "image", "format": {"display_source": "https://ok/b.png"}}),
        "i3": _blk({"id": "i3", "type": "image", "format": {"display_source": "file:///etc/passwd"}}),
    }}}
    out = fetch_notion.parse_record_map(data, "root")
    assert out["images"] == ["https://ok/b.png"]


def test_parse_record_map_cycle_no_recursion():
    # C2: content 순환참조가 있어도 RecursionError 없이 유한 종료
    data = {"recordMap": {"block": {
        "root": _blk({"id": "root", "type": "page",
                      "properties": {"title": [["T"]]}, "content": ["a"]}),
        "a": _blk({"id": "a", "type": "text", "properties": {"title": [["A"]]}, "content": ["b"]}),
        "b": _blk({"id": "b", "type": "text", "properties": {"title": [["B"]]}, "content": ["a"]}),
    }}}
    out = fetch_notion.parse_record_map(data, "root")
    texts = [b["text"] for b in out["blocks"]]
    assert texts == ["A", "B"]  # 각 블록 1회만 방문


def test_parse_record_map_truncated_flag_on_missing_cid():
    # C3: content가 가리키는 cid가 블록맵에 없으면 truncated=True로 유실을 알림
    data = {"recordMap": {"block": {
        "root": _blk({"id": "root", "type": "page",
                      "properties": {"title": [["T"]]}, "content": ["a", "missing"]}),
        "a": _blk({"id": "a", "type": "text", "properties": {"title": [["A"]]}}),
    }}}
    out = fetch_notion.parse_record_map(data, "root")
    assert out["truncated"] is True


def test_fetch_page_merges_chunks(monkeypatch):
    # C3: cursor가 남아있으면 다음 청크까지 가져와 병합
    chunk0 = {"recordMap": {"block": {"a": _blk({"id": "a", "type": "text"})}},
              "cursor": {"stack": [[{"table": "block", "id": "x", "index": 0}]]}}
    chunk1 = {"recordMap": {"block": {"b": _blk({"id": "b", "type": "text"})}},
              "cursor": {"stack": []}}
    seq = [chunk0, chunk1]
    monkeypatch.setattr(fetch_notion, "fetch_chunk", lambda pid, cur, n: seq[n])
    merged = fetch_notion.fetch_page("pid")
    blocks = merged["recordMap"]["block"]
    assert set(blocks) == {"a", "b"}


def test_main_outputs_json(monkeypatch, capsys):
    # 실제 API는 root 블록을 페이지 UUID로 키한다 → main이 그 UUID를 root_id로 사용.
    pid = "41fea2e0-bab9-8080-bd35-d3c700e4212c"
    fixture = {"recordMap": {"block": {
        pid: _blk({"id": pid, "type": "page",
                   "properties": {"title": [["My Talk"]]}, "content": ["b3"]}),
        "b3": _blk({"id": "b3", "type": "text",
                    "properties": {"title": [["private note", [["h", "gray"]]]]}}),
    }}}
    monkeypatch.setattr(fetch_notion, "fetch_page", lambda p: fixture)
    rc = fetch_notion.main(["--url", "https://foo.notion.site/t-41fea2e0bab98080bd35d3c700e4212c"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "My Talk"
    assert any(b["gray"] for b in data["blocks"])
