#!/usr/bin/env python3
"""
daily:start 브리핑 데이터(JSON)를 HTML 템플릿에 넣어 Artifact로 게시할 페이지를 만든다.

사용법:
  python3 render-report.py --data <brief.json> [--out <file.html>]

- 템플릿: ../assets/report-template.html
- 기본 출력: ~/.claude/tmp/daily-start/<data.date>.html (날짜별 경로라 Artifact가 매일 새 URL로 게시된다)
- 출력: 만든 파일 경로를 담은 JSON 한 줄
"""

import argparse
import json
import sys
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "report-template.html"
DEFAULT_OUT_DIR = Path.home() / ".claude" / "tmp" / "daily-start"
DATA_PLACEHOLDER = "/*__DATA__*/null"
TITLE_PLACEHOLDER = "{{TITLE}}"
REQUIRED_KEYS = ("date", "weekday", "title", "headline")


def embed_json(data: dict) -> str:
    """<script> 안에 넣어도 태그가 닫히지 않도록 이스케이프한다"""
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("</", "<\\/").replace("<!--", "<\\!--")


def escape_title(title: str) -> str:
    return title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="브리핑 데이터 JSON 파일")
    parser.add_argument("--out", help="출력 HTML 경로 (기본: ~/.claude/tmp/daily-start/<date>.html)")
    args = parser.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_KEYS if not data.get(k)]
    if missing:
        print(json.dumps({"success": False, "error": f"missing keys: {missing}"}, ensure_ascii=False))
        return 1

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if DATA_PLACEHOLDER not in template or TITLE_PLACEHOLDER not in template:
        print(json.dumps({"success": False, "error": "template placeholder not found"}, ensure_ascii=False))
        return 1

    page = (
        template
        .replace(TITLE_PLACEHOLDER, escape_title(data["title"]), 1)
        .replace(DATA_PLACEHOLDER, embed_json(data), 1)
    )

    out = Path(args.out) if args.out else DEFAULT_OUT_DIR / f"{data['date']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")

    print(json.dumps({"success": True, "path": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
