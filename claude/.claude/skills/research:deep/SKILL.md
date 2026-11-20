---
name: research:deep
description: |
  공식 문서·공개 코드·논문·이미지를 넓게 수집해 원문 스냅샷과 주장 원장을 만들고, codex로 주장과 초안을 두 번 교차 검증한 뒤 Claude Docs 보고서로 정리하는 심층 리서치 스킬. 실제로 읽은 데이터 양을 기록 기반으로 브리핑한다.
  사용 시점: (1) 한 문제를 깊게 파서 근거가 검증된 보고서가 필요할 때, (2) 공식 문서·코드·논문을 함께 근거로 써야 할 때, (3) 다른 모델의 교차 검증이 필요할 때. 빠른 조사는 research 스킬을 쓴다.
  트리거 키워드: "심층 리서치", "딥 리서치", "deep research", "교차 검증 리서치", "research:deep", "/research:deep".
model: opus
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/research:deep/scripts/manifest.py *)
  - Bash(python3 /Users/changhwan/.claude/skills/research:deep/scripts/codex_verify.py *)
  - Agent
  - Read
  - Write
  - Edit
  - Grep
  - WebSearch
  - WebFetch
  - Artifact
  - mcp__claude_ai_Claude_Docs__batch
  - mcp__claude_ai_Claude_Docs__update
  - mcp__claude_ai_Claude_Docs__create
  - mcp__claude_ai_Claude_Docs__read
  - mcp__claude_ai_Claude_Docs__query
  - mcp__claude_ai_Claude_Docs__guide
---
# research:deep Skill

질문 하나를 서브질문으로 나눠 병렬 수집하고, 원문 인용이 붙은 주장 원장을 codex로 검증한 뒤, 검증된 주장만으로 쓴 초안을 codex로 다시 검증해 Claude Docs 보고서로 게시한다.

```
분해 → 문서 골격 → 병렬 수집 → 수집 브리핑 → 주장 원장 → codex 주장 검증 → 재판정
→ 로컬 초안 → codex 초안 검증 → Claude Docs 게시 → 검증
```

---

## 핵심 원칙

- **원문이 기준이다**: 모든 소스는 `manifest.py source`로 원문 스냅샷을 먼저 저장한다. 주장의 `quote`는 스냅샷에 그대로 있어야 하며, `ledger`가 기계적으로 대조해 맞지 않으면 버린다
- **블라인드 교차 검증**: codex에는 주장·URL·스냅샷 경로만 준다. 우리 인용·등급·확신을 주지 않는다. codex는 반드시 `codex_verify.py`로 부른다(셸 alias `--dangerously-bypass-approvals-and-sandbox`를 거치지 않고 `-s read-only`로 실행됨)
- **검증된 주장만 쓴다**: 보고서 본문은 SUPPORTED 주장과 조건을 반영한 PARTIAL 주장만 근거로 쓴다. REFUTED·UNVERIFIABLE은 제외하거나 "소스 상충"으로 표기한다
- **숫자는 기록에서**: 수집량·판정 수는 `manifest.py stats` 출력만 쓴다. 어림잡은 숫자를 쓰지 않는다
- **문서는 먼저, 이미지는 마지막**: Claude Docs 골격은 분해 직후 만든다. 이미지 업로드는 승인 카드가 뜨므로 글을 모두 채운 뒤 한 번에 올린다
- 보고서 문체: `~/.claude/docs/notion-writing-style.md`. 채팅 응답: 한국어 격식체

`M=/Users/changhwan/.claude/skills/research:deep/scripts/manifest.py`
`V=/Users/changhwan/.claude/skills/research:deep/scripts/codex_verify.py`

---

## 워크플로우

### Step 0: 질문 분해 (도구 호출 없이)

- 질문을 서브질문 3~5개로 나눈다. 각 서브질문에 핵심 질문 2~4개, 찾을 소스 종류(`official`/`code`/`paper`/`blog`), 공식 도메인을 정한다
  - 축 예시: 정의·동작 원리 / 버전 변화·현재 상태 / 구현(코드) / 연구·성능 근거(논문) / 운영 사례·함정
- 용어·범위가 모호해 수집 방향이 갈리면 AskUserQuestion으로 먼저 묻는다(그 외에는 묻지 않는다)
- 보고서 제목: 질문을 6단어 안팎으로, slug는 영문 소문자·하이픈

