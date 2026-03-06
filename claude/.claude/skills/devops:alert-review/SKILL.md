---
name: devops:alert-review
description: |
  야간/부재 중 Grafana 알림을 수집, 분석, 리뷰하는 스킬.
  Slack #notification_infra 채널과 Grafana에서 알림을 수집해
  심각도별 분류, 알림 규칙 쿼리 확인, TODO 액션 아이템을 생성한다.
  사용 시점: (1) 아침 출근 시 야간 알림 리뷰, (2) 특정 시간대 알림 분석,
  (3) 반복 발생 알림 패턴 파악, (4) 미해결 알림 현황 확인.
  트리거 키워드: "알림 리뷰", "야간 알림", "alert review", "overnight alerts",
  "알림 분석", "/devops:alert-review".
model: sonnet
allowed-tools:
  - Bash(python3 /Users/changhwan/.claude/skills/devops:alert-review/scripts/time-range.py *)
  - mcp__slack__slack_get_channel_history
  - mcp__slack__slack_get_thread_replies
  - mcp__grafana__get_alert_rule_by_uid
  - mcp__slack__slack_post_message
---

# Alert Review Skill

Slack #notification_infra 채널의 알림을 수집·분석하여 구조화된 리포트와 TODO를 생성한다.

---

## 핵심 원칙

- **Slack `#notification_infra` 채널 메시지가 유일한 데이터 소스이다.** vmalertmanager 직접 발송 포함 모든 실제 운영 알림이 이 채널에 도착한다.
- **VictoriaMetrics MCP, Grafana OnCall API 사용 금지.** OnCall은 dev/stg 포함 전체 채널 데이터를 반환하여 노이즈가 발생한다.
- 알림 메시지 파싱은 Claude 자연어 이해를 활용한다 (regex 사용 금지 — 형식 변경에 robust).
- firing 알림이 5개 초과 시 CRITICAL만 자동 조사한다.

---

## 워크플로우

### Step 1 — 시간 범위 계산

사용자가 시간 범위를 지정하지 않으면 기본값 `yesterday 22:00 ~ now`를 사용한다.

```bash
python3 /Users/changhwan/.claude/skills/devops:alert-review/scripts/time-range.py calc \
  --from "yesterday 22:00" --to "now"
```

응답 JSON에서 `from_utc`, `to_utc`, `from_epoch`, `to_epoch`, `slack_oldest`, `slack_latest`를 추출한다.

### Step 2 — 알림 데이터 수집

Slack `#notification_infra` 채널만 조회한다:

- `slack_get_channel_history(channel_id="C0782TXLBT5", limit=200)`
- 반환된 메시지 중 `ts`가 `from_epoch` ~ `to_epoch` 범위 밖인 것은 제외한다.
- 메시지가 200개 꽉 차고 가장 오래된 메시지의 `ts`가 `from_epoch`보다 크면 누락 가능성이 있으므로 사용자에게 알린다.

### Step 3 — 알림 파싱 및 분류

Slack 메시지에서 다음을 추출한다:
- **알림 ID**: `#NNNNN` 형식 (OnCall alert group ID)
- **규칙명**: 알림 제목/이름
- **심각도**: CRITICAL / WARNING / INFO (severity 라벨 또는 메시지 컨텍스트로 판단)
- **상태**: firing / resolved
- **서비스명**: 관련 서비스 또는 네임스페이스
- **클러스터**: 어느 클러스터에서 발생했는지
- **Source 링크**: Grafana/Alertmanager 링크

분류 규칙:
1. 같은 rule name으로 그룹화한다.
2. firing → resolved 전환 쌍을 매칭한다 (같은 rule name + 유사 라벨).
3. resolved 없이 firing만 있으면 "미해결"로 분류한다.
4. `#NNNNN` alert group ID는 Slack 메시지에서 추출하여 참조 링크로만 사용한다 (OnCall API 호출 없음).

