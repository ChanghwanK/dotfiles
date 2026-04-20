---
name: obsidian:lint
description: |
  Obsidian 지식 베이스 링크 정합성 검증 및 개선 스킬. 깨진 링크, 고아 노트, 메타데이터 누락,
  오래된 노트를 감지하고 자동 수정 또는 개선안을 제안.
  사용 시점: (1) 주기적 볼트 건강 점검, (2) 노트 추가 후 링크 검증, (3) 태그 정규화 정리,
  (4) 고아 노트 연결 개선.
  트리거 키워드: "노트 점검", "링크 검증", "lint", "볼트 점검", "깨진 링크", "고아 노트", "태그 정리", "/obsidian:lint".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/obsidian:lint/scripts/obsidian-lint.py *)
  - Read
  - Edit
---
# obsidian:lint

Obsidian vault의 링크 정합성과 메타데이터 품질을 검증하고, 태그 자동 정규화와 개선 제안을 수행한다.

---

## 핵심 원칙

- `check`: 읽기 전용 — 파일 수정 없음
- `fix --target tags`: 유일한 auto-fix — `_lib/tags.py` normalize_tags() 재사용
- 그 외 개선(broken-links, missing-related 등)은 Claude가 Read/Edit으로 직접 수행
- `--dry-run`을 반드시 먼저 확인 후 실제 적용

---

## 체크 항목

| Target | 설명 | 심각도 |
|--------|------|--------|
| `broken-links` | [[링크]] 대상 파일 없음 | error |
| `metadata` | title/date/type/tags 중 누락 | warning |
| `tags` | domain/ 형식 미준수 태그 | warning |
| `orphans` | 인바운드 링크 0개 노트 | warning |
| `missing-related` | learning-note에 관련 노트 섹션 없음 | info |
| `stale` | last_reviewed 없음 또는 90일 초과 | info |

---

## 워크플로우

### Step 1 — 전체 검사 실행

```bash
python3 /Users/changhwan/.claude/skills/obsidian:lint/scripts/obsidian-lint.py \
  check --target all [--format text|json]
```

### Step 2 — 자동 수정 (tags)

```bash
# 미리보기
python3 /Users/changhwan/.claude/skills/obsidian:lint/scripts/obsidian-lint.py \
  fix --target tags --dry-run

# 확인 후 적용
python3 /Users/changhwan/.claude/skills/obsidian:lint/scripts/obsidian-lint.py \
  fix --target tags
```

### Step 3 — Claude 직접 개선

- **broken-links**: Read로 해당 노트 확인 → 링크 대상 파일 탐색 → Edit으로 수정
- **missing-related**: `obsidian:query related` 실행으로 연관 노트 발굴 → `## 관련 노트` 섹션 추가
- **orphans**: 관련 MOC 또는 노트에 링크 추가 제안

---

## 주의사항

- `fix` 명령은 `--target tags`만 지원. 나머지는 Claude 판단 필요
- Daily Notes(`01. Daily/`)는 orphans/metadata 체크에서 제외
- lint 범위 기본값: `02. Notes/` + `03. Resources/`
