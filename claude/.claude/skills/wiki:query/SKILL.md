---
name: wiki:query
description: |
  Obsidian 지식 베이스 검색 스킬. 키워드/태그로 관련 노트를 찾고 링크 그래프 기반 연관 노트까지 탐색.
  사용 시점: (1) 특정 주제 노트 검색, (2) 노트 작성 전 관련 지식 탐색, (3) Daily Note Issues 검색,
  (4) 도메인별 지식 인벤토리 파악.
  트리거 키워드: "노트 검색", "관련 노트", "obsidian 검색", "지식 찾기", "노트 찾아줘", "/wiki:query".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/wiki:query/scripts/obsidian-query.py *)
  - Read
---
# wiki:query

Obsidian vault(217개+ 노트)에서 키워드/태그/연관 링크 그래프로 관련 지식을 찾는다.

---

## 핵심 원칙

- `search`: 제목·본문 키워드 + 태그 필터 → 스코어 정렬
- `related`: BFS 링크 그래프 + 태그 겹침으로 연관 노트 탐색 (depth 기본 2홉)
- `find-issues`: Daily Note의 `## Issues` 섹션 수집
- 결과는 JSON — Claude가 상위 노트를 Read 후 내용 요약 제공

---

## 워크플로우

### Step 1 — 검색 실행

```bash
# 키워드 검색 (기본 scope: 02. Notes + 03. Resources)
python3 /Users/changhwan/.claude/skills/wiki:query/scripts/obsidian-query.py \
  search --query "검색어" [--tags domain/kubernetes] [--type learning-note] [--limit 10]

# 연관 노트 탐색 (링크 그래프 BFS)
python3 /Users/changhwan/.claude/skills/wiki:query/scripts/obsidian-query.py \
  related --note "노트 파일명.md" [--depth 2] [--limit 10]

# Daily Note Issues 검색
python3 /Users/changhwan/.claude/skills/wiki:query/scripts/obsidian-query.py \
  find-issues [--date 2026-04-20] [--days-back 7]
```

### Step 2 — 결과 분석 및 노트 읽기

1. JSON 결과에서 score 상위 노트 2-3개 선택
2. `Read` 도구로 해당 노트 파일 읽기
3. 핵심 내용 요약 + 관련 노트 목록 제시

### Step 3 — 연관 탐색 (필요 시)

검색 결과 중 가장 관련성 높은 노트를 시작점으로 `related` 실행 → 추가 지식 발굴

---

## 스코어 계산

| 항목 | 점수 |
|------|------|
| 제목에 검색어 포함 | +10 |
| 본문 등장 횟수 × 2 | +N |
| 지정 태그 일치 | +3 |
| 직접 링크 (related) | +5 |
| 공유 domain 태그 × 3 (related) | +N |

---

## 주의사항

- `--scope all`은 Daily Notes 포함 (날짜별 노트 다수 포함될 수 있음)
- `--note` 파라미터는 부분 일치 지원 (파일명 일부 또는 제목 키워드)
- 볼트 경로: `/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home`
