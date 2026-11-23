# Jira 티켓 템플릿

Claude가 Jira 티켓을 만들거나 설명을 다시 쓸 때 따르는 정본이다(2026-11-23 사용자 결정). 기본 대상은 PLE Space(riiid-pioneer.atlassian.net)다.
Goal·Key Result·Todo의 구분과 문체는 `tasks:goal-kr-todo`가 정본이고, 이 문서는 그 구분을 Jira 유형에 맞춰 배치하는 방법만 정한다.

## 유형 고르기

| 유형 | 언제 | 템플릿 |
|------|------|--------|
| Epic | 여러 티켓으로 나뉘는 목표. 만들기는 사람이 정한다(Claude는 제안하지 않는다) | Epic |
| Task | 기본. 한 사람이 끝낼 수 있는 한 조각 | Task |
| Issue | 장애·알럿 RCA의 후속. `incident` 라벨을 붙인다 | Task와 같고, Background에 영향 측정값을 넣는다 |

## Task·Issue 템플릿

```markdown
## Background
왜 지금 하는가. 문제와 근거(측정값, 링크) 2~4줄. 원인을 재지 못했으면 (원인 미확인)

## Goal
이 티켓이 끝나면 바뀌는 모습 1~2줄. 수단과 수치 없이

## Key Result (완료 기준)
- 규칙형 결과 진술 1~3개. 수치와 판정 시점은 문장 끝 괄호

## Todo
- [ ] 구체적 행동

## 범위 밖
- 이 티켓에서 하지 않는 것 (있을 때만)

## 링크
- PR, Notion Task·설계 문서, 관련 티켓
```

- Goal은 Epic의 Goals를 되풀이하지 않고 이 조각이 바꾸는 것만 쓴다. 상위 Epic이 없으면 Goal이 작업 전체의 방향이다
- Key Result가 곧 완료 기준이다. "완료 기준" 칸을 따로 두지 않는다
- Todo는 행동이 2개 이하인 작은 티켓에서 생략할 수 있다. Key Result는 생략하지 않는다
- Issue의 Background에는 언제, 어디서, 무엇이 얼마나 영향을 받았는지를 측정값으로 쓴다

## Epic 템플릿

```markdown
## Background

## Goals
- 2~4개. 막을 것과 막으면 안 되는 것을 함께

## Key Results
- Epic 전체를 끝났다고 판정하는 기준

## 링크
```

Epic에는 Todo를 두지 않는다. 하위 Task 티켓이 Todo 역할을 한다.

## 쓰기 전 점검

- Key Result에 "작성한다", "연다", "적용한다"가 있으면 행동이므로 Todo로 옮기고, 그 행동의 결과를 Key Result로 쓴다 (예: "dev 적용 PR이 열린다" → Todo, "dev k6가 PgBouncer를 거쳐 연결되고 오류율이 전환 전과 같다" → Key Result)
- Goal에 도구 이름이나 수치가 있으면 설계나 Key Result가 섞인 것이다
- 원인 주장에는 측정이 있어야 한다. 측정 전이면 Background에 (원인 미확인)을 쓴다

## 필드 관례 (PLE)

- `summary`: 대상과 결과가 보이는 한 줄. 날짜·환경은 필요할 때만 괄호로
- `priority`: P1 목표와 보안은 `High`, 그 외 `Medium`
- `labels`: 소문자 컴포넌트·환경 (예: `istio`, `prod`, `security`, `incident`)
- `parent`: 같은 주제의 Epic이 있으면 건다
- `assignee`: 사용자가 정한 사람. 본인이면 `atlassianUserInfo`로 accountId를 얻는다(하드코딩하지 않는다)
- 상태: To Do, In Progress, DONE. 상태 전환은 사용자가 요청할 때만 한다

## 기존 티켓을 다시 쓸 때

- 사용자가 고른 티켓만 고친다. 다른 사람이 담당인 티켓의 설명은 고치지 않고 코멘트로 제안한다
- 기존 설명의 사실(측정값, PR, 링크)은 빠뜨리지 않고 새 칸으로 옮긴다