### Step 1: Claude Docs 골격

1. Claude Docs 서버 지침이 컨텍스트에 없으면 `guide(items=["topic.instructions"])`를 먼저 부른다
2. birth batch: `assets/report-outline.md`의 블록 표대로 만든다. 첫 Claude Docs 호출이 이것이어야 한다
   ```
   batch(container={"kind":"project","create":{"name":"<제목>","doc":{
     "blocks":{"asof":{"type":"date","value":"<오늘>"},"me":{"type":"mention","user":"me"},
               "s0":{"type":"pending","intent":"요약: ..."},"q1":{"type":"pending","intent":"<서브질문 1>: 수집·검증 중"}, ...},
     "markdown":"# <제목>\n\n<?claude block asof?> · <?claude block me?>\n\n<?claude block s0?>\n\n<?claude block q1?>..."}}},
     batch=[])
   ```
3. ack의 문서 링크(`frame.url`)를 `Artifact(action="open", url=<link>)`로 연다. 다음 값을 기록해 둔다
   - 문서 id: `created.minted`(UUID). 이후 모든 호출의 `container.id`다. `lids.f`는 탭 id라 container로 쓰면 거부된다
   - 본문 node id: `lids.n`. `update`의 `ref.id`다
   - pending 블록 전체 id: `<session>.<keys의 번호>`(예: `m3pczkcs17t.44`)
4. `guide(items=["topic.editing"])`를 부른다. `topic.index`는 7만 자가 넘어 결과가 잘리므로 메인 컨텍스트에서 부르지 않는다(필요하면 Explore 에이전트에게 저장 파일을 요약시킨다)
5. 실행 폴더를 만든다
   ```bash
   python3 $M init <slug> --question "<원 질문>"
   ```
   출력 경로가 `{run_dir}`이다. `run.json`에 문서 링크와 node id를 Edit로 덧붙인다
6. 채팅에 한 줄: 문서를 열었고 수집을 시작한다는 것

### Step 2: 병렬 수집

1. `agents/agent-researcher.md`를 Read하고 변수를 치환한다: `{run_dir}`, `{subq_id}`, `{subq}`, `{source_types}`, `{official_domains}`, `{version_anchor}`
2. 버전이 답을 좌우하는 주제면 공식 releases 페이지를 `manifest.py source`로 1회 저장해 최신 버전과 날짜를 확정하고 `{version_anchor}`에 넣는다
3. 서브질문마다 리서처 1개를 **한 메시지에서 동시에** 실행한다
   ```
   Agent(subagent_type="general-purpose", model="sonnet", description="Research <subq_id>", prompt=<치환된 agent-researcher.md>)
   ```
4. 모두 끝나면 `notes/*.md`의 `## 빈 곳`을 본다. 핵심 질문의 절반 이상이 비면 그 서브질문만 리서처를 1회 더 실행한다(추가 라운드는 1회까지)

### Step 3: 수집 브리핑 (MUST)

```bash
python3 $M stats {run_dir}
```

채팅에 표를 그대로 보여 준다. 연 URL 대비 원문 확보 비율, 종류·등급별 수, 추출 텍스트 분량, 이미지 수를 한두 줄로 해석한다(예: "T1이 n개로 공식 근거는 충분하고, 논문은 m개뿐이다").

### Step 4: 주장 원장

1. 합치고 원문 대조
   ```bash
   python3 $M ledger {run_dir}
   ```
   `claims.rejected.jsonl`(quote 불일치)은 버린다. 핵심 근거가 거기 몰려 있으면 해당 스냅샷을 Read해 quote를 원문 그대로 고쳐 notes에 다시 넣고 `ledger`를 재실행한다
2. `claims.jsonl`을 Read해 정리한다(Edit)
   - 질문과 무관한 주장, 같은 사실의 중복(같은 출처의 같은 문장)만 지운다. 상충 쌍은 둘 다 남긴다
   - 건수 상한은 두지 않는다. 수집한 근거를 줄이는 단계가 아니다. 200건을 넘으면 codex 청크 수(15건 단위)와 예상 시간을 채팅에 한 줄로 알리고 진행한다
   - 공식 문서·코드의 사용 예시(YAML, 명령)도 원문 그대로 quote에 넣어 주장으로 남긴다. 보고서의 "사용 예시" 섹션이 이 주장만 쓴다
   - `claim_id`는 다시 매기지 않는다

