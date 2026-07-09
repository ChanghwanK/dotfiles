---
name: calendar
description: |
  changhwan.kim@socra.ai 구글 캘린더 일정을 생성·조회·수정·삭제하고 빈 시간을 찾는 스킬.
  자연어 일정 요청을 파싱 → 조회는 즉시, 생성·수정은 즉시, 삭제는 확인 후 실행.
  사용 시점: (1) 일정 추가/변경/취소, (2) 특정 기간 일정 조회, (3) 회의 잡을 빈 시간 찾기.
  트리거 키워드: "일정 추가", "일정 조회", "일정 수정", "일정 삭제", "캘린더", "빈 시간", "/calendar".
model: sonnet
allowed-tools:
  - mcp__claude_ai_Google_Calendar__list_calendars
  - mcp__claude_ai_Google_Calendar__list_events
  - mcp__claude_ai_Google_Calendar__get_event
  - mcp__claude_ai_Google_Calendar__create_event
  - mcp__claude_ai_Google_Calendar__update_event
  - mcp__claude_ai_Google_Calendar__delete_event
  - mcp__claude_ai_Google_Calendar__suggest_time
  - AskUserQuestion
---

# calendar

`changhwan.kim@socra.ai` 구글 캘린더 일정을 자연어로 생성·조회·수정·삭제하고, 회의용 빈 시간을 찾는다.

---

## 핵심 원칙

- **계정 고정**: 모든 호출에 `calendarId = changhwan.kim@socra.ai`, `timeZone = Asia/Seoul`을 명시한다. 사용자가 다른 캘린더를 지정하지 않는 한 이 기본값을 항상 적용한다.
- **상대 날짜 절대화**: "내일 3시", "다음 주 월요일", "오늘 오후" 등은 **세션의 오늘 날짜 기준**으로 ISO 8601 절대 시각으로 변환한다 (예: `2026-06-15T14:00:00`). 모호하면 추론값을 출력에 명시한다.
- **확인 정책**: 삭제(delete)만 실행 전 `AskUserQuestion`으로 확인한다. 생성(create)·수정(update)·조회(read)·빈 시간(suggest)은 **즉시 실행**한다.
- **모호성 해소**: 대상 일정 식별이 모호하면(같은 제목 여러 건, "그 미팅" 등) 먼저 `list_events`로 후보를 좁힌 뒤 `AskUserQuestion`으로 선택받는다. 임의로 한 건을 골라 변경/삭제하지 않는다.
- **외부 영향 인지**: 참석자(`attendees`) 추가나 시간 변경은 외부에 초대 메일·알림을 발송한다. 결과 출력에 발송 사실을 명시한다.

---

## 워크플로우: 의도 분기

요청을 아래 5개 흐름 중 하나로 라우팅한다. 시간 정보가 필요한데 누락됐고 추론도 불가하면 그 항목만 사용자에게 묻는다.

### CREATE: 일정 생성

`mcp__claude_ai_Google_Calendar__create_event`

```
필수: summary, startTime, endTime
  - endTime 미지정 시 startTime + 1시간을 기본값으로 사용
선택: description, location, attendees(이메일 배열), addGoogleMeetUrl(회의 링크 요청 시 true), allDay(종일 일정 시 true)
공통: calendarId="changhwan.kim@socra.ai", timeZone="Asia/Seoul"
```

- 즉시 실행 → 생성된 이벤트(제목 / 시각 / 장소 / Meet 링크)를 요약 출력
- 참석자 포함 시: "참석자에게 초대 메일이 발송되었습니다." 안내 추가
- 종일 일정은 `allDay=true` + 날짜만 지정

### READ: 일정 조회

`mcp__claude_ai_Google_Calendar__list_events` / `mcp__claude_ai_Google_Calendar__get_event`

```
기간 조회: list_events(
  calendarId="changhwan.kim@socra.ai",
  startTime=<구간 시작>, endTime=<구간 끝>,
  timeZone="Asia/Seoul", orderBy="startTime", pageSize=10
)
키워드 검색: list_events에 fullText="<검색어>" 추가
단건 상세: get_event(calendarId="changhwan.kim@socra.ai", eventId=<id>)
```

- "오늘/이번 주/다음 주" 같은 기간 표현을 startTime~endTime으로 변환
- 결과를 표로 출력: `시각 | 제목 | 장소`
- 결과 없으면 "해당 기간에 일정이 없습니다." 출력

### UPDATE: 일정 수정

