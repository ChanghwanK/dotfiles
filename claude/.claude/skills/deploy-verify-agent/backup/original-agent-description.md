# deploy-verify-agent — 원본 Agent tool 설명 (백업)

백업 일자: 2026-03-30

## 원본 설명 (CLAUDE.md Agent tool 시스템 프롬프트)

**subagent_type**: `deploy-verify-agent`

**설명**:
Use this agent to check any live deployment state: ArgoCD sync/health status, pod status, logs, env var injection, and canary rollout progress. Use when: deployment isn't reflecting, why isn't ArgoCD syncing?, check pod status, verify env vars injected, canary in progress, promote/abort rollout, or after git push to confirm cluster state.

**도구**: All tools

## 라우팅 규칙 (kubernetes/CLAUDE.md Agent Routing)

| 트리거 | 에이전트 |
|--------|---------|
| 배포 후 확인, ArgoCD sync 상태, 카나리 진행상황 | deploy-verify-agent |
| 특정 pod 상태/로그/env var 확인 (배포 컨텍스트) | deploy-verify-agent |

## 사용 예시

- "santa-authentication dev 배포 잘 됐어?" → ArgoCD sync, pod status, 최근 로그 확인
- "ai-gateway 배포가 왜 반영이 안되고 있어?" → ArgoCD sync status, pod 상태 확인
- "ai-gateway 카나리 성공률 어때? 프로모션 해도 될까?" → rollout 진행상황, AnalysisRun 결과
- "santa-authentication 롤아웃이 왜 실패했어?" → AnalysisRun 실패 상세 분석
