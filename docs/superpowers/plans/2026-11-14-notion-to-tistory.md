# notion-to-tistory 스킬 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 노션 게시 링크를 받아 분류·요약·이미지 생성 후 티스토리 붙여넣기용 게시 패키지를 만드는 Claude Code 스킬 구축

**Architecture:** 단일 스킬(`~/.skills/skills/notion-to-tistory/`)이 파이프라인(노션 읽기 → 분류 → 초안 → 사용자 승인 → 이미지 생성 → 패키지 출력)을 오케스트레이션한다. 노션 읽기는 Notion MCP, 이미지 생성은 stdlib 전용 Python 스크립트가 Gemini REST API를 호출한다. 분류·문체 기준은 references 문서로 분리한다.

**Tech Stack:** Claude Code 스킬(SKILL.md), Python 3.13 표준 라이브러리만(urllib, subprocess, base64, argparse), Gemini API(`gemini-2.5-flash-image`, REST), macOS Keychain(`security`), Notion MCP(`notion-fetch`), pytest

**Spec:** `docs/superpowers/specs/2026-11-14-notion-to-tistory-design.md`

## Global Constraints

- 모든 산출물(SKILL.md, references, 블로그 초안)은 한국어
- API 키는 Keychain 서비스명 `GEMINI_API_KEY`에서만 조회, plaintext 저장·커밋 금지
- Python 스크립트는 외부 패키지 설치 없이 표준 라이브러리만 사용
- 게시 패키지 출력 루트는 `~/Documents/BlogPackages/<YYYY-MM-DD>-<slug>/`, 기존 폴더 덮어쓰기 금지(중복 시 `-2` suffix)
- 카테고리는 기존 4개(`Devlog`/`회고`/`Paper Review`/`CS`)만 사용, 신설 금지
- Claude Code 전용(다른 harness 지원 없음), 티스토리 자동 게시 없음
- SKILL.md 트리거 조건은 frontmatter가 아닌 본문 "When to Use This" 섹션에 작성
- 작업 브랜치 `feat/notion-to-tistory` (main에서 분기), 태스크마다 커밋

## Review Focus

1. 노션 페이지가 비어 있거나 이미지뿐일 때 — 초안을 지어내지 않고 중단·안내해야 한다 → Task 4 Step 2 체크리스트
2. Gemini 응답에 이미지 파트가 없을 때(세이프티 차단, 텍스트만 반환) — 스크립트가 빈 파일을 쓰지 않고 명확히 실패해야 한다 → Task 2 Step 1 `test_extract_image_bytes_no_image`
3. Keychain에 키가 없을 때 — 등록 안내 메시지와 함께 중단해야 한다 → Task 2 Step 1 `test_get_api_key_missing`
4. 같은 글을 같은 날 재실행할 때 — 기존 패키지를 덮어쓰지 않아야 한다 → Task 4 Step 2 체크리스트(slug 중복 규칙)
5. 노션 원본 이미지 다운로드 실패 시 — 생성 삽화로 몰래 대체하지 않고 위치만 표시하고 사용자에게 알려야 한다 → Task 4 Step 2 체크리스트

---

### Task 1: 브랜치 준비와 설계 문서 커밋

**Files:**
- Modify: `~/.skills` 저장소 (브랜치 생성)
- 포함: `docs/superpowers/specs/2026-11-14-notion-to-tistory-design.md`, `docs/superpowers/plans/2026-11-14-notion-to-tistory.md` (현재 untracked)

**Interfaces:**
- Produces: `feat/notion-to-tistory` 브랜치 — 이후 모든 태스크가 이 브랜치에서 작업

- [ ] **Step 1: main 기준 브랜치 생성**

Run: `git -C ~/.skills stash --include-untracked --keep-index 2>/dev/null; git -C ~/.skills fetch origin && git -C ~/.skills switch -c feat/notion-to-tistory origin/main`
주의: 현재 체크아웃은 `chore/branch-completion-verification` 브랜치이며 untracked `skills/dev-workflow-setup/`가 있다. 해당 untracked 파일은 건드리지 않는다(스펙·플랜 문서 2개만 이번 작업 대상). stash가 스펙·플랜을 삼켰다면 pop으로 복원한다.

- [ ] **Step 2: 설계·계획 문서 커밋**

```bash
git -C ~/.skills add docs/superpowers/specs/2026-11-14-notion-to-tistory-design.md docs/superpowers/plans/2026-11-14-notion-to-tistory.md
git -C ~/.skills commit -m "docs: notion-to-tistory 스킬 설계·구현 계획 추가"
```

- [ ] **Step 3: 상태 확인**

Run: `git -C ~/.skills status --short --branch`
Expected: `## feat/notion-to-tistory` 이고 스펙·플랜 외 변경 없음(기존 untracked 제외)

