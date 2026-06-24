"""Notion 본문 텍스트 하드룰 sanitizer (작성 스킬 공유).

마크다운 인라인 텍스트를 Notion rich_text로 변환하기 직전에 호출해,
CLAUDE.md 하드 가드레일을 쓰기 시점에 결정적으로 강제한다 (모델 준수와 무관한 backstop).

- em dash(U+2014) 금지 -> 콜론으로 대체 (CLAUDE.md가 명시한 1순위 대체 문자)
- 본문 이모지 금지 -> 제거

코드 블록은 리터럴이므로 호출자가 "인라인 prose 텍스트"에만 적용한다 (코드 블록 빌더는 우회).
화살표(U+2192), 중간점(U+00B7), 복합어 하이픈(-), 한글(U+AC00~U+D7AF)은 보존된다.
주관적 스타일(짧게/핵심만)은 코드로 강제할 수 없어 작성 시점 모델 + notion-review가 담당한다.
참조: ~/.claude/docs/notion-writing-style.md
"""
import re

# em dash는 앞뒤 공백(개행 제외)까지 흡수해 "A - B"/"A-B" 형태 모두 "A: B"로 정규화한다.
# 개행을 먹지 않도록 [ \t]만 흡수한다 (속성 필드의 줄 구조 보존).
_EM_DASH = re.compile(r"[ \t]*—[ \t]*")

# 본문 금지 이모지 범위. 한글/화살표(2190-21FF)/중간점은 의도적으로 제외한다.
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # 그림문자, 이모티콘, 교통, 보조 기호
    "\U00002600-\U000026FF"  # 기타 기호
    "\U00002700-\U000027BF"  # 딩벳 (체크/연필 등 이모지)
    "\U00002B00-\U00002BFF"  # 별/장식 기호
    "\U0001F1E6-\U0001F1FF"  # 지역 표시 기호 (국기)
    "\U0000FE0F"             # variation selector-16 (이모지 표현 강제)
    "]+"
)


def sanitize_body(text):
    """본문 인라인 prose 텍스트의 하드룰 위반을 제거한다.

    코드 블록/인라인 코드 식별자에는 적용하지 않는다 (리터럴 보존은 호출자 책임).
    None/빈 문자열은 그대로 반환한다.
    """
    if not text:
        return text
    text = _EM_DASH.sub(": ", text)
    text = _EMOJI.sub("", text)
    return text


if __name__ == "__main__":
    # 자가 검증: 하드룰은 정리하되 보존 대상은 건드리지 않는다.
    cases = [
        ("증상 분석 — 근본 원인 규명", "증상 분석: 근본 원인 규명"),  # em dash + space
        ("A—B", "A: B"),                                            # em dash no space
        ("배포 완료 \U0001F389 했습니다", "배포 완료  했습니다"),          # emoji 제거
        ("점검 ✅ 통과", "점검  통과"),                               # 딩벳 체크 제거
        ("트래픽 → 증가, infra·santa", "트래픽 → 증가, infra·santa"),  # 화살표/중간점 보존
        ("한글은 그대로", "한글은 그대로"),                                # 한글 보존
        ("`kubectl get pod`", "`kubectl get pod`"),                       # 일반 텍스트 보존
        ("줄1\n— 줄2", "줄1\n: 줄2"),                                # 개행 보존
        ("", ""),
        (None, None),
    ]
    ok = True
    for src, want in cases:
        got = sanitize_body(src)
        mark = "ok" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{mark}] {src!r} -> {got!r} (want {want!r})")
    print("ALL PASS" if ok else "SOME FAILED")
