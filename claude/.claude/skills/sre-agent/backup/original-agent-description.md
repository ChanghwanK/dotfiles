# sre-agent — 원본 Agent tool 설명 (백업)

백업 일자: 2026-03-30

## 원본 설명 (CLAUDE.md Agent tool 시스템 프롬프트)

**subagent_type**: `sre-agent`

**설명**:
Use this agent for: (1) Active incident response — alert fired, service down, CrashLoopBackOff, 503/504 spike; (2) Proactive health scan — 'prod 이상한 거 있어?', 'is anything wrong?', general cluster health check. Performs automated parallel evidence collection, hypothesis-driven RCA, and parallel Quick Fix + Deep RCA pipelines.

**도구**: All tools

## 라우팅 규칙 (kubernetes/CLAUDE.md Agent Routing)

| 트리거 | 에이전트 |
|--------|---------|
| 알림 발생, service down, CrashLoopBackOff, 503/504 폭증 | sre-agent |
| "prod 이상한 거 있어?", "뭔가 이상해 보여", 사전 점검 | sre-agent |

**경계 룰**: 장애 여부 불명확 → sre-agent (더 많은 증거를 수집하므로 안전)