### Task 2: scripts/generate_image.py (TDD)

**Files:**
- Create: `skills/notion-to-tistory/scripts/generate_image.py`
- Test: `skills/notion-to-tistory/tests/test_generate_image.py`

**Interfaces:**
- Produces(CLI): `python3 scripts/generate_image.py --prompt "<이미지 설명>" --out <path.png> [--aspect 16:9|1:1|4:3]` — 성공 시 exit 0과 PNG 파일, 키 없음 exit 2, 이미지 미반환 exit 3
- Produces(함수): `get_api_key() -> str`, `build_request(prompt: str, aspect: str) -> dict`, `extract_image_bytes(response: dict) -> bytes`, `main(argv: list[str]) -> int`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_generate_image.py`:

```python
def test_get_api_key_missing(monkeypatch):
    # subprocess.run이 returncode 44(미존재)를 반환하도록 mock
    with pytest.raises(SystemExit) as e:
        generate_image.get_api_key()
    assert e.value.code == 2

def test_get_api_key_found(monkeypatch):
    # stdout "test-key\n" mock
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
    # get_api_key와 urllib.request.urlopen을 mock, --out 파일에 PNG 바이트가 써지는지 확인
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python3 -m pytest ~/.skills/skills/notion-to-tistory/tests/test_generate_image.py -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현**

`get_api_key`: `security find-generic-password -s GEMINI_API_KEY -w` 를 `subprocess.run`으로 호출, 실패 시 한국어 안내(발급 URL, `security add-generic-password -s GEMINI_API_KEY -a gemini -w` 등록 예시)를 stderr에 출력하고 exit 2.
`build_request`/HTTP: `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent`, 헤더 `x-goog-api-key`, urllib 사용. API 키를 로그·예외 메시지에 노출하지 않는다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m pytest ~/.skills/skills/notion-to-tistory/tests/test_generate_image.py -v`
Expected: 전체 PASS

- [ ] **Step 5: 커밋**

```bash
git -C ~/.skills add skills/notion-to-tistory/scripts/generate_image.py skills/notion-to-tistory/tests/test_generate_image.py
git -C ~/.skills commit -m "feat: notion-to-tistory 이미지 생성 스크립트 추가"
```

### Task 3: references/blog-profile.md (분류·문체 레퍼런스)

**Files:**
- Create: `skills/notion-to-tistory/references/blog-profile.md`

**Interfaces:**
- Produces: SKILL.md가 분류·집필 단계에서 읽는 단일 레퍼런스 문서

- [ ] **Step 1: 기존 블로그 글 수집**

WebFetch로 `https://mgs10204.tistory.com/` 및 최근 글 2~3편을 읽어 문체 특징(문장 길이, 어미, 코드블록·헤딩 사용 패턴), 제목 prefix 어휘, 태그 어휘를 추출한다.

- [ ] **Step 2: 문서 작성**

필수 섹션: `## 카테고리 분류 기준`(4개 카테고리 각각의 판정 기준과 예시 — Devlog=개발 과정, 회고=경험·배움, Paper Review=논문, CS=학습 정리), `## 제목 규칙`(prefix 어휘: `[Hackathon]` `[Project]` `[Conference]` `[Troubleshooting]` `[Toy Project]` 등 기존 관행 + 활동 유형 확장), `## 태그 어휘`(기술 분야: Agentic AI, AI Systems, Backend, Infra, Automation, Vision + 스택 태그 규칙), `## 문체 가이드`(Step 1에서 추출한 실제 특징), `## 패키지 형식`(post.md 구조 — 삽화 삽입 마커 `<!-- image: images/NN.png | <대체텍스트> -->` — 와 meta.md 필드 정의: 제목, 카테고리, 태그, 썸네일 설명)

- [ ] **Step 3: 검증**

Run: `grep -c '^## ' ~/.skills/skills/notion-to-tistory/references/blog-profile.md`
Expected: 5 (필수 섹션 모두 존재)

- [ ] **Step 4: 커밋**

```bash
git -C ~/.skills add skills/notion-to-tistory/references/blog-profile.md
git -C ~/.skills commit -m "feat: notion-to-tistory 블로그 프로필 레퍼런스 추가"
```

### Task 4: SKILL.md

**Files:**
- Create: `skills/notion-to-tistory/SKILL.md`

**Interfaces:**
- Consumes: Task 2 CLI(`generate_image.py` 사용법·exit code), Task 3 레퍼런스(`references/blog-profile.md`)

- [ ] **Step 1: SKILL.md 작성**

