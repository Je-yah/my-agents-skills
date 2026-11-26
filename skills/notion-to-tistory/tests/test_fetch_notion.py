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


def test_rich_text_plain():
    assert fetch_notion.rich_text([["abc"]]) == ("abc", False)


def test_rich_text_gray():
    text, gray = fetch_notion.rich_text([["note", [["h", "gray"]]]])
    assert text == "note" and gray is True


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


def test_main_outputs_json(monkeypatch, capsys):
    # 실제 API는 root 블록을 페이지 UUID로 키한다 → main이 그 UUID를 root_id로 사용.
    pid = "41fea2e0-bab9-8080-bd35-d3c700e4212c"
    fixture = {"recordMap": {"block": {
        pid: _blk({"id": pid, "type": "page",
                   "properties": {"title": [["My Talk"]]}, "content": ["b3"]}),
        "b3": _blk({"id": "b3", "type": "text",
                    "properties": {"title": [["private note", [["h", "gray"]]]]}}),
    }}}
    monkeypatch.setattr(fetch_notion, "fetch_chunk", lambda p: fixture)
    rc = fetch_notion.main(["--url", "https://foo.notion.site/t-41fea2e0bab98080bd35d3c700e4212c"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "My Talk"
    assert any(b["gray"] for b in data["blocks"])
