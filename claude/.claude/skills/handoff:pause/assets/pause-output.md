# Pause 출력 템플릿

```
⏸️ Handoff 저장 완료 ({time})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
사유: {reason}

✅ 완료
{completed_items}

🔄 진행 중
{in_progress_items}

📋 다음 할 것
{next_items}

📝 메모
{notes}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
복귀 시 `/handoff:resume` 또는 "돌아왔다"로 복원
```

## 섹션 규칙

- 항목이 없는 섹션은 출력하지 않는다
- `in_progress` 항목은 `- {task} — {context}` 형식으로 출력
- `completed`, `next` 항목은 `- {item}` 형식
- `notes`가 빈 문자열이면 메모 섹션 생략