frontmatter: `name: notion-to-tistory`, `description`은 한 문장 요약만(트리거 나열 금지).
본문 필수 섹션:
- `## When to Use This` — 트리거: "노션 글 블로그로 옮겨줘", "활동 기록 티스토리에 정리해줘", 노션 게시 링크와 함께 블로그화 요청
- `## 사용법` — `/notion-to-tistory <노션 게시 링크>`
- `## 실행 파이프라인` — ① Notion MCP(`notion-fetch`)로 읽기 ② `references/blog-profile.md` 기준 분류(카테고리 1 + prefix + 태그 n) ③ 초안 집필(원본 사실 범위 내, 블로그 문체) ④ **승인 게이트**: 분류 결과+초안 전문을 보여주고 명시적 승인 후에만 이미지 단계 진행 ⑤ 썸네일 1장(16:9) + 본문 삽화 2~3장(섹션 수 따라 조정) `scripts/generate_image.py`로 생성 ⑥ 노션 원본 이미지는 다운로드해 `images/`에 우선 포함(생성 삽화는 보조), `~/Documents/BlogPackages/<YYYY-MM-DD>-<slug>/`에 post.md·meta.md·thumbnail.png·images/ 출력, 티스토리 에디터 붙여넣기 절차 안내
- `## 오류 처리` — Notion MCP 미연결: 연결 안내 후 중단 / 페이지 본문 없음·이미지 전용: 지어내지 않고 중단 / Keychain 키 없음(exit 2): 발급·등록 안내 / 이미지 미반환(exit 3): 해당 삽화 건너뛰고 보고 / slug 중복: `-2` suffix / 노션 원본 이미지 다운로드 실패: 마커만 남기고 사용자에게 보고(생성 삽화로 대체 금지)

- [ ] **Step 2: 체크리스트 검증**

본문에 다음이 모두 있는지 확인: 승인 게이트 명시, slug 중복 규칙, 빈 페이지 중단 규칙, 원본 이미지 실패 규칙, exit code 2/3 처리, "When to Use This" 섹션.
Run: `grep -E 'When to Use This|승인|slug|exit' ~/.skills/skills/notion-to-tistory/SKILL.md | head`
Expected: 각 항목 출력 존재

- [ ] **Step 3: 커밋**

```bash
git -C ~/.skills add skills/notion-to-tistory/SKILL.md
git -C ~/.skills commit -m "feat: notion-to-tistory 스킬 본문 추가"
```

### Task 5: adversarial-reviewer 2회 적용

**Files:**
- Modify: `skills/notion-to-tistory/` 전체 (리뷰 반영)

- [ ] **Step 1: adversarial-reviewer 1회차(탐지) 실행, 발견 사항 수정**
- [ ] **Step 2: adversarial-reviewer 2회차(재검증) 실행**

Expected: 2회차에서 신규 치명 결함 없음

- [ ] **Step 3: 수정 사항 커밋**

```bash
git -C ~/.skills add skills/notion-to-tistory/
git -C ~/.skills commit -m "fix: adversarial review 반영"
```

### Task 6: 설치·스모크 검증·push

**Files:**
- Create: `~/.agents/skills/notion-to-tistory` (symlink, my-ai-agents 레포 — 기존 스킬들과 동일 패턴)

- [ ] **Step 1: 심링크 등록**

Run: `ln -s /Users/User/.skills/skills/notion-to-tistory /Users/User/.agents/skills/notion-to-tistory && ls -l /Users/User/.agents/skills/notion-to-tistory`
Expected: 심링크 생성 확인. (~/.agents 레포 커밋 여부는 기존 심링크들의 추적 상태를 따른다)

- [ ] **Step 2: 스모크 테스트 — 키 미등록 경로**

Run: `python3 ~/.skills/skills/notion-to-tistory/scripts/generate_image.py --prompt test --out /tmp/x.png; echo "exit=$?"`
Expected: Keychain에 키가 없는 현재 상태에서 한국어 등록 안내 + `exit=2`, 파일 미생성

- [ ] **Step 3: 전체 테스트 재실행**

Run: `python3 -m pytest ~/.skills/skills/notion-to-tistory/tests/ -v`
Expected: 전체 PASS

- [ ] **Step 4: push**

Run: `git -C ~/.skills push -u origin feat/notion-to-tistory`
Expected: 원격 브랜치 생성. (main 병합은 사용자 결정 — finishing-a-development-branch에서 처리)

### 잔여(실키 E2E — 계획 밖, 사용자 입력 필요)

Gemini API 키 발급·Keychain 등록 후, 실제 노션 게시 링크 1건으로 전체 파이프라인을 1회 실행해 패키지 산출물을 확인한다. 키와 샘플 링크가 준비되기 전에는 완료로 선언하지 않고 "실이미지 E2E 미검증"을 명시한다.
