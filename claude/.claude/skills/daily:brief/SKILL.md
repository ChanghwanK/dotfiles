---
name: daily:brief
description: |
  하루 시작 페이지 다시 보기 스킬. daily:start가 오늘(또는 지정한 날짜) 게시한 하루 시작 Artifact를 새로 만들지 않고 그대로 다시 연다. 완료 체크와 직접 추가한 항목도 그대로 보인다.
  사용 시점: (1) 아침에 만든 하루 시작 화면을 다시 볼 때, (2) 지난 날짜의 하루 시작 페이지를 열 때.
  트리거 키워드: "하루 시작 다시 보기", "브리핑 다시 열어줘", "오늘 보드 열어줘", "daily brief", "/daily:brief".
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/daily:brief/scripts/find-brief.py *)
---
# daily:brief

`daily:start`가 저장한 브리핑 JSON(`~/.claude/tmp/daily-start/{date}.json`)의 `artifact_url`을 읽어 그 페이지를 다시 연다.

## 핵심 원칙

- 읽고 열기만 한다. 페이지를 렌더하거나 다시 게시하지 않고, 브리핑 JSON도 고치지 않는다(재게시하면 같은 URL이라도 내용이 아침 데이터로 덮인다)
- 페이지가 없으면 만들지 않는다. `/daily:start`를 안내하고 끝낸다
- 결과에 이모지와 em dash를 쓰지 않는다

## 워크플로우

### Step 1: 페이지 주소 찾기

인자로 날짜(`YYYY-MM-DD`)를 받았으면 `--date`로 넘기고, 없으면 오늘(`Asia/Seoul`)이다.

```bash
python3 /Users/changhwan/.claude/skills/daily:brief/scripts/find-brief.py [--date 2026-11-24]
```

출력:
- 성공: `{"success": true, "date", "artifact_url", "title", "path"}`
- 실패: `{"success": false, "date", "error", "latest"}`. `latest`는 그 날짜 이전에 가장 최근 브리핑이 있는 날짜(없으면 null)

### Step 2: 열기

- 성공이면 Artifact 도구 `action: "open"`, `url: <artifact_url>`로 연다
- 실패면 열지 않고 아래처럼 알린다
  - 오늘 것이 없음: "오늘 하루 시작 페이지가 아직 없습니다. `/daily:start`로 만드세요." `latest`가 있으면 "가장 최근 페이지는 {latest}입니다. `/daily:brief {latest}`로 열 수 있습니다"를 덧붙인다
  - JSON은 있는데 `artifact_url`이 없음: 그날 `daily:start`가 게시 전에 멈춘 것이다. 오류 문구를 그대로 전한다

### Step 3: 응답

두 줄로 끝낸다.

```
{date} 하루 시작 페이지를 열었습니다. (제목: {title})
{artifact_url}
```

Claude 데스크톱 앱에서 "상태 반영하기"로 일지에 바로 반영하려면 앱 사이드바에 고정된 페이지로 열어야 한다(`daily:start`가 매일 고정한다). 사용자가 반영 버튼을 물을 때만 이 점을 덧붙인다.

## 검증

```bash
python3 /Users/changhwan/.claude/skills/skills:manage/scripts/manage_skill.py validate --scope user daily:brief
python3 /Users/changhwan/.claude/skills/daily:brief/scripts/find-brief.py --date 1999-01-01   # success: false 확인
```
