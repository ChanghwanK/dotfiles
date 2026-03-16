---
name: tasks:ing-listup
description: |
  오늘 실제 수행한 작업을 Claude 세션 기반으로 요약하는 읽기 전용 스킬.
  전 세션 transcript + claude-mem timeline + 현재 세션 분석 + Obsidian Daily Note를
  결합하여 프로젝트별 작업 리포트를 출력한다.
  사용 시점: (1) 오늘 뭐 했는지 정리, (2) 세션 간 작업 요약, (3) 일일 작업 리포트 확인,
  (4) handoff 전 작업 현황 파악, (5) daily:review 전 내용 수집.
  트리거 키워드: "오늘 뭐 했지", "작업 리포트", "ing listup", "오늘 작업 정리",
  "tasks:ing-listup", "지금까지 한 일", "오늘 한 일".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py *)
  - Read
  - mcp__plugin_claude-mem_mcp-search__timeline
  - mcp__plugin_claude-mem_mcp-search__search
---

# tasks:ing-listup

오늘 실제 수행한 작업을 **Claude 세션 데이터 기반**으로 요약한다. "뭘 해야 하는가"(tasks:show)가 아닌 **"뭘 했는가"** 관점.

---

## 핵심 원칙

- **읽기 전용** — 어떤 데이터도 수정하지 않는다
- **"한 일" 중심** — 계획이 아닌 실제 수행 기록 기반
- **병렬 수집** — 4개 소스를 단일 메시지에서 동시 호출하여 속도 최적화
- **LLM 요약** — 원본 데이터 JSON 출력 금지, 반드시 자연어로 요약

---

## 역할 구분

| 스킬 | 관점 |
|------|------|
| `tasks:show` | "뭘 해야 하는가" (계획) |
| **`tasks:ing-listup`** | **"뭘 했는가" (실행)** |
| `daily:review` | "어떻게 했는가" (KPT 회고) |
| `handoff:pause` | "어디까지 했고 다음은" (저장) |

---

## 워크플로우

### Step 1 — 4개 소스 병렬 수집

아래 4개를 **단일 메시지에서 동시 호출**한다 (순차 금지).

**소스 1: 다른 세션 transcript (Bash)**
```bash
python3 /Users/changhwan/.claude/skills/daily:start/scripts/extract-work.py --date today
```
오늘 날짜의 모든 프로젝트 JSONL transcript에서 user 메시지 추출. 에러 시 해당 소스 생략.

**소스 2: claude-mem timeline (MCP)**

`mcp__plugin_claude-mem_mcp-search__timeline` 도구를 호출하여 오늘 날짜의 구조화된 관찰 기록(완료 작업, 의사결정, 발견 사항)을 가져온다.

**소스 3: 현재 세션 (LLM 자체 분석)**

현재 대화 컨텍스트에서 오늘 수행한 작업을 직접 분석한다. 가장 최신 상태 반영.

**소스 4: Obsidian Daily Note (Read)**

오늘 날짜의 Daily Note를 읽어 계획된 항목을 파악한다:
```
/Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/YYYY-MM-DD.md
```
(YYYY-MM-DD를 오늘 날짜로 치환. 파일 없으면 해당 섹션 생략)

---

### Step 2 — 프로젝트별 그룹핑 & LLM 요약

수집한 데이터를 분석하여:

1. **프로젝트별 그룹핑**: extract-work.py의 `project` 필드 기준. 프로젝트 불명확 시 키워드로 추론
   - `riiid-kubernetes`, `kubernetes` → `riiid-kubernetes`
   - `engineering101` → `engineering101`
   - `terraform` → `riiid-terraform`
   - 공통 prefix 없이 `/workspace/riiid/` 하위 → 리포명 사용

2. **작업 상태 분류**:
   - `✅ 완료`: 명확히 마무리된 작업 (문서 저장됨, 이슈 해결됨, 기능 구현됨 등)
   - `🔄 진행 중`: 현재 세션에서 활성 작업, 또는 명시적 완료 없는 작업

3. **요약 원칙**:
   - 각 항목은 1줄 이내로 핵심 동작 + 결과 표현
   - 기술 용어는 그대로 유지 (ArgoCD, CNPG, Karpenter 등)
   - 중복 제거 (여러 소스에서 같은 작업 언급 시 1건으로 통합)

---

### Step 3 — 포맷팅 출력

아래 형식으로 출력한다:

```
📊 오늘의 작업 리포트 ({YYYY-MM-DD} {HH:MM} 기준)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 {프로젝트명} ({N}건)
  ✅ {완료된 작업 요약}
  🔄 {진행 중인 작업 요약}

🔹 {프로젝트명2} ({N}건)
  ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 총 {N}건 | 완료 {N}건 | 진행 중 {N}건

📋 계획 대비 실행 (Daily Note 기반)   ← Daily Note 없으면 이 섹션 생략
  - [x] {계획 항목} ✅
  - [ ] {계획 항목} — 미착수
  진행률: {완료}/{전체} ({퍼센트}%)
```

---

## Edge Cases

| 상황 | 처리 방법 |
|------|----------|
| extract-work.py 오류 | 해당 소스 생략, 나머지 소스로 진행 |
| claude-mem timeline 응답 없음 | 해당 소스 생략 |
| Daily Note 파일 없음 | "계획 대비 실행" 섹션 생략 |
| 오늘 작업 데이터가 전혀 없음 | "오늘 아직 수집된 작업 데이터가 없습니다" 출력 후 현재 세션 작업만 표시 |
| 현재 세션이 유일한 소스 | 현재 세션 분석 결과만으로 리포트 구성 |

---

## 주의사항

- 데이터 수정/쓰기 절대 금지 (읽기 전용)
- JSON 원본 데이터 출력 금지
- `tasks:show`와 혼동 금지 — 이 스킬은 "한 일" 조회, tasks:show는 "할 일" 조회
