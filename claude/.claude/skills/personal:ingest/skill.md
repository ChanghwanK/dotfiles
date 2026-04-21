---
name: personal:ingest
description: |
  Personal Wiki (Second Self) ingest 스킬.
  04. Wiki/personal/raw/*.md 파일을 읽어 wiki/ 하위 구조화 페이지를 생성/업데이트한다.
  LLM이 패턴을 합성하여 "나 자신"을 데이터로 누적한다.
  트리거 키워드: "personal ingest", "나 자신 위키", "second self 업데이트", "personal:ingest", "/personal:ingest".
model: sonnet
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Bash(find * -type f -name "*.md")
  - Bash(ls *)
---

# Personal Wiki Ingest 스킬

`04. Wiki/personal/raw/` 기록을 분석하여 `wiki/` 구조화 페이지를 생성·업데이트한다.
"나 자신"을 데이터로 누적하는 Second Self 엔진.

---

## 핵심 원칙

- **LLM이 Wiki를 소유한다**: 인간(changhwan)은 raw/에 소스를 쌓고, LLM이 wiki/를 작성·유지한다.
- **합성이 핵심**: 단순 요약이 아니라 패턴·반복·성장·모순을 감지하고 통합한다.
- **복리 축적**: 새 raw 항목이 기존 wiki 페이지를 업데이트하거나 새 페이지를 생성한다.
- **raw/는 불변**: raw/*.md는 읽기만 하고 절대 수정하지 않는다.

---

## 경로 상수

```
VAULT = ~/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home
RAW_DIR = VAULT/04. Wiki/personal/raw/
WIKI_DIR = VAULT/04. Wiki/personal/wiki/
```

---

## Wiki 카테고리 구조

```
wiki/
  _index.md           # 전체 카탈로그 (항상 최신 유지)
  _log.md             # ingest 작업 이력 (append-only)
  patterns/           # 반복 행동 패턴, 습관, 안티패턴
  values/             # 가치관, 의사결정 원칙
  growth/             # 역량 성장 기록, 학습 패턴
  goals/              # 목표와 진행 상황 (장기/단기)
  reflections/        # 중요한 통찰, 자기 이해 메모
```

---

## 워크플로우

### Step 1 — raw 파일 목록 조회

```
04. Wiki/personal/raw/ 안의 모든 .md 파일을 Glob으로 조회
```

- 날짜순 정렬 (오래된 것 → 최근 순)
- 파일 수와 날짜 범위 확인
- 이미 처리된 raw 파일은 `_log.md`에서 확인 (중복 ingest 방지)

### Step 2 — 신규/미처리 raw 파일 읽기

`_log.md`에 기록된 날짜 이후 파일만 처리 (첫 실행 시 전체 처리).

각 raw 파일에서 추출:
- **결정한 것**: 의사결정과 그 이유
- **배운 것**: 기술/개인 학습
- **개선점/후회**: 문제, 반복 실수, 후회
- **주요 작업**: 완료한 일
- **오늘의 상태**: 에너지·집중도 / 인상 깊었던 것 / 머릿속에 남는 생각

### Step 3 — 기존 wiki/ 현황 파악

`wiki/_index.md`를 읽어 현재 존재하는 페이지 목록 확인.
없으면 `_index.md`와 `_log.md`를 빈 템플릿으로 생성.

### Step 4 — 패턴 합성 및 wiki 페이지 생성/업데이트

**4-1. patterns/ 업데이트**

raw 전체를 교차 분석하여 반복 패턴 탐지:
- 같은 문제가 2회 이상 등장 → `patterns/` 페이지 생성 또는 업데이트
- 예시: "분석 완료 후 실행 미착수", "이월 반복 태스크", "Top 3 미체크 습관"

패턴 페이지 형식:
```markdown
---
title: "패턴명"
type: pattern
first_seen: YYYY-MM-DD
last_seen: YYYY-MM-DD
frequency: N회 관찰
status: active | resolved
tags: [domain/self, topic/habit]
---

## 패턴 설명
...

## 관찰 사례
- [YYYY-MM-DD] 구체적 상황
- [YYYY-MM-DD] 구체적 상황

## 근본 원인 (LLM 합성)
...

## 시도한 개선
- [YYYY-MM-DD] 시도한 것, 결과
```

**4-2. values/ 업데이트**

"결정한 것" 섹션에서 의사결정 원칙 추출:
- 특정 방향을 반복 선택하는 패턴 → `values/의사결정-원칙.md`에 통합
- 예시: "Draft-Only 워크플로우", "로컬 우선 자동화", "LLM 복리 설계"

**4-3. growth/ 업데이트**

"배운 것" 섹션에서 학습 궤적 추출:
- 기술 학습 기록 → `growth/기술-학습-궤적.md`
- 스킬 구축 과정 → `growth/devops-역량-성장.md`
- 학습 패턴 (어떤 방식으로 배우는가) → `growth/학습-패턴.md`

**4-4. reflections/ 업데이트**

중요한 통찰이나 인사이트를 발견하면 `reflections/`에 단독 페이지 생성.
기준: 동일 인사이트가 2회 이상 언급되거나, 행동 변화를 이끈 통찰.

### Step 5 — _index.md 업데이트

새로 생성/업데이트된 페이지를 `_index.md`에 반영.

형식:
```markdown
---
title: Personal Wiki Index
type: index
last_updated: YYYY-MM-DD
---

# Personal Wiki (Second Self)

## Patterns
- [[patterns/패턴명]] — 한줄 설명 (N회 관찰, 상태)

## Values
- [[values/원칙명]] — 한줄 설명

## Growth
- [[growth/페이지명]] — 한줄 설명

## Reflections
- [[reflections/통찰명]] — 한줄 설명
```

### Step 6 — _log.md에 ingest 이력 append

```markdown
## [YYYY-MM-DD] ingest | raw YYYY-MM-DD ~ YYYY-MM-DD (N개 파일)
- 처리: N개 raw 파일
- 생성: 페이지명, 페이지명
- 업데이트: 페이지명 (이유)
- 탐지된 패턴: 패턴명
```

---

## 출력 포맷

```
## Personal Wiki Ingest 완료

### 처리한 raw 파일
- 2026-04-20.md (1개)

### wiki/ 변경사항
**신규 생성 (N개)**
- patterns/분석-완료-실행-미착수.md
- growth/기술-학습-궤적.md
- values/의사결정-원칙.md
- reflections/...

**업데이트 (N개)**
- 없음 (첫 ingest)

### 탐지된 패턴
1. **분석 완료 후 실행 미착수**: youtube:summary 리팩토링 분석 후 실행 연결 끊김 — 반복 관찰
2. **이월 반복 태스크**: clickhouse 모니터링 3일 이월 — 우선순위 vs 관성 충돌

### 다음 ingest 권고
- daily:review Step 4가 raw/에 매일 추가 → 주 1회 /personal:ingest 실행 권고
```

---

## 주의사항

- `raw/*.md` 파일은 절대 수정하지 않는다 (불변 소스)
- 페이지 내용은 raw 데이터에서 직접 인용하거나 LLM이 합성 — 사실 왜곡 금지
- 아직 raw 데이터가 적으면 (1~7일) 패턴 합성보다 기록 정리에 집중
- 시간이 쌓일수록 패턴 분석의 정확도가 높아진다 — 데이터 복리 효과
