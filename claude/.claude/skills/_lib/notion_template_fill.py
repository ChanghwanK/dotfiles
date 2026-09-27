"""Notion DB 템플릿으로 만든 페이지의 섹션을 heading 기준으로 채우는 공유 헬퍼
(tasks:manage notion-task.py, notion:add-engineering-note notion-eng-note.py 공유).

왜 템플릿을 적용한 뒤 채우는가:
- Task 템플릿의 버튼 블록은 API에서 `unsupported` 타입이라 직접 만들 수 없다. 템플릿을 적용해야만
  버튼과 네이티브 목차(table_of_contents)가 들어온다.
- 템플릿 구조를 스크립트에 복제하지 않으므로, 템플릿 문구·배치를 Notion에서 바꿔도 heading 이름만
  유지되면 스크립트를 고칠 필요가 없다.

템플릿은 POST /pages 응답 이후 백그라운드에서 적용되므로, 필요한 heading이 전부 보일 때까지
기다린 뒤(wait_for_headings) 섹션을 채운다(fill_section / append_to_section).

섹션 경계: heading 바로 다음 형제부터, 같은 레벨 이상의 heading, 구분선, column_list,
부모의 끝 중 먼저 나오는 곳까지. column 안의 heading(Before/After, Goals/Non Goals)은
column이 부모가 되므로 같은 규칙으로 처리된다.

request 인자는 (method, path, body) -> dict 형태의 콜러블이다. 두 스크립트의
notion_request 시그니처가 달라 호출자가 맞춰 넘긴다.
"""
import time

NOTION_APPEND_BATCH = 100  # children append 한 번에 넣을 수 있는 최대 블록 수
_CONTAINER_TYPES = {"column_list", "column"}
_TEXT_TYPES = {"paragraph", "bulleted_list_item", "numbered_list_item", "to_do", "quote"}


def _normalize(text):
    # 템플릿 heading에 뒤 공백이 섞여 있다("근본 원인 "). 공백 차이로 매칭이 깨지지 않게 한다.
    return " ".join((text or "").split())


def _plain_text(block):
    btype = block.get("type", "")
    rich_text = block.get(btype, {}).get("rich_text", []) or []
    return "".join(
        seg.get("plain_text") or seg.get("text", {}).get("content", "") for seg in rich_text
    )


def _heading_level(block):
    btype = block.get("type", "")
    if btype.startswith("heading_"):
        try:
            return int(btype.split("_")[1])
        except (IndexError, ValueError):
            return None
    return None


def _is_empty_placeholder(block):
    """템플릿이 깔아 둔 빈 불릿/빈 문단인가. 자식이 있으면 사용자가 쓴 내용으로 본다."""
    return (
        block.get("type") in _TEXT_TYPES
        and not block.get("has_children")
        and not _plain_text(block).strip()
    )


def list_children(request, block_id):
    """block_id의 직계 자식 전체(페이지네이션 포함). 오류면 None."""
    results, cursor = [], None
    while True:
        path = f"/blocks/{block_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        resp = request("GET", path, None)
        if resp.get("object") == "error":
            return None
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            return results
        cursor = resp.get("next_cursor")


def load_tree(request, page_id):
    """페이지 블록 트리. heading이 column 안에도 있으므로 column_list/column만 재귀로 펼친다.

    반환: [{"parent_id": id, "blocks": [...]}] 형태의 형제 그룹 목록. 각 블록에는
    컨테이너일 때 "_children"(하위 형제 그룹 인덱스가 아니라 블록 리스트)가 붙는다.
    """
    groups = []

    def walk(parent_id):
        children = list_children(request, parent_id)
        if children is None:
            return None
        groups.append({"parent_id": parent_id, "blocks": children})
        for block in children:
            if block.get("type") in _CONTAINER_TYPES and block.get("has_children"):
                if walk(block["id"]) is None:
                    return None
        return children

    if walk(page_id) is None:
        return None
    return groups


def _locate(groups, heading_text, prefix=False):
    """heading을 찾아 (parent_id, siblings, index)를 반환한다. 없으면 None.

    prefix=True면 heading이 heading_text로 시작하는지로 판정한다. 괄호 안 설명처럼 템플릿에서
    자주 바뀌는 꼬리("성장 회고 (Keep / Problem / Try)")에 매칭이 묶이지 않게 할 때 쓴다.
    """
    target = _normalize(heading_text)
    for group in groups:
        for idx, block in enumerate(group["blocks"]):
            if not _heading_level(block):
                continue
            text = _normalize(_plain_text(block))
            if text == target or (prefix and text.startswith(target)):
                return group["parent_id"], group["blocks"], idx
    return None