`mcp__claude_ai_Google_Calendar__get_event` → `mcp__claude_ai_Google_Calendar__update_event`

```
1. list_events 또는 get_event로 대상 eventId 및 현재 값 확인
2. update_event(
     calendarId="changhwan.kim@socra.ai", eventId=<id>,
     <변경 필드만 전달>
   )
```

- **부분 업데이트**: 변경하려는 필드만 전달한다 (전달 안 한 필드는 유지됨)
- 시간 변경 시: `startTime` + `endTime` + `timeZone="Asia/Seoul"`을 함께 전달
- 참석자 추가: `addedAttendees`(Attendee 객체 배열), 제거: `removedAttendeeEmails`
- 즉시 실행 → 변경 전/후 비교 출력

### DELETE: 일정 삭제 (확인 필수)

`mcp__claude_ai_Google_Calendar__list_events` → 확인 → `mcp__claude_ai_Google_Calendar__delete_event`

```
1. list_events로 삭제 대상 특정 (eventId 확보)
2. 대상 요약 출력: "제목 / 시각"
3. AskUserQuestion으로 삭제 승인 받기
4. delete_event(calendarId="changhwan.kim@socra.ai", eventId=<id>)
```

- 삭제는 복구 불가. 반드시 확인 후 실행
- 후보가 여러 건이면 먼저 선택받고, 그 다음 삭제 확인
- 반복 일정이면 단일 인스턴스/전체 시리즈 중 어느 범위를 삭제할지 확인

### SUGGEST: 빈 시간 찾기

`mcp__claude_ai_Google_Calendar__suggest_time`

```
suggest_time(
  attendeeEmails=["changhwan.kim@socra.ai", <추가 참석자...>],
  startTime=<탐색 구간 시작>, endTime=<탐색 구간 끝>,
  durationMinutes=<회의 길이, 기본 30>,
  timeZone="Asia/Seoul",
  preferences={ startHour:"09:00", endHour:"18:00", excludeWeekends:true }
)
```

- `attendeeEmails`에 본인 계정을 항상 포함 (primary 캘린더 접근)
- 추천 슬롯 목록 출력 → 사용자가 슬롯을 고르면 **CREATE 흐름**으로 연결해 일정 생성
- 근무 시간/주말 제외는 preferences로 제어 (사용자 요청 반영)

---

## 출력 형식

**생성/수정/삭제 결과**
```
[생성됨] 팀 회의
  시각: 2026-06-16 15:00 ~ 16:00 (KST)
  장소: 회의실 A
  Meet: https://meet.google.com/...
  참석자에게 초대 메일이 발송되었습니다.
```

**조회 결과**
```
2026-06-15 (오늘) 일정: 3건

시각              | 제목         | 장소
14:00 ~ 15:00     | 스프린트 회의 | 회의실 B
16:00 ~ 16:30     | 1:1          | -
19:00 (종일)      | 워크샵       | 판교
```

**빈 시간 추천**
```
다음 주 빈 시간 (60분, 평일 09:00~18:00): 추천 3건
1. 2026-06-16 (월) 10:00 ~ 11:00
2. 2026-06-17 (화) 14:00 ~ 15:00
3. 2026-06-18 (수) 11:00 ~ 12:00

어느 시간으로 일정을 잡을까요?
```

---

## 주의사항

- **삭제는 복구 불가**. 항상 확인 후 실행. 생성·수정은 즉시 실행하되 결과를 명확히 보고한다.
- **외부 발송**: 참석자 추가·시간 변경은 초대 메일/알림을 발송한다. 테스트 일정에는 참석자를 넣지 않는다.
- **상대 날짜는 오늘 기준**: 세션 컨텍스트의 현재 날짜를 기준으로 계산하고, timezone은 Asia/Seoul로 고정한다.
- **권한 오류 대응**: `calendarId="changhwan.kim@socra.ai"` 호출이 권한 오류(403/notFound)로 실패하면, 연결된 Google Calendar MCP가 다른 계정으로 인증되어 있고 해당 캘린더 공유 권한이 없는 상황이다. 이때는 (1) MCP를 changhwan.kim@socra.ai로 재인증하거나 (2) 해당 계정 캘린더를 공유받아야 함을 안내한다. 임의로 `primary`로 폴백해 다른 계정 캘린더를 건드리지 않는다.
- **eventId 확보**: 수정·삭제·단건 조회는 eventId가 필수다. 사용자가 제목으로만 지칭하면 먼저 list_events로 id를 찾는다.
