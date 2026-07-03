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
- `in_progress` 항목은 **번호 목록**으로 출력: `{n}. **{task}** - {context 요약}`
  - task가 2개 이상이면 출력 마지막에 픽업 안내 한 줄 추가: `"N번 이어가자"로 특정 작업을 바로 시작할 수 있습니다`
  - context가 길면 핵심(현재 상태 + 다음 액션 + 작업 위치)만 남기고 요약
- `completed`, `next` 항목은 `- {item}` 형식
- `notes`가 빈 문자열이면 메모 섹션 생략
- resume은 handoff를 consume하지 않는다 (SKILL.md Step 3 참조)
