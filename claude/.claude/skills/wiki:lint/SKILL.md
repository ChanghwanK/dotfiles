---
name: wiki:lint
description: |
  LLM Wiki (04. Wiki/) 정합성 검증 및 개선 스킬. _index.md 동기화, 깨진 링크, 고아 노트,
  메타데이터 누락, 잘못된 type, 오래된 노트를 감지하고 자동 수정 또는 개선안을 제안.
  사용 시점: (1) 주기적 Wiki 건강 점검, (2) 노트 추가 후 index 동기화 확인,
  (3) 태그 정규화, (4) 고아 노트 연결 개선.
  트리거 키워드: "wiki 점검", "wiki lint", "index 동기화", "링크 검증", "태그 정리",
  "wiki 건강", "노트 정합성", "/wiki:lint".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/wiki:lint/scripts/wiki-lint.py *)
  - Read
  - Edit
---
# wiki:lint

LLM Wiki (`04. Wiki/`)의 정합성과 메타데이터 품질을 검증하고, 개선 제안을 수행한다.

---

## 핵심 원칙

- `check`: 읽기 전용 — 파일 수정 없음
- `fix --target tags`: 유일한 auto-fix — `_lib/tags.py` normalize_tags() 재사용
- 그 외 개선(broken-links, index-sync 등)은 Claude가 Read/Edit으로 직접 수행
- `--dry-run`을 반드시 먼저 확인 후 실제 적용

---

## 체크 항목

| Target | 설명 | 심각도 |
|--------|------|--------|
| `broken-links` | `[[링크]]` 대상 파일 없음 | error |
| `index-dead` | `_index.md` 항목이 없는 파일을 가리킴 | error |
| `index-sync` | Wiki 노트가 `_index.md`에 미등록 | error |
| `metadata` | title/date/type/tags 중 누락 | warning |
| `type-invalid` | type이 허용 값(concept/system/incident/synthesis/career) 외 | warning |
| `tags` | domain/ 형식 미준수 태그 | warning |
| `orphans` | 인바운드 링크 0개 노트 (`_index.md` 링크 포함) | warning |
| `missing-related` | concept/incident/synthesis 노트에 관련 노트 섹션 없음 | info |
| `stale` | last_reviewed 없음 또는 90일 초과 | info |

---

## 워크플로우

### Step 1 — 전체 검사 실행

```bash
python3 /Users/changhwan/.claude/skills/wiki:lint/scripts/wiki-lint.py \
  check --target all [--format text|json]
```

### Step 2 — 자동 수정 (tags)

```bash
# 미리보기
python3 /Users/changhwan/.claude/skills/wiki:lint/scripts/wiki-lint.py \
  fix --target tags --dry-run

# 확인 후 적용
python3 /Users/changhwan/.claude/skills/wiki:lint/scripts/wiki-lint.py \
  fix --target tags
```

### Step 3 — Claude 직접 개선

- **broken-links / index-dead**: Read로 해당 노트 확인 → 링크 대상 파일 탐색 → Edit으로 수정
- **index-sync**: 미등록 노트를 `04. Wiki/_index.md` 해당 섹션에 추가
- **missing-related**: 연관 노트 탐색 → `## 관련 노트` 섹션 추가
- **orphans**: `_index.md` 또는 관련 노트에 링크 추가 제안

---

## 주의사항

- `fix` 명령은 `--target tags`만 지원. 나머지는 Claude 판단 필요
- 메타 파일(`_index.md`, `_log.md`, `_overview.md`, `schema.md`)은 모든 체크에서 제외
- 검사 범위: `04. Wiki/` 전체 (Daily 및 Sources 제외)
- `topic/` 접두사 태그는 정규화 없이 그대로 유지됨
