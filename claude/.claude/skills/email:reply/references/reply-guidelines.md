# 벤더별 이메일 답변 가이드

## 언어 판별 로직

1. 발신자 도메인이 한국 기업 (hostway.co.kr, naver.com 등) → **한국어**
2. 상대방 이전 메시지에 한국어 포함 → **한국어**
3. 자동발송(noreply, no-reply, notifications@) → 실제 수신 담당자에게 **한국어**로 작성
4. 순수 해외 CS 포털 (AWS Support 케이스, GCP Support 티켓 시스템) → **영어**
5. 그 외 → **한국어** 기본

---

## AWS (amazon.com, amazonaws.com, aws.amazon.com)

**언어**: 영어 (AWS Support 티켓 시스템) / 한국어 (한국 AWS 담당자와 직접 소통)

**톤**: Professional, 기술적, 간결

**필수 포함 항목**:
- Support 케이스 번호 (있으면 제목에 포함: `[Case: 12345678]`)
- AWS 계정 ID (12자리) — 요청이 계정 관련인 경우
- 요청 리전 명시

**유형별 요점**:
- **서비스 한도 증가**: 현재 한도 / 요청 한도 / 비즈니스 justification (예상 트래픽, 서비스 규모)
- **청구 이슈**: 해당 기간, 서비스 명, 예상 금액 vs 실제 금액
- **기술 지원**: 재현 단계, 에러 메시지, 리전, 서비스 이름
- **Enterprise Support**: 기술적 세부사항 충분히 서술, SLA 언급 가능

**예시 인사**:
```
Hello AWS Support Team,

Thank you for contacting us regarding [주제].
Our AWS Account ID is: XXXXXXXXXXXX
```

---

## Hostway IDC (hostway.co.kr, hostway.com)

**언어**: 한국어

**톤**: 친근하되 명확, 기술 요구사항은 구체적 수치로

**필수 포함 항목**:
- 티켓/문의 번호 (있으면 제목에 포함)
- 영향 받는 서버 IP 또는 호스트명
- 요구 조치 사항을 bullet로 명확히

**유형별 요점**:
- **유지보수 안내 수신**: 영향 받는 서비스 확인, 허용 가능한 유지보수 시간대 협의, 공지 요청
- **네트워크 이슈**: 영향 범위 (CIDR, VLAN ID), 예상 복구 시간 문의
- **하드웨어 요청**: 스펙 명세, 납기 일정, 예산 범위
- **계약/청구**: 담당자 확인 후 내부 검토 필요 시 타임라인 제시

**예시 인사**:
```
안녕하세요, Hostway 담당자님.

SOCRA AI DevOps 팀 창환입니다.
[주제]와 관련하여 문의드립니다.
```

---

## CSP — GCP, Azure 등 (google.com, azure.com, microsoft.com)

**언어**: 한국어 (한국 파트너/담당자) / 영어 (해외 CS 포털)

**톤**: Formal, action-oriented

**필수 포함 항목**:
- 프로젝트 ID / 구독 ID
- 지원 티켓 번호 (있으면 포함)

**유형별 요점**:
- **기술 지원**: Severity level 언급, reproduction steps, 관련 로그 첨부 여부
- **결제/크레딧**: 사용 기간, 서비스 명, 크레딧 코드

---

## 기타 벤더 (일반)

**언어**: 한국어 기본

**톤**: Professional, 요청/응답 항목 bullet로 명확히

**유형별 요점**:
- **계약/청구**: 담당자 확인 → 내부 검토 타임라인 제시
- **기술 문의**: 재현 가능한 정보 제공, 예상 SLA 문의
- **파트너십**: 구체적인 요구사항과 기대 일정 명시

---

## 공통 서명

```
감사합니다.

창환 (Changhwan)
DevOps Engineer, SOCRA AI
claude3@socra.ai
```

영어 답변 시:
```
Best regards,

Changhwan
DevOps Engineer, SOCRA AI
claude3@socra.ai
```

---

## SOCRAAI 인프라 컨텍스트 (참조용)

답변 작성 시 활용 가능한 인프라 정보:
- **AWS 계정**: 도쿄 리전 (ap-northeast-1) 메인
- **EKS 클러스터**: infra-k8s-prod, infra-k8s-stg, infra-k8s-dev, infra-k8s-global
- **IDC**: Seoul (Hostway), GPU A6000 클러스터
- **네트워크**: Tokyo VPC 10.0.0.0/16, Seoul VPC 10.100.0.0/16
- **서비스**: Santa (TOEIC/TOEFL), SOCRAAI (AI 튜터)