### Step 4 — Source 쿼리 조사 (firing 알림 대상)

미해결(firing) 알림 또는 반복 발생 알림에 대해:

1. Slack 메시지의 source 링크에서 PromQL 쿼리를 추출하여 리포트에 포함한다.
2. (선택) `get_alert_rule_by_uid(uid)` → 알림 규칙 상세 확인 (uid는 Slack 메시지의 source 링크에서 추출).
3. 현재 메트릭 조회는 하지 않는다 (`query_prometheus` 사용 금지).

조사 범위 제한:
- firing 알림 ≤ 5개: 전부 조사
- firing 알림 > 5개: CRITICAL만 자동 조사, 나머지는 리포트에 목록만 표시

### Step 5 — 리포트 생성

Slack mrkdwn 호환 포맷으로 출력한다. 마크다운 테이블은 Slack에서 렌더링되지 않으므로 사용 금지.
이모지는 🔴(미해결)과 ✅(해결)만 사용한다.

```
*Alert Review: {from_kst} ~ {to_kst}*

━━━━━━━━━━━━━━━━━━━━

*요약*
• 총 알림: *N건*
• 🔴 Firing (미해결): *N건*
• ✅ Resolved: *N건*
• CRITICAL: N | WARNING: N | INFO: N
• 클러스터별: prod N건, stg N건, dev N건, global N건, idc N건

━━━━━━━━━━━━━━━━━━━━

🔴 *미해결 알림 (즉시 확인 필요)*

> *{알림명} — {심각도}*
> • 서비스: `{service}`
> • 발생: {KST}
> • 쿼리: `{PromQL/LogQL}`
> • 클러스터: `{cluster}` / NS: `{namespace}`
> • {source_link}

━━━━━━━━━━━━━━━━━━━━

✅ *해결된 알림*

> *{알림명} — {심각도}*
> 서비스: `{service}`
> 발생 {HH:MM} → 해결 {HH:MM} KST (지속 ~N분)

━━━━━━━━━━━━━━━━━━━━

*반복 발생 알림*

> *{알림명}* — N회
> 서비스: `{service}`
> 패턴: {패턴 설명}

━━━━━━━━━━━━━━━━━━━━

*TODO*

*즉시 조치 (미해결 알림)*
☐ `{알림명}`: {권장 조치}

*조사 필요 (반복 알림)*
☐ `{알림명}`: {조사 방향}

*알림 규칙 개선 (noisy 알림)*
☐ `{알림명}`: {개선 제안}

━━━━━━━━━━━━━━━━━━━━
_Claude Code alert-review by changhwan_
```

각 섹션에 해당 항목이 없으면 "해당 없음"으로 표시한다.

Slack 메시지 전송이 요청된 경우 `slack_post_message`로 리포트를 채널에 전송한다.

### Step 6 — 검증

반드시 아래를 확인한다:
- 리포트의 firing 수 = Step 3에서 분류한 미해결 알림 수와 일치
- TODO 섹션에 빈 항목(`- [ ]` 뒤에 내용 없음)이 없는지 확인
- 시간 범위 밖 알림이 리포트에 포함되지 않았는지 확인

실패 시:
- 수 불일치 → Step 3 파싱 결과를 재확인 후 리포트 수정
- 빈 TODO → 해당 항목 제거 또는 내용 보완
- 범위 밖 알림 → 해당 항목 제거

---

## 주의사항

- Slack 채널 ID `C0782TXLBT5`는 `#notification_infra` 채널이다.
- MCP 토큰은 wrapper 스크립트가 자동 주입한다 — 별도 인증 작업 불필요.
- 알림 ID (`#NNNNN`)가 메시지에 없는 경우 (vmalertmanager 직접 발송) rule name으로만 그룹화한다.
- OnCall API (`list_alert_groups`, `get_alert_group`)와 VictoriaMetrics MCP (`query_prometheus` 등)는 사용하지 않는다.
