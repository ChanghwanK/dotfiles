---
name: email:reply
description: |
  외부 CSP/AWS/Hostway IDC 등 인프라 벤더 이메일을 Gmail에서 검색·분석하여 한국어 기반 답변 초안을 자동 작성하고 Gmail Draft로 저장.
  Gmail URL 또는 검색어로 스레드 로드 → 분석 → 초안 생성 → 사용자 확인 → Draft 저장.
  사용 시점: (1) AWS/CSP 기술 지원 이메일 답변, (2) Hostway IDC 관리자 소통, (3) 외부 벤더 계약·청구 대응.
  트리거 키워드: "이메일 답장", "메일 답변", "email reply", "email:reply", "/email:reply".
model: sonnet
allowed-tools:
  - Read
  - mcp__claude_ai_Gmail__search_threads
  - mcp__claude_ai_Gmail__get_thread
  - mcp__claude_ai_Gmail__create_draft
  - mcp__claude_ai_Gmail__list_labels
  - mcp__claude_ai_Gmail__label_thread
  - AskUserQuestion
---

# email:reply

Gmail에서 외부 벤더 이메일을 읽어 한국어 답변 초안을 작성하고 Draft로 저장한다.

---

## 핵심 원칙

- **Draft-only**: Gmail MCP는 전송 미지원 — 항상 Draft 저장, 사용자가 Gmail에서 직접 전송
- **한국어 기본**: 답변은 한국어 작성. 순수 해외 CS 포털(AWS/GCP Support 티켓 시스템)만 영어 예외
- **수정 루프**: 사용자가 승인할 때까지 재생성 반복 — 횟수 제한 없음
- **SOCRAAI 컨텍스트**: 인프라 스택(EKS, IDC, VPC 등) 지식을 답변에 반영

---

## 워크플로우

### Phase 1 — 이메일 로드

입력 유형을 판별하여 스레드를 로드한다.

**Mode A — Gmail URL 입력 (우선)**
```
사용자: "https://mail.google.com/mail/u/0/#inbox/FMfcgzGtwXjKvBzR 이 메일 답변해줘"

→ URL fragment에서 thread ID 추출
    패턴: /#inbox/{id}, /#all/{id}, /#label/{label}/{id}
→ mcp__claude_ai_Gmail__get_thread(id=추출된_id) 직접 호출
```

**Mode B — 검색어 입력**
```
사용자: "AWS enterprise support에서 온 최근 메일 답변해줘"

→ mcp__claude_ai_Gmail__search_threads(
     query="from:aws.amazon.com OR from:amazonaws.com",
     maxResults=5
   )
→ 결과 1개: 자동 선택
→ 결과 여러 개: AskUserQuestion으로 선택
→ mcp__claude_ai_Gmail__get_thread(id=선택된_id)
```

### Phase 2 — 스레드 분석

스레드 데이터에서 다음을 추출한다.

```
발신자 분류:
  AWS (amazon.com, amazonaws.com, aws.amazon.com)
  Hostway IDC (hostway.co.kr, hostway.com)
  CSP (google.com, azure.com, gcp...)
  기타 벤더

요청 유형: 기술 지원 | 청구/계약 | 유지보수 안내 | 일반 문의
긴급도: 즉시 대응 | 일반 | 정보성

언어 판별 (references/reply-guidelines.md 참조):
  한국 기업 도메인 → 한국어
  상대방이 한국어 사용한 적 있음 → 한국어
  순수 해외 CS 포털 → 영어
  그 외 → 한국어 기본
```

### Phase 3 — 답변 초안 생성

`references/reply-guidelines.md`의 벤더별 가이드를 참조하여 답변을 작성한다.

```
Read /Users/changhwan/.claude/skills/email:reply/references/reply-guidelines.md

초안 구조:
  제목: Re: {원본 제목}
  수신: {발신자 이메일}
  본문:
    - 인사 (벤더 유형별 톤)
    - 핵심 요구사항 순서대로 답변
    - 다음 액션 또는 추가 확인 사항
    - 서명: 창환 / Changhwan | DevOps Engineer, SOCRA AI | claude3@socra.ai
```

사용자에게 출력:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[발신자] {이름} <{이메일}>
[유형]   {분류} / {요청 유형}
[긴급도] {긴급도}
[언어]   {한국어 / 영어}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

제목: Re: {원본 제목}

{생성된 본문}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이 내용으로 Gmail Draft에 저장할까요?
수정이 필요하면 내용을 알려주세요.
```

### Phase 4 — Draft 저장 (사용자 승인 후)

```
mcp__claude_ai_Gmail__create_draft(
  to=발신자_이메일,
  subject="Re: {원본_제목}",
  body=생성된_답변,
  threadId=원본_스레드_ID   ← 스레드 연결
)

완료 후 출력:
"Gmail Draft에 저장했습니다.
 Gmail Drafts 탭에서 확인 후 전송해 주세요."

선택: AskUserQuestion으로 레이블 적용 여부 확인
      (예: "Replied" 레이블로 처리 완료 표시)
```

---

## 주의사항

- 스레드 전체를 읽어야 맥락이 파악됨 — 최신 메시지만 보지 말 것
- create_draft의 threadId 누락 시 새 대화로 저장됨 (답장이 아님)
- AWS Support 케이스 번호, Hostway 티켓 번호는 답변에 반드시 포함
- 개인정보(계정 ID, 비밀번호 등)는 이메일 본문에 절대 포함하지 않음
