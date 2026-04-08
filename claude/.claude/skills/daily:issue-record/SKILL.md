---
name: daily:issue-record
description: |
  작업 중 발생한 이슈를 Obsidian Daily Note의 Issues 섹션에 기록하는 도구.
  사용 시점: (1) 작업 중 이슈 발생 시 기록, (2) 블로커/문제 상황 메모.
  트리거 키워드: "이슈 기록", "issue 기록", "이슈 남겨", "/daily:issue-record".
allowed-tools:
  - Read
  - Edit
---

# daily:issue-record 스킬

작업 중 발생한 이슈를 오늘 Obsidian Daily Note의 `## Issues` 섹션에 기록한다.

---

## 핵심 원칙

- 스크립트 없이 Read + Edit 도구만 사용한다.
- 대화 맥락에서 이슈 정보를 최대한 파악한다. 맥락이 불충분하면 질문한다.
- Daily Note가 없으면 경로를 안내하고 종료한다.
- `## Issues` 섹션이 없으면 파일 하단에 해당 섹션을 새로 추가한다.

---

## 워크플로우

### Step 1 — 이슈 정보 추출

대화 맥락을 분석하여 다음을 추출한다:

- **요약**: 이슈를 한 줄로 요약 (무엇이 어떻게 됐는지)
- **세부 내용**: 원인, 과정, 조치 등 구체적 사항 (여러 줄 가능)

맥락이 불충분하면 질문한다.

### Step 2 — Daily Note 읽기

오늘 날짜로 Daily Note를 읽는다.

```
경로: /Users/changhwan/Library/Mobile Documents/com~apple~CloudDocs/obsidian_home/ch_home/01. Daily/YYYY-MM-DD.md
```

파일이 없으면:
- "오늘 Daily Note가 없습니다. `/daily:start`로 먼저 생성해 주세요." 출력 후 종료.

### Step 3 — Issues 섹션에 append

`## Issues` 섹션의 마지막 항목 뒤에 Edit 도구로 append한다.

- `## Issues` 섹션이 없으면 → 파일 끝에 섹션 + 이슈 함께 추가.
- 다음 섹션(`##`)이 나오기 전에 삽입한다.

---

## 기록 형식

```markdown
- {요약 1줄}
	- {세부 내용 1}
	- {세부 내용 2}
```

**예시:**
```markdown
- k6-restarter grace period 배포 시 CRD 스키마 불일치로 ArgoCD sync 실패
	- `make manifests`는 `config/crd/bases/`에만 CRD를 생성하고 chart에는 복사하지 않음
	- CRD 복사 없이 helm package → Harbor push하여 구 스키마 배포됨
	- Makefile `manifests` 타겟에 cp 추가하여 재발 방지
```

---

## 완료 출력

```
✅ 이슈 기록 완료
- 파일: YYYY-MM-DD.md
- 이슈: {요약 1줄}
```

트러블슈팅(에러 분석, 장애 대응, 원인 추적)에 해당하면 추가 안내:

```
💡 트러블슈팅이었다면 `## Hypothesis Log`에도 가설을 기록해보세요.
   형식: ### [HH:MM] 이슈명 → 증상 → H1/H2 가설 → 결과
```

---

## 엣지 케이스

| 상황 | 처리 방법 |
|------|-----------|
| Daily Note 파일 없음 | `/daily:start`로 생성 안내 후 종료 |
| `## Issues` 섹션 없음 | 파일 끝에 섹션 + 첫 이슈 함께 추가 |
| 이슈 정보 불충분 | Step 1에서 질문하여 확인 후 진행 |
