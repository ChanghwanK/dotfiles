"""Notion 페이지 상단 콜아웃 목차(TOC) 공유 헬퍼 (tasks:manage, notion:add-engineering-note 공유).

패턴: 본문 생성 시 콜아웃을 placeholder로 먼저 넣어 페이지 맨 앞 자식으로 만들고,
그 형제 블록들이 실제로 생성된 뒤(POST/PATCH 응답 또는 GET children으로 얻은 id 포함
블록 리스트) 순서를 스캔해 heading과 특정 라벨 문단(Goal/Non-goal/Goals/Non-Goals)을
페이지 내 링크로 채운 rich_text로 콜아웃을 갱신한다.

블록 생성 시점엔 아직 블록 id가 없어 링크를 만들 수 없고, 생성 후 응답에만 id가
있으므로 이 2단계(placeholder → 생성 → 링크 채우기)가 필요하다.
"""
import re

TOC_ICON = "📌"
_PLACEHOLDER_TEXT = "목차 생성 중..."
_NUMBERED_HEADING = re.compile(r'^\d+\.\s')
# 목차에서 상위 항목(heading) 아래 한 단계 들여써 넣는 라벨 문단.
# Task 본문의 "Goals"/"Non-Goals", Engineering Note의 "Goal"/"Non-goal" 둘 다 대응한다.
_SUB_LABELS = {"Goal", "Non-goal", "Goals", "Non-Goals"}


def placeholder_callout():
    """본문 맨 앞에 넣을 콜아웃 placeholder 블록. 생성 후 build_toc_rich_text()로 채운다."""
    return {
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": _PLACEHOLDER_TEXT}}],
            "icon": {"type": "emoji", "emoji": TOC_ICON},
            "color": "default",
        },
    }


def _plain_text(block):
    btype = block.get("type", "")
    rich_text = block.get(btype, {}).get("rich_text", [])
    return "".join(
        seg.get("plain_text") or seg.get("text", {}).get("content", "")
        for seg in rich_text
    ).strip()


def build_toc_rich_text(created_blocks, page_url):
    """생성된 블록 목록(순서 보존, id 포함)에서 콜아웃과 목차 항목을 찾아 rich_text를 만든다.

    created_blocks: POST/PATCH 응답의 children 블록 리스트 또는 GET children 결과.
    각 항목은 최소 "id"/"type"/{type}.rich_text 를 가져야 한다.

    반환: (callout_block_id, rich_text), 콜아웃을 못 찾거나 목차 항목이 하나도 없으면
    (None, None). 콜아웃이 없으면 애초에 채울 대상이 없고, 항목이 없으면(제목 없는
    본문 등) 목차 자체가 의미 없으므로 둘 다 스킵 조건으로 다룬다.
    """
    callout_id = None
    entries = []  # (indent_level, title, block_id)
    for block in created_blocks:
        btype = block.get("type", "")
        if btype == "callout" and callout_id is None:
            callout_id = block.get("id")
            continue
        if btype.startswith("heading_"):
            text = _plain_text(block)
            if _NUMBERED_HEADING.match(text):
                entries.append((0, text, block.get("id")))
            continue
        if btype == "paragraph":
            text = _plain_text(block)
            if text in _SUB_LABELS:
                entries.append((1, text, block.get("id")))

    if callout_id is None or not entries:
        return None, None

    rich_text = []
    for i, (level, title, block_id) in enumerate(entries):
        if i > 0:
            rich_text.append({"type": "text", "text": {"content": "\n"}})
        if level == 1:
            rich_text.append({"type": "text", "text": {"content": "    "}})
        anchor = block_id.replace("-", "")
        rich_text.append({
            "type": "text",
            "text": {"content": title, "link": {"url": f"{page_url}#{anchor}"}},
        })
    return callout_id, rich_text
