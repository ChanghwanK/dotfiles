---
name: 1p:addsecret
description: |
  1Password vault에 시크릿을 추가하는 스킬. 사용 시점: (1) API 키/봇 토큰/비밀번호를 1Password에 저장, (2) 대화 중 생성된 시크릿을 즉시 vault에 등록, (3) 팀 vault 공유 항목 생성.
  트리거 키워드: "1password에 저장", "볼트에 추가", "op에 추가", "1p:addsecret".
model: haiku
allowed-tools:
  - Bash(op vault list*)
  - Bash(op item create*)
  - Bash(op item get*)
---

# 1p:addsecret

`op item create`를 사용하여 1Password vault에 시크릿 항목을 생성한다.

---

## 핵심 원칙

- **값 노출 금지**: 시크릿 값은 출력에 절대 표시하지 않는다 (`--reveal` 금지)
- **vault 자동 탐색**: vault 이름이 모호하면 `op vault list`로 실제 이름을 확인 후 사용
- **카테고리 선택**: API 키/토큰 → `API Credential`, 비밀번호 → `Login`, 기타 → `Secure Note`
- **런타임 조회 안내**: 저장 후 반드시 `op read` 사용법을 알려준다

---

## 워크플로우

### Step 1 — 입력 파악

대화 맥락에서 다음 정보를 추출한다:

| 항목 | 필수 | 기본값 |
|------|------|--------|
| 시크릿 값 | ✅ | - |
| 항목 제목 (title) | ✅ | - |
| vault 이름 | ❌ | 사용자에게 선택 요청 |
| 카테고리 | ❌ | `API Credential` |
| 필드명 | ❌ | `credential` |

값이 누락된 경우에만 사용자에게 질문한다.

### Step 2 — Vault 확인

vault 이름이 불확실한 경우:

```bash
op vault list
```

출력에서 실제 vault 이름(NAME 컬럼)을 확인한다.
> ⚠️ vault 이름은 대소문자/공백을 정확히 맞춰야 한다 (예: "chapter devops" → `Chapter_DevOps`)

### Step 3 — 항목 생성

```bash
op item create \
  --vault "<VAULT_NAME>" \
  --title "<TITLE>" \
  --category "API Credential" \
  "credential=<SECRET_VALUE>"
```

**카테고리별 필드명:**
- `API Credential` → `credential`
- `Login` → `username=<id>`, `password=<pw>`
- `Secure Note` → `notesPlain=<내용>`

### Step 4 — 결과 확인 및 안내

성공 시 출력:
```
✅ 저장 완료
- Vault: <vault>
- Title: <title>
- Item ID: <id>

런타임 조회:
op read "op://<vault>/<title>/credential"
```

---

## 주의사항

- `op` CLI가 로그인 상태가 아니면 `op signin` 먼저 실행 필요
- vault 이름에 공백이 있으면 따옴표로 감싸야 한다
- 생성 후 값 확인은 `op item get <id> --reveal`로만 가능 (스킬에서는 호출하지 않음)