### Step 5: codex 주장 검증 → 재판정

1. 백그라운드로 실행하고 완료 알림을 기다린다(15건 단위 청크, 4개 병렬, 청크당 1~5분)
   ```bash
   python3 $V claims {run_dir}      # Bash run_in_background=true
   ```
2. 판정 인용이 원문에 있는지 확인한다(codex가 실제로 읽었는지의 증거)
   ```bash
   python3 $M check-verdicts {run_dir} --verdict SUPPORTED
   ```
   `found_ratio`가 0.8 미만이면 해당 청크를 `--only`로 재검증한다(`--start-index`를 기존 청크 수 + 1로)
3. 재판정: `PARTIAL`·`REFUTED`·`UNVERIFIABLE`마다 Claude가 스냅샷의 해당 부분과 codex `counter_evidence`를 직접 읽고 결정한다
   - codex가 맞으면: PARTIAL은 조건을 넣어 주장을 고치고, REFUTED는 제외한다
   - codex가 틀렸으면(원문에 근거가 있음): 근거 문장을 들어 채택한다
   - 둘 다 근거가 있으면: "소스 상충"으로 남긴다
   - `counter_evidence` URL을 근거로 쓰려면 `manifest.py source`로 저장하고, 쓸 문장을 원문 그대로 quote로 붙인 새 주장으로 `claims.jsonl`에 추가한 뒤 `codex_verify.py claims --only <새 id들> --start-index <기존 청크 수 + 1>`로 검증한다. 검증하지 않은 근거는 초안에 쓰지 않는다
   - 결정을 `{run_dir}/adjudication.md`에 `claim_id | codex 판정 | 결론 | 근거` 한 줄씩 남긴다
4. 채팅에 한 줄: 판정 분포와 재판정 건수

### Step 6: 로컬 초안 (본문은 전부, 핵심은 요약에)

1. 핵심 추출은 요약 섹션의 일이다. 본문은 채택 대상 주장(SUPPORTED, 조건을 반영한 PARTIAL, 재판정으로 채택한 주장)을 **모두** 서브질문별로 쓴다. 주장을 버리는 단계가 아니다
   - 같은 결론을 받치는 주장은 한 문장에 묶고 인용을 여러 개 붙인다(`[@c012] [@c047]`)
   - 쓰지 않을 주장은 `adjudication.md`에 `cNNN | <판정> | 미사용 | <사유>`로 남긴다(예: 다른 주장과 완전히 같은 내용, 질문과 무관)
   - 초안의 사실 문장은 반드시 `claims.jsonl`에 있고 검증을 통과한 주장으로만 쓴다. 원장에 없는 사실이 필요하면 먼저 원장에 추가하고 `--only`로 검증한다
2. `{run_dir}/draft.md`를 Write한다. 구조와 섹션 규칙은 `assets/report-outline.md`를 따르고, 인용은 주장 id `[@cNNN]`로 쓴다(번호는 render가 출처 단위로 매긴다)
3. 반영률을 확인한다. 90% 미만이면 `본문에 쓰지 않은 채택 대상 주장` 목록을 본문에 넣거나 `미사용` 사유를 남긴다
   ```bash
   python3 $M stats {run_dir}      # "보고서 반영률" 행과 미사용 목록
   ```
4. 그림 후보: `notes/*.md`의 `## 시각자료`와 `images.jsonl`의 `embed:true`만 본문 삽입 대상이다. 초안에는 `<!-- image: i... after: <문장 앞부분> -->` 주석으로 위치만 표시한다
5. 도식이 필요한 곳(흐름·상태·구조·단계가 핵심인 서브질문)은 `<!-- diagram: <무엇을 그릴지> -->`로 표시한다

### Step 7: codex 초안 검증 → 반영

```bash
python3 $V draft {run_dir}      # Bash run_in_background=true
```

