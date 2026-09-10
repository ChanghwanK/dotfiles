# review Output Format

Korean, formal register (격식체), conclusion first. Angle brackets are placeholders. Scale the length to the target; keep the section order. No em dash; use colon, comma, or parentheses.

```
# 검토: <대상 한 줄>

## 결론
- 버전 앵커 A1: <컴포넌트 = 설치 버전, 출처 경로>
- <가장 나쁜 소식부터. 클레임별 판정 한 줄씩>
  - I1 <추론 요약>: PARTIAL (신뢰 medium) [1][4], 대안 ALT1 미배제
  - M1 <메커니즘 요약>: SUPPORTED (신뢰 high, A1 기준) [1]
  - O1 <관측 요약>: UNDETERMINED (쿼리 없음, 아래 5절에서 실행)

## 분해
- M1: <메커니즘 진술, 평가어 제거>. 거짓 조건: <...>
- O1: <관측 진술>. 쿼리: <Q1 또는 "없음">
- I1: <M과 O로 증상을 설명하는 추론>. 거짓 조건: <대안이 동등하게 설명 / 형태 불일치>
- ALT1: <경쟁 메커니즘>
- P1: <숨은 전제>. 확인: <검증됨 [n] / 반증됨 [n] / 미확인>

## 클레임별 근거
### M1 <요약>: SUPPORTED (신뢰 high, A1 기준)
- 반증 탐색: <검색어 / 소스 경로>, 해당 없음
- 지지: <근거> [1] (T1, <A1 버전 문서 또는 태그>)
- 가장 강한 반론: <...>
- 판정을 바꾸는 조건: <...>

### I1 <요약>: PARTIAL (신뢰 medium)
- 형태 대조: 타이밍 <일치/불일치>, 크기 <...>, 분포 <...> [n]
- 대안: ALT1 <배제됨 [n] / 미배제 / 미검증>
- 가장 강한 반론: <...>
- 판정을 바꾸는 조건: <...>

## 판정 불일치   (블라인드 평가와 사전 판정이 다를 때만)
- I1: 사전 판정 SUPPORTED, 블라인드 평가 PARTIAL. 차이의 원인: <어느 근거를 어떻게 다르게 읽었는가>. 최종: <판정과 이유>

## 모호함 해소   (항상)
- O1 확정: `<PromQL / LogQL / kubectl 명령>` → 실행 결과: <값> (또는 실행 불가 사유)
- ALT1 배제: <필요한 측정 또는 A1 버전 문서 페이지>

## 제안   (REFUTED / PARTIAL이 있거나 사용자가 요청했을 때만)
1. <제안> [n]
   - 우리 인프라에서는: <SOCRA AI 맥락 한 줄>
   - 트레이드오프: <성능 / 비용 / 운영 부담 / 복잡도 / 위험>
2. <제안> [n]

## References
[1] <제목> · <URL> (T1, <버전 또는 날짜>)
[2] <제목> · <URL> (T2, <날짜>)
[3] <제목> · <URL> (T2, <날짜>, stale-suspect)
[4] <제목> · <repo 경로 또는 PR URL> (TX, <날짜>)
```

Rules:
- Every verdict line has `[n]`. `UNDETERMINED` explains why (T3 only, premise unverified, query missing).
- M verdicts state that they are for the version anchor `A1`; a version delta is written out, never implied.
- `모호함 해소` is always present; queries that are read-only and available are executed and their result shown.
- `가장 강한 반론` and `판정을 바꾸는 조건` are present on every claim, including `SUPPORTED`.
- The `판정 불일치` and `제안` sections are omitted when empty; do not print "해당 없음".
- References include tier and date or version; TX items point to a path or PR URL, never to "a past session".
- Do not open with agreement phrases (see `references/bias-checklist.md`).
