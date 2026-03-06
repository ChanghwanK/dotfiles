# Obsidian Daily Note 출력 템플릿

## Markdown 템플릿

```markdown
---
Date: 2026-03-05
tags:
  - Daily
---

# Top 3
1. [작업명] — [이유]
2. [작업명] — [이유]
3. [작업명] — [이유]

# 어제 리뷰 (YYYY-MM-DD)

## 완료
- 항목1
- 항목2 (transcript에서 추가)

## 진행 중 / 미완료
- 항목

## 메모
- 메모 내용

# 오늘 할 것들
- [ ] 항목1
- [ ] 항목2

# Carry-over
- 항목
```

## 섹션별 작성 규칙

- `Date`: YAML frontmatter, 오늘 날짜 (YYYY-MM-DD)
- `tags`: `[Daily]` 고정
- `Top 3`: daily:start와 동일한 선정 로직 적용, 각 항목에 이유 포함
- `어제 리뷰`: 날짜 헤딩에 실제 어제 날짜 기입 (예: `# 어제 리뷰 (2026-03-04)`)
  - `완료`: Notion done=true + transcript 추가 항목 (출처 괄호 표기)
  - `진행 중 / 미완료`: Notion done=false 항목
  - `메모`: 어제 Notion note 내용
- `오늘 할 것들`: 오늘 Notion todos를 `- [ ]` 형식으로 (done=true면 `- [x]`)
- `Carry-over`: carry-over 항목이 없으면 섹션 자체를 생략
