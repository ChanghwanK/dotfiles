---
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py *)
  - mcp__claude_ai_Google_Calendar__gcal_list_events
---

# Agent B: Notion + Google Calendar 수집

오늘 날짜는 {today_date}이다.

아래 순서로 데이터를 수집하고 결과를 요약하여 반환하라. 단, raw JSON 전체를 반환하지 말고 파싱된 요약만 반환하라.

## 수집 절차

1. Notion 주간 Task 조회:
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read-weekly
   ```

2. Notion 오늘 페이지 조회:
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py read --date today
   ```
   결과에 `error`가 있으면 (페이지 없음) 자동으로 생성:
   ```bash
   python3 /Users/changhwan/.claude/skills/daily:start/scripts/notion-daily.py create --date today --title "@오늘 업무 일지"
   ```
   생성 후 반환된 `page_id`를 기록한다.

3. Google Calendar 오늘 일정 조회:
   - `gcal_list_events` 도구로 `time_min={today_date}T00:00:00+09:00`, `time_max={today_date}T23:59:59+09:00` 조회
   - primary 캘린더 대상. 시작 시간순 정렬
   - 다음 제목의 이벤트는 결과에서 제외 (반복 일정, 노이즈):
     - "Busy"
     - "Todo List Up"
     - "daily sync up(오후)"

## 반환 형식

이 형식을 정확히 따를 것. 코드/JSON 원문 반환 금지.

```yaml
---
weekly_tasks:
  - name: "작업명", priority: P1, status: 진행중, due: 2026-03-10~2026-03-14, level: daily
  - name: "주간 프로젝트명", priority: P1, status: 진행 중, due: 2026-03-23~2026-04-05, level: weekly_project
  - ...
today_page_id: "notion-page-uuid"
today_page_created: true/false
today_todos: ["기존 Todo 항목1", ...]
calendar_events:
  - title: "이벤트명", start: "10:00", end: "11:00", location: "Google Meet"
  - ...  (없으면 빈 리스트)
---
```
