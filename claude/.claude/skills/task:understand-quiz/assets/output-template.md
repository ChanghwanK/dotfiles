# Output templates

Korean, 격식체, no em dash, no emoji. Two templates: the **question round** and the
**grading round**. Model answers, 한 문장 요약, and 게이트 기준답 never appear in a
question round; they surface only in the grading round, for the items being graded.

The three `###` question headings change with granularity. Use the axis names from
SKILL.md Step 3 for the resolved granularity, not the ones below verbatim.

---

## 1. 질문 라운드 (round 1 shown; later rounds drop the gates)

---

{target_title} 기준 {difficulty} 라운드 {round_n}입니다.
{scope_line}

---

## 복기 게이트 (closed-book)

산출물과 출처를 보지 않고 답하십시오. 채점과 기준답 공개는 답변 후에 이루어집니다.

- **게이트 1 (재구성)**: 이 {단위}가 왜 존재하고 무엇을 바꾸는지 본인 말로 2~3문장으로 재구성하십시오.
- **게이트 2 (복기)**: 이 {단위}의 핵심 주장(또는 핵심 결정) {claim_count}개를 복기하십시오.

---

### Q1 ({axis_1_name}). {question}

### Q2 ({axis_2_name}). {question}

### Q3 ({axis_3_name}). {question}

---

## 이 단위의 위치

{include only for phase-level or step-level quizzes. one line each.}

- *앞 단계:* {what must already be true}
- *이 단계:* {what changes here}
- *뒤 단계:* {what becomes possible}

---

## 근거를 찾지 못한 항목

{omit when empty. never invent an answer to fill it.}

- {axis}: {what is missing} → {where the author should state it}

---

답변을 주시면 채점하고, 부족한 지점을 파고드는 후속 질문으로 이어갑니다.
중단하려면 "그만" 또는 "여기까지"라고 말씀해 주십시오.

---

## 2. 채점 라운드

---

라운드 {round_n} 채점입니다.

## 게이트 채점

{round 1 grading only. reveal the held references here.}

- **게이트 1 (재구성)**: {통과|부분|미달} : {what matched or missed, grounded}
  - 기준 재구성: **"{elevator_pitch}"**
- **게이트 2 (복기)**: {matched}/{claim_count} 일치, {통과|미달} (기준 {pass_threshold}개)
  - 기준답:
    1. {load_bearing_claim}
    2. {load_bearing_claim}
    3. {load_bearing_claim}

## 문항 채점

### Q{n} ({axis_name}): {통과|부분|미달}

- **교정**: {exactly what was missing or wrong, citing the concrete artifact}
- **모범답안**: {model answer, revealed now}

{repeat per question}

---

## 다음 라운드

{only when at least one item is 부분/미달, or when escalating difficulty after a clean pass.
1 to 3 questions. each follow-up names which gap it chases.}

### Q1 ({axis_name} 심화). {follow_up_question}

{questions only. answers stay held for the next grading round.}

---

## 종료 요약

{only on exit: all axes passed at 고급, or the owner stopped.}

- **통과**: {axes that passed cleanly, at which difficulty}
- **라운드가 필요했던 축**: {axes that needed follow-ups, and what closed the gap}
- **남은 무지 항목**: {items still not understood. omit the line when none.}

### 예상 리뷰 질문

{omit unless at least two are genuinely likely. mainly for pr granularity.}

- "{likely_question}" → {short_answer}
- "{likely_question}" → {short_answer}

💡 남은 무지 항목은 `/wiki:note 무지` 로 저장하고 1달 후 재인터뷰할 수 있습니다.
