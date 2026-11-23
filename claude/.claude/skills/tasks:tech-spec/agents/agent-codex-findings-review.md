# codex 수집 결과 검토·흡수 에이전트 (Claude)

```
{research_run} : research:deep 실행 폴더 절대 경로
```

codex가 같은 서브질문을 독립적으로 수집한 결과(`{research_run}/codex/collect-<qN>.json`)를 검토한다. 목표는 둘이다.
1. codex 결과의 오류를 걸러낸다(원문에 없는 인용, 과장된 주장, 버전 불일치)
2. Claude 수집에 없던 사실을 원장으로 흡수해 자료를 보완한다

`M=/Users/changhwan/.claude/skills/research:deep/scripts/manifest.py`

## 절차

1. `{research_run}/claims.jsonl`의 `claim`·`url`을 훑어 Claude 쪽이 이미 가진 사실을 파악한다
2. `codex/collect-*.json`의 finding마다:
   - 같은 사실이 이미 원장에 있으면(같은 URL·같은 내용) `중복`으로 기록하고 넘어간다
   - 없으면 URL을 원문 저장한다. 이미 `sources/`에 같은 URL이 있으면 그 source_id를 재사용한다
     ```bash
     python3 $M source {research_run} "<url>" --type <official|code|blog|paper> --tier <T1|T2|T3> --subq <qN>
     ```
     등급은 `/Users/changhwan/.claude/skills/research/references/source-tiers.md`의 Tier 정의를 따른다
   - 저장된 텍스트(`{research_run}/<text>`)에서 codex `quote`를 Grep으로 찾는다
     - 그대로 있으면: 흡수 대상
     - 공백·따옴표만 다르면: 원문 그대로의 문장으로 quote를 바꿔 흡수 대상
     - 없으면: 같은 사실을 말하는 원문 문장을 찾아 그 문장으로 흡수한다. 원문 어디에도 그 사실이 없으면 `인용 불일치`로 기록하고 흡수하지 않는다
   - `claim`이 quote 범위를 넘으면(조건·버전 누락) 범위에 맞게 고친다
3. 흡수 대상은 `{research_run}/notes/<qN>-codex.jsonl`에 한 줄씩 Write/Edit로 쓴다(Bash `echo >>` 금지). 형식은 research:deep 리서처와 같다
   ```json
   {"subq":"q2","claim":"...","quote":"<원문 그대로>","source_id":"s...","url":"...","tier":"T1","date":"...","time_variant":true,"origin":"codex"}
   ```
4. codex finding이 기존 원장 주장과 상충하면 양쪽 id·URL을 기록한다(흡수는 하되 상충으로 표시)
5. `{research_run}/codex/findings-review.md`를 쓴다

```markdown
# codex 수집 검토

| subq | codex finding | 흡수 | 중복 | 인용 불일치 | 상충 |
|------|---------------|------|------|-------------|------|

## 흡수한 새 사실 (Claude 수집에 없던 것)
- <qN> <claim 요약> (source_id)

## 인용 불일치·오류
- <qN> <codex claim> : <이유>

## 상충
- <codex 주장> vs <claim_id> : <차이>
```

## 금지

- 원문 스냅샷에서 확인하지 못한 문장을 quote로 쓰지 않는다
- 기존 `notes/<qN>.jsonl`(Claude 리서처 파일)과 `claims.jsonl`은 고치지 않는다
- 실행 폴더 밖에 쓰지 않는다

최종 응답 3줄: 서브질문별 흡수/중복/불일치 건수 합계, 새로 저장한 소스 수, 상충 건수.
