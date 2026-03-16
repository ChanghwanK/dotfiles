# Resume 출력 템플릿

```
▶️ 복귀 컨텍스트 ({saved_time} → {now_time}, {elapsed} 경과)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
사유: {reason}

✅ 이전 완료
{completed_items}

🔄 이어서 할 것
{in_progress_items}

📋 다음 계획
{next_items}

📝 메모
{notes}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 섹션 규칙

- 항목이 없는 섹션은 출력하지 않는다
- `in_progress` 항목은 `- {task} — {context}` 형식으로 출력
- `completed`, `next` 항목은 `- {item}` 형식
- `notes`가 빈 문자열이면 메모 섹션 생략
