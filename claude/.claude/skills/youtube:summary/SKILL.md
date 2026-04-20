---
name: youtube:summary
description: |
  YouTube 영상의 자막을 추출하여 심층 요약/분석 후 Obsidian 노트로 저장하는 스킬.
  영상 URL을 입력하면 자막 추출 → 요약 → 핵심 포인트 → 인사이트 분석 → Obsidian 저장.
  사용 시점: (1) 시청한 영상의 핵심을 빠르게 정리, (2) 기술 컨퍼런스/튜토리얼 영상 학습 노트화,
  (3) DevOps 관련 영상에서 실무 적용점 추출.
  트리거 키워드: "유튜브 요약", "영상 요약", "youtube summary", "/youtube:summary".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/youtube:summary/scripts/yt-extract.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py *)
  - Read(/Users/changhwan/.claude/skills/youtube:summary/assets/template.md)
  - Read(/tmp/yt-extract-result.json)
  - Write(/tmp/yt-extract-result.json)
  - Write(/tmp/obsidian-content.json)
---

# YouTube Summary Skill

YouTube 영상의 자막을 추출하여 구조화된 요약 + 심층 분석을 수행하고 Obsidian 노트로 저장한다.

## 워크플로우

### Step 1 — URL 확인

- 사용자로부터 YouTube URL 수신
- URL 형식 검증 (`youtube.com/watch?v=` 또는 `youtu.be/`)
- 유효하지 않으면 `유효한 YouTube URL을 입력해주세요 (예: https://youtu.be/XXX)` 메시지로 재입력 요청 후 중단

### Step 2 — 자막 + 메타데이터 추출

```bash
python3 /Users/changhwan/.claude/skills/youtube:summary/scripts/yt-extract.py extract "<URL>"
```

- `/tmp/yt-extract-result.json` 읽어서 결과 확인
- `success: false`이면 에러 메시지를 사용자에게 전달하고 중단
- `metadata_warning` 필드가 있으면 사용자에게 경고 표시 후 진행 (yt-dlp 미설치 → 메타데이터 제한)
- 자막 우선순위: `ko` → `en` → `ko(auto)` → `en(auto)`

### Step 3 — 요약 및 분석 생성

자막 텍스트(`transcript` 필드)를 기반으로 **반드시 한국어**로 분석을 생성한다.

**출력 템플릿:** `~/.claude/skills/youtube:summary/assets/template.md` 참조 (Read로 로드).

**생성 규칙:**
- 출력 언어는 **반드시 한국어** (영어 자막이라도 번역하여 분석)
- 기술 용어는 원문을 병기 (예: "서비스 메시(Service Mesh)")
- `실무 적용점` 섹션은 DevOps/인프라 관련 내용일 때만 포함, 아니면 생략
- `인상적인 인용/구절`은 자막에서 직접 발췌 (번역 시 원문 병기)
- `인사이트`는 영상의 정보를 내재화한 해석 — 시청자(DevOps Engineer) 관점에서 "So what?"에 답하는 내용
- `추천 Action Items`는 당장 실행 가능한 수준의 구체적 행동. 추상적 목표("더 공부하자") 금지, 구체적 행동("X 문서를 읽고 Y를 시도해보기")으로 작성
- `인사이트`와 `추천 Action Items`는 영상 주제와 무관하게 **반드시 포함** (DevOps 비관련 영상이라도 개인 성장/사고방식 관점에서 작성)

### Step 4 — Obsidian 노트 저장

1. Step 3에서 생성한 마크다운 본문(제목 `#` 헤딩 제외)을 **순수 텍스트**로 `/tmp/obsidian-content.txt`에 Write:
   - JSON 인코딩 절대 금지 — 마크다운을 그대로 저장 (따옴표, 역슬래시 이스케이프 없이)
   - `{`, `}`, `"blocks"` 등 JSON 구조 포함 금지
   - 메타정보 blockquote(`> **채널**:...`)부터 관련 키워드 섹션까지 완성된 마크다운

2. 기존 `obsidian:note` 스크립트 호출:
```bash
python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py create \
  --title "[영상제목] 유튜브 요약" \
  --tags "YouTube,태그1,태그2" \
  --content-file /tmp/obsidian-content.txt
```

**태그 규칙:**
- 첫 번째 태그는 **반드시** `YouTube`
- 영상 주제에 맞는 태그를 obsidian:note의 태그 목록에서 선택
- 영상에 등장하는 구체적 기술 키워드도 태그로 추가

### Step 5 — 결과 검증 및 출력

obsidian-note.py 응답의 `success` 필드를 **반드시 확인**한다.

- `success: false` → 에러 메시지(`error` 필드)를 사용자에게 전달하고 중단. 성공 메시지 출력 금지.
- `success: true` → 아래 형식으로 출력:

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
| 잘못된 URL | "유효한 YouTube URL을 입력해주세요 (예: https://youtu.be/XXX)" 안내 |
| yt-dlp 미설치 | "pip install yt-dlp를 실행해주세요" 안내 |
| 메타데이터 경고 | `metadata_warning` 필드 있으면 사용자 안내 후 진행 |
| Obsidian 저장 실패 | obsidian-note.py 응답의 `error` 필드 전달 후 중단 |
| 네트워크 오류 | 에러 메시지 전달 |
