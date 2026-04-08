# Amazon SQS / Amazon MQ — 개발자를 위한 개념 가이드

## 한줄 요약

Celery, Sidekiq의 브로커를 AWS가 운영해주는 것.
**SQS**: 단순 HTTP 큐 / **Amazon MQ**: RabbitMQ/ActiveMQ 호환 풀 기능 메시지 브로커

## 개발자에게 익숙한 비유

| 로컬 환경 | AWS 동등 서비스 |
|----------|--------------|
| `docker-compose`의 RabbitMQ | Amazon MQ (for RabbitMQ) |
| 단순 작업 큐 (순서/영속성 덜 중요) | Amazon SQS |

우리 팀은 기존 RabbitMQ 연동 코드(AMQP 프로토콜)를 그대로 사용하기 위해 **Amazon MQ** 를 주로 사용한다.

## 핵심 개념

### Amazon SQS
| 개념 | 설명 |
|------|------|
| **Queue** | 메시지 저장소. Standard (높은 처리량) / FIFO (순서 보장) |
| **Standard Queue** | 순서 보장 안 함. 초당 수만 건 처리 가능 |
| **FIFO Queue** | 순서 보장 + 중복 방지. 초당 3,000건 |
| **DLQ (Dead Letter Queue)** | 처리 실패 메시지를 따로 보관 |
| **Visibility Timeout** | 메시지 처리 중 다른 Consumer가 못 가져가는 시간 |

### Amazon MQ (RabbitMQ)
| 개념 | 설명 |
|------|------|
| **Broker** | RabbitMQ 서버. 인스턴스 타입 선택 |
| **Exchange/Queue** | 기존 RabbitMQ 개념과 동일 |
| **AMQP** | 기존 Pika, Celery 등 그대로 사용 가능 |

## Riiid에서 어떻게 쓰는지

- **Amazon MQ**: `src/{sphere}/{circle}/{env}/mq/mq.tf`
- **사용 sphere**: socraai (비동기 작업), santa 등
- **Celery 연동**: Amazon MQ (RabbitMQ)를 Celery broker로 사용
- **환경별 차이**:

| 설정 | dev | prod |
|------|-----|------|
| 인스턴스 | `mq.t3.micro` | `mq.m5.large` 이상 |
| 고가용성 (Multi-AZ) | false | true |
| 자동 Minor 업그레이드 | true | 상황에 따라 |

## 결정해야 할 사항 체크리스트

- [ ] 프로토콜: AMQP 사용? (→ Amazon MQ) / 단순 HTTP 큐? (→ SQS)
- [ ] 기존 RabbitMQ 클라이언트를 그대로 쓸 건가요?
- [ ] 순서 보장 필요 여부 (FIFO)
- [ ] 예상 메시지 처리량
- [ ] 환경: dev만? 전체?

## tf:iac 요청에 필요한 정보

```
{sphere}/{circle}/{env}에 Amazon MQ (RabbitMQ) 생성
- 용도: {Celery broker / 이벤트 처리 / 기타}
- 프로토콜: AMQP (RabbitMQ 호환) / SQS (HTTP)
- 환경: {dev / stg / prod}
- 인스턴스 크기: {기본값 사용 / 요구사항}
```
