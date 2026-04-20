---
allowed-tools:
  - Read
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py *)
---

# Agent A: 어제 리뷰 수집 (Obsidian + Transcript)

어제 날짜는 {yesterday_date}이다.

아래 순서로 데이터를 수집하고 결과를 요약하여 반환하라. 단, 코드나 JSON 전체를 반환하지 말고 파싱된 요약만 반환하라.

## 수집 절차

1. Read 도구로 어제 Obsidian Daily Note를 읽는다.
   - 경로: `/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/{yesterday_date}.md`

2. 읽은 파일에서 다음을 파싱한다:
   - `## Top 3 오늘의 목표` 섹션: `[x]` → 완료, `[ ]` → 미완료
   - `## 내일 해야할 것` 섹션: 체크박스 항목 + 서브 메모 (있으면)
   - `## Todos` 섹션: `[x]`/`[ ]` 진행률
   - `## Notes` 섹션 내용
   - `## 회고 (EOD)` 섹션 내용

3. 어제 Claude transcript를 분석한다:
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py --date {yesterday_date}
   ```

4. Obsidian 파일이 없으면 (FileNotFoundError 또는 빈 파일):
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read --date yesterday
   ```
   Notion의 완료/미완료 항목을 폴백 소스로 사용한다.

## Obsidian 체크박스 파싱 규칙

```
## Top 3 오늘의 목표
- [x] 완료된 항목          → done: true
- [ ] 미완료 항목          → done: false
	- 서브 메모 (탭 들여쓰기) → 부모 항목의 메모

## 내일 해야할 것
- [ ] 항목                  → tomorrow_task (오늘 반드시 고려)
	- 서브 메모 (탭 들여쓰기) → 부모 항목의 컨텍스트
```

## 반환 형식

이 형식을 정확히 따를 것. 코드/JSON 원문 반환 금지.

```yaml
---
completed: [항목1 (Obsidian Top 3), 항목2 (transcript)]
incomplete: [항목3]
tomorrow_tasks: ["kyverno 업데이트", "operator 학습", "k6 stg 배포 체크 — 배포 에러 발생하면 abort...", ...]
notes: "Notes 섹션 내용 (없으면 빈 문자열)"
retrospective: "회고 내용 (없으면 빈 문자열)"
obsidian_found: true/false
---
```