1. `{run_dir}/draft-review.json`의 `issues`를 하나씩 확인해 `draft.md`를 고친다. 지적이 틀렸다고 판단하면 고치지 않고 이유를 `adjudication.md`에 남긴다
2. `unsourced`·`uses_refuted`를 3건 넘게 고쳤으면 `draft` 검증을 1회 더 돌린다
3. 번호 인용으로 변환한다
   ```bash
   python3 $M render {run_dir}
   ```
   `unknown_source_ids`와 `unknown_claim_ids`가 비어 있어야 한다

### Step 8: Claude Docs 게시

1. 섹션마다 `update` 1회로 pending 블록을 채운다(`assets/report-outline.md`의 블록 순서). 채우기 전에 채팅에 한 줄로 어느 섹션인지 알린다
   ```
   update(ref={"object":"node","id":"<lids.n>"}, engine="prose", container={"kind":"project","id":"<created.minted>"},
     payload={"ops":[{"op":"replace","target":{"kind":"blocks","ids":["<session>.<n>"]},
       "with":{"from":{"kind":"inline","content":"## <제목>\n\n- ..."},"as":"markdown"}}]})
   ```
   - 내용은 `final.md`의 해당 섹션(이미지·도식 주석 제외), 출처는 `references.md`, 수집 브리핑은 `manifest.py stats` 최신 출력
2. 도식: `guide(items=["topic.diagram"])`를 읽고, 초안의 `diagram` 주석마다 widget 1개를 만들어 해당 블록 뒤에 embed한다. 만든 뒤 `read(... payload={"kind":"screenshot"})`로 렌더를 확인한다
3. 이미지(모든 pending이 채워진 뒤): `guide(items=["topic.uploads"])`를 읽고
   - `Artifact(action="publish", url=<문서 링크>, asset=true, file_paths=[<{run_dir}/images/...>, ...])`로 한 번에 올린다(승인 1회)
   - 반환된 asset id마다 `create(object="blob", engine="blob", container=C, payload={"asset":"<id>"})`
   - 초안 주석 위치의 블록 뒤에 `![<캡션>](blob/<id>)`와 `그림: <설명> · [출처](<page>) (<license>)`를 insert
   - 업로드를 거절당하면 이미지 없이 `관련 그림: [<설명>](<page>)` 링크로 대신한다
4. 수집 브리핑을 다시 계산해 숫자를 확정한다: 출처 섹션까지 채운 뒤 `python3 $M stats {run_dir}`의 "초안 인용 출처"가 `references.md` 줄 수와 같아야 한다

### Step 9: 검증 (MUST)

- [ ] 문서를 outline으로 `read`해 pending 블록이 0개다
- [ ] 본문 인용 번호의 최댓값이 출처 목록 개수와 같고, 출처 목록의 모든 항목이 본문에서 한 번 이상 인용됐다
- [ ] 업로드한 이미지가 모두 문서에 보인다(blob 참조 수 = 업로드 수)
- [ ] 수집 브리핑 표가 `manifest.py stats` 출력과 같다
- [ ] REFUTED·UNVERIFIABLE 주장이 본문 근거로 쓰이지 않았다(`stats`의 "채택 대상이 아닌데 인용된 주장"이 없음)
- [ ] `stats`의 보고서 반영률이 90% 이상이다. 미만이면 Step 6으로 돌아간다
- [ ] em dash(U+2014)가 없다

통과하면 채팅에 2~3줄로 끝낸다: 문서 링크, 수집량 한 줄(원문 확보 n / 시도 m, 텍스트 약 k자, 이미지 i개), 검증 한 줄(주장 K건 중 채택 a, 상충 c, 제외 d, 보고서 반영률 r%). 문서 내용을 채팅에 붙이지 않는다.

---

## 주의사항

- codex 호출은 Bash 포그라운드 한도(600초)를 넘기 쉬우므로 반드시 `run_in_background=true`로 실행하고 완료 알림을 기다린다. 폴링하지 않는다
- 실행 폴더는 `~/.claude/research-runs/<날짜>-<slug>/`에 남는다. 재검증·감사에 쓰이므로 지우지 않는다
- 웹 공개 자료 전용이다. 사내 문서(Slack·Notion·devops-wiki)는 수집하지 않는다
- 유료·로그인 필요 논문은 초록 페이지만 저장하고 본문 주장의 근거로 쓰지 않는다
- 조사 1회에 리서처 서브에이전트 3~5개와 codex 호출 여러 번이 든다. 질문 하나에 답 하나면 `research` 스킬로 충분하다
