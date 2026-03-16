---
name: youtube:summary
description: |
  YouTube 영상의 자막을 추출하여 심층 요약/분석 후 Obsidian 노트로 저장하는 스킬.
  영상 URL을 입력하면 자막 추출 → 요약 → 핵심 포인트 → 인사이트 분석 → Obsidian 저장.
  트리거 키워드: "유튜브 요약", "영상 요약", "youtube summary", "/youtube:summary".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/youtube:summary/scripts/yt-extract.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py *)
  - Read
  - Write(/tmp/yt-extract-result.json)
  - Write(/tmp/obsidian-content.json)
---

# YouTube Summary Skill

YouTube 영상의 자막을 추출하여 구조화된 요약 + 심층 분석을 수행하고 Obsidian 노트로 저장한다.

## 워크플로우

### Step 1 — URL 확인

- 사용자로부터 YouTube URL 수신
- URL 형식 검증 (`youtube.com/watch?v=` 또는 `youtu.be/`)
- 유효하지 않은 URL이면 사용자에게 알림

### Step 2 — 자막 + 메타데이터 추출

```bash
python3 /Users/changhwan/.claude/skills/youtube:summary/scripts/yt-extract.py extract "<URL>"
```

- `/tmp/yt-extract-result.json` 읽어서 결과 확인
- `success: false`이면 에러 메시지를 사용자에게 전달하고 중단
- 자막 우선순위: `ko` → `en` → `ko(auto)` → `en(auto)`

### Step 3 — 요약 및 분석 생성

자막 텍스트(`transcript` 필드)를 기반으로 **한국어**로 다음 구조의 분석을 생성한다:

```markdown
# [영상 제목]

> **채널**: [채널명] | **길이**: [MM:SS] | **날짜**: [YYYY-MM-DD]
> **원본**: [YouTube URL]

## 핵심 요약
3-5문장으로 영상의 핵심 메시지 요약

## 주요 포인트
- 포인트 1
- 포인트 2
- ...

## 심층 분석
영상 내용에 대한 비판적 분석, 맥락, 의미

## 실무 적용점
DevOps/인프라 관점에서의 적용 가능한 인사이트 (해당 시)

## 인상적인 인용/구절
> "직접 인용구"

## 인사이트
영상에서 얻은 핵심 인사이트를 3-5개 bullet으로 정리.
단순 내용 반복이 아닌, "이 영상이 나에게 의미하는 것"을 도출.

## 추천 Action Items
영상 내용을 기반으로 실행 가능한 구체적 액션 아이템 2-4개.
각 항목은 체크박스(`- [ ]`) 형식으로 작성.

## 관련 키워드
`keyword1` `keyword2` `keyword3`
```

**생성 규칙:**
- 출력 언어는 항상 **한국어**
- 영어 자막이라도 한국어로 번역하여 분석
- 기술 용어는 원문을 병기 (예: "서비스 메시(Service Mesh)")
- `실무 적용점` 섹션은 DevOps/인프라 관련 내용일 때만 포함, 아니면 생략
- `인상적인 인용/구절`은 자막에서 직접 발췌 (번역 시 원문 병기)
- `인사이트`는 영상의 정보를 내재화한 해석 — 시청자(DevOps Engineer) 관점에서 "So what?"에 답하는 내용
- `추천 Action Items`는 당장 실행 가능한 수준의 구체적 행동. 추상적 목표("더 공부하자") 금지, 구체적 행동("X 문서를 읽고 Y를 시도해보기")으로 작성
- 두 섹션 모두 영상 주제와 무관하게 항상 포함 (DevOps 비관련 영상이라도 개인 성장/사고방식 관점에서 작성)

### Step 4 — Obsidian 노트 저장

1. Step 3에서 생성한 마크다운 본문(제목 `#` 헤딩 제외)을 JSON으로 `/tmp/obsidian-content.json`에 Write:
```json
{
  "blocks": "메타정보 blockquote부터 관련 키워드까지의 마크다운 텍스트"
}
```

2. 기존 `obsidian:note` 스크립트 호출:
```bash
python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py create \
  --title "[영상제목] 유튜브 요약" \
  --tags "YouTube,태그1,태그2" \
  --content-file /tmp/obsidian-content.json
```

**태그 규칙:**
- 첫 번째 태그는 항상 `YouTube`
- 영상 주제에 맞는 태그를 obsidian:note의 태그 목록에서 선택
- 영상에 등장하는 구체적 기술 키워드도 태그로 추가

### Step 5 — 결과 출력

스크립트의 JSON 응답을 파싱 후 사용자에게 출력:

```
YouTube 영상 요약이 Obsidian에 저장되었습니다.
- 제목: {title}
- 태그: {tags}
- 날짜: {date}
- 파일: {filename}
- 관련 노트: {related_count}개 링크됨
```

## 에러 처리

| 상황 | 대응 |
|------|------|
| 자막 없는 영상 | "이 영상에는 사용 가능한 자막이 없습니다" 안내 |
| 잘못된 URL | "유효한 YouTube URL을 입력해주세요" 안내 |
| yt-dlp 미설치 | "pip install yt-dlp를 실행해주세요" 안내 |
| 네트워크 오류 | 에러 메시지 전달 |
