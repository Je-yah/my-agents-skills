# Jehye.log 블로그 프로필

대상: https://mgs10204.tistory.com/ (Tech Archive ∥ AI Research & Paper Review ∥ SW Engineering & Project Devlog)
작성 기준: 2026-11-14 실제 게시글(/12, /13 등) 분석.

## 카테고리 분류 기준

기존 4개 카테고리만 사용한다. 신설하지 않는다.

| 카테고리 | 판정 기준 | 예시 |
|---|---|---|
| Devlog | 개발 과정·구현·트러블슈팅이 중심 | 해커톤 개발기, 프로젝트 구현기, 익스텐션 개발 |
| 회고 | 경험·배움·감상이 중심, 코드보다 사람 | 해커톤 참가 후기, 학기 회고, 컨퍼런스 참관기 |
| Paper Review | 논문이 중심 | 논문 리뷰, 연구 키워드 정리 |
| CS | 개념 학습 정리가 중심 | 인코딩, 네트워크, 자료구조 정리 |

경계 판정: 한 글에 개발과 회고가 섞이면 분량이 더 많은 쪽을 따른다. 판단이 어려우면 분류 근거 두 가지를 제시하고 사용자에게 묻는다.

## 제목 규칙

형식: `[Prefix] 제목` — 기존 글 관행.

prefix는 카테고리와 함께 고른다. 아래 대응을 기본으로 한다.

| Prefix | 기본 카테고리 |
|---|---|
| `[Troubleshooting]` `[Project]` `[Toy Project]` `[Agent]` | Devlog |
| `[Hackathon]` `[Conference]` `[Retrospective]` `[Career]` `[Identity]` | 회고 |
| `[Research]` | Paper Review |
| `[Encoding]` `[Study]` | CS |

- 기존 어휘에 맞는 것이 있으면 기존 어휘를 우선 사용한다.
- prefix의 기본 카테고리와 2번 분류 결과가 다르면 분류 결과를 우선하고 그 이유를 한 줄 남긴다.
- 제목은 콜론으로 부제를 나눌 수 있다. 예: `[Encoding] 텍스트 인코딩: ASCII부터 유니코드 심화까지`

## 태그 어휘

기술 분야(1~2개): `Agentic AI` `AI Systems` `Backend` `Infrastructure` `Automation` `Vision`
보조 태그(0~3개): 사용한 핵심 스택·도구명 그대로 (예: `FastAPI` `Claude Code` `FFmpeg` `Docker`)
활동 태그(해당 시): `해커톤` `공모전` `컨퍼런스`

## 문체 가이드

실제 게시글에서 추출한 특징. 초안은 이 문체를 따른다.

- 어미: 합니다체 기본, 개인 경험 서술에 해요체 약간 혼용
- 구조: `INTRO` → `MAIN`(소제목 세분) → `OUTRO` 헤딩을 명시적으로 사용
- 도입: 구체적 상황·문제 제시로 시작 (예: "~하면서 문제가 생겼습니다.")
- 전개: 문제 중심 — "왜 문제인가" → "어떻게 해결했나" 순서
- 코드블록: 복사해서 실행 가능한 형태, 주석으로 용도 설명
- 리스트·표: 단계 설명은 불릿, 비교는 표
- 마무리: 배운 점 성찰 + 향후 계획·확장 가능성 한두 문장
- 문장은 짧게(25~35자 내외), 어려운 개념은 바로 뒤에 풀어서 설명
- 원본(노션)에 없는 사실·수치·평가를 추가하지 않는다

## 패키지 형식

출력 루트: `~/Documents/BlogPackages/<YYYY-MM-DD>-<slug>/` (slug는 제목 핵심어의 영문 kebab-case, 중복 시 `-2` suffix)

`post.md` 구조:
- 본문만 담는다(제목은 meta.md에). INTRO/MAIN/OUTRO 헤딩 포함.
- 이미지 삽입 위치는 마커로 표시하며, 출처를 반드시 명시한다.
  - 노션 원본 이미지: `<!-- image: images/NN.png | <대체텍스트> | source: notion:<원본 URL> -->`
  - 생성 삽화: `<!-- image: images/NN.png | <대체텍스트> | source: generate | prompt: <영문 프롬프트> -->`
- `NN`은 본문 등장 순서대로 01부터 연속 부여한다. 특정 삽화 생성이 실패(exit 3)해도 번호는 그대로 두고 그 마커만 "생성 실패" 주석으로 남긴다.
- 썸네일 마커는 본문에 넣지 않는다(티스토리 대표 이미지로 별도 지정).

`meta.md` 필드:
```
제목: [Prefix] 제목
카테고리: Devlog | 회고 | Paper Review | CS
태그: 쉼표로 구분
썸네일: thumbnail.png 설명(대체텍스트)
원본: 노션 게시 링크
```

`thumbnail.png`: 16:9. `images/`: 본문 삽화 `01.png`, `02.png`, … (노션 원본 이미지 우선, 생성 삽화는 보조)
