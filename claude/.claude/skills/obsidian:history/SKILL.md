---
name: obsidian:history
description: |
  Claude와의 문제 해결 대화를 분석하여 Obsidian 히스토리 노트로 아카이빙하는 스킬.
  사용 시점: (1) 장애 해결 후 사례 기록, (2) 트러블슈팅 완료 후 아카이빙,
  (3) 복잡한 디버깅 과정 보존.
  트리거 키워드: "히스토리 저장", "사례 아카이빙", "history 저장", "/obsidian:history".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py *)
  - Write(/tmp/obsidian-content.json)
---
# obsidian:history Skill

Claude와의 문제 해결 대화를 구조화된 히스토리 노트로 아카이빙하고 `02. Notes/history/`에 저장한다.

## 핵심 원칙

- **과정 중심**: 결과만이 아닌 시도·실패·전환점을 포함한다
- **시간순 보존**: 발견 → 조사 → 해결 흐름을 타임라인으로 기록한다
- **실패도 자산**: "왜 안 됐는지"가 다음 엔지니어의 시간을 아껴준다
- **재현 가능성**: 구체적인 명령어·설정·환경 정보를 포함한다

## 노트 템플릿

### 필수 섹션

| 섹션 | 내용 |
|------|------|
| `## Summary` | 1-3줄 요약 |
| `## 환경 컨텍스트` | 클러스터, 서비스, 버전, 시점 |
| `## 문제 상황` | 증상, 영향 범위, 발견 경위 |
| `## 타임라인` | 발견 → 조사 → 해결 시간순 |
| `## 시도한 접근들` | 각 접근의 가설/실행/결과 (실패 포함) |
| `## 해결` | 최종 해결책, 변경사항, 검증 방법 |
| `## 배운 것과 앞으로` | takeaway, 재발 방지, 후속 작업 |
| `## 관련 리소스` | PR, Grafana, Slack 링크 등 |

### 선택 섹션 (대화에서 해당 내용이 있을 때만 포함)

- `## 관측 데이터` — 메트릭/로그 분석이 있었을 때
- `## Root Cause Analysis` — 근본 원인 분석이 있었을 때
- `## 변경 내역` — 설정 변경 diff가 있었을 때

**제목 규칙**: `[서비스/영역] 증상 요약` 형식 (날짜 prefix 없음)
- 예: `Santa Gateway 503 에러 폭증 해결`
- 예: `Istio 1.28 업그레이드 후 Ingress Gateway 메트릭 누락`

## 워크플로우

### Mode A — 즉시 저장 (현재 대화 기반)

#### Step 1 — 대화 분석 및 서사 추출

현재 대화를 분석하여 문제 해결 서사를 추출한다:
- 어떤 증상이 있었는가?
- 어떤 환경/서비스에서 발생했는가?
- 어떤 접근들을 시도했는가? (실패 포함)
- 어떻게 해결했는가?
- 무엇을 배웠는가?

문제 해결 과정이 없으면 (개념 학습 대화 등) 사용자에게 알리고 중단한다.
개념 학습은 `obsidian:note` 스킬을 사용하도록 안내한다.

#### Step 2 — 구조화된 마크다운 작성

템플릿에 따라 노트 본문을 작성한다:
- 필수 섹션 전체 포함
- 선택 섹션은 대화에서 해당 내용이 있을 때만 포함
- `---` 수평선 사용 금지
- 헤딩에 `--` 사용 금지

#### Step 3 — 제목과 태그 결정

- 제목: `[서비스/영역] 증상 요약` 형식
- 태그: 관련 domain/ 태그 (예: `kubernetes,istio,observability`)

#### Step 4 — 노트 파일 작성

```bash
# 1. 본문 파일 작성
# Write 도구로 /tmp/obsidian-content.json 에 {"blocks": "...마크다운 본문..."} 형태로 저장

# 2. obsidian-note.py로 노트 생성
python3 /Users/changhwan/.claude/skills/obsidian:note/scripts/obsidian-note.py create \
  --title "[서비스/영역] 증상 요약" \
  --tags "tag1,tag2" \
  --type "history" \
  --content-file /tmp/obsidian-content.json
```

#### Step 5 — 결과 보고

스크립트 출력에서 `filepath`를 추출하여 저장 경로를 보고한다.

### Mode B — 과거 대화 기반 저장

#### Step 1 — 대상 세션 식별

사용자가 어떤 사례인지 설명한다. 또는:

```
claude-mem search로 관련 observation 검색
claude-mem timeline으로 해당 날짜 세션 수집
```

정보가 부족하면 사용자에게 보충 질문한다. 무리하게 채우지 않는다.

#### Step 2 — 서사 재구성

수집된 observation들로 문제 해결 서사를 재구성한 후 Mode A의 Step 2-5와 동일하게 진행한다.

## 결과 출력 형식

```
히스토리 노트가 저장되었습니다.

- 제목: {title}
- 경로: 02. Notes/history/{filename}
- 태그: {tags}
- 관련 노트: {related_count}개 wikilink 추가됨
```

## 가드레일

- 대화에 문제 해결 과정이 없으면 사용자에게 알리고 중단
- 개념 학습 대화는 `obsidian:note` 사용 안내
- `---` 수평선 금지, 헤딩에 `--` 금지
- Mode B에서 정보가 불충분하면 무리하게 채우지 말고 사용자에게 질문