def _section_range(siblings, heading_idx):
    """heading 다음부터 섹션 경계 전까지의 블록 리스트."""
    level = _heading_level(siblings[heading_idx])
    body = []
    for block in siblings[heading_idx + 1:]:
        other_level = _heading_level(block)
        if other_level is not None and other_level <= level:
            break
        if block.get("type") in ("divider", "column_list"):
            break
        body.append(block)
    return body


def find_missing(groups, headings, prefix=False):
    return [h for h in headings if _locate(groups, h, prefix) is None]


def wait_for_headings(request, page_id, headings, timeout_sec=30, interval_sec=1.0, prefix=False):
    """필요한 heading이 전부 나타날 때까지 폴링한다. 성공하면 트리, 타임아웃이면 None.

    첫 자식만 확인하면 템플릿이 일부만 들어온 상태에서 채우기를 시작할 수 있어
    heading 전체를 기준으로 기다린다.
    """
    deadline = time.monotonic() + timeout_sec
    while True:
        groups = load_tree(request, page_id)
        if groups is not None and not find_missing(groups, headings, prefix):
            return groups
        if time.monotonic() > deadline:
            return None
        time.sleep(interval_sec)


def _insert_after(request, parent_id, after_id, blocks):
    """after_id 바로 뒤에 blocks를 순서대로 넣는다. 실패하면 error 응답을 반환한다."""
    for start in range(0, len(blocks), NOTION_APPEND_BATCH):
        chunk = blocks[start:start + NOTION_APPEND_BATCH]
        resp = request("PATCH", f"/blocks/{parent_id}/children", {"children": chunk, "after": after_id})
        if resp.get("object") == "error":
            return resp
        # after 삽입 응답의 results는 "삽입한 블록 + 그 뒤의 기존 형제 전부"다(2026-09-27 실측).
        # 다음 묶음은 이번에 넣은 마지막 블록 뒤에 이어 붙인다.
        results = resp.get("results", [])
        if len(results) < len(chunk):
            return {"object": "error", "message": "append 응답에 삽입된 블록 수가 모자람"}
        after_id = results[len(chunk) - 1]["id"]
    return None


def _delete_blocks(request, blocks):
    for block in blocks:
        resp = request("DELETE", f"/blocks/{block['id']}", None)
        if resp.get("object") == "error":
            return resp
    return None


def fill_section(request, groups, heading_text, blocks, replace=False, prefix=False):
    """heading 아래 섹션을 blocks로 채운다.

    replace=False: 템플릿의 빈 placeholder만 지우고 heading 바로 뒤에 넣는다(신규 생성용).
    replace=True: 섹션의 기존 내용을 전부 지우고 넣는다(최종본 동기화용).
    반환: None(성공) | "missing"(heading 없음) | error dict.
    """
    located = _locate(groups, heading_text, prefix)
    if located is None:
        return "missing"
    parent_id, siblings, idx = located
    body = _section_range(siblings, idx)
    to_delete = body if replace else [b for b in body if _is_empty_placeholder(b)]
    err = _delete_blocks(request, to_delete)
    if err:
        return err
    if not blocks:
        return None
    return _insert_after(request, parent_id, siblings[idx]["id"], blocks)


def append_to_section(request, groups, heading_text, blocks):
    """heading 섹션의 끝(경계 직전)에 blocks를 덧붙인다. 빈 placeholder는 먼저 지운다.

    페이지 끝 append로는 '실행 기록' 같은 중간 섹션에 누적 기록을 쌓을 수 없어서 쓴다.
    반환: None | "missing" | error dict.
    """
    # 사람이 CLI에 괄호 설명까지 치지 않도록 정확 일치가 없으면 접두어로 찾는다("성장 회고").
    located = _locate(groups, heading_text) or _locate(groups, heading_text, prefix=True)
    if located is None:
        return "missing"
    parent_id, siblings, idx = located
    body = _section_range(siblings, idx)
    placeholders = [b for b in body if _is_empty_placeholder(b)]
    err = _delete_blocks(request, placeholders)
    if err:
        return err
    remaining = [b for b in body if b not in placeholders]
    anchor = remaining[-1]["id"] if remaining else siblings[idx]["id"]
    return _insert_after(request, parent_id, anchor, blocks)
