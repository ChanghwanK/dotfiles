#!/usr/bin/env python3
"""
Notion Infra PM CLI

Usage:
  notion-infra-pm.py create-db [--parent-page-id <id>]
  notion-infra-pm.py save-assessment --data '<json>'
  notion-infra-pm.py list-assessments [--dimension reliability|operability|all] [--cluster all|prod|idc|global] [--limit N]
  notion-infra-pm.py dashboard
  notion-infra-pm.py list-improvements [--limit N]
  notion-infra-pm.py create-backlog --items '<json_array>' [--dry-run]
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
import argparse

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")

# Assessment DB ID (set after create-db, or hardcoded after first creation)
# This will be populated after the first create-db run
ASSESSMENT_DB_ID = os.environ.get("INFRA_PM_DB_ID", "")

# Task DB ID (from notion-task.py)
TASK_DB_ID = "2da64745-3170-8072-80bd-fb05cf592929"

# North Star target scores per dimension (0-100)
NORTH_STAR_TARGETS = {
    "Reliability": 90,
    "Operability": 85,
    "Security": 90,
    "Observability": 85,
    "Cost": 80,
    "Scalability": 80,
}

# Assessment priority → Notion Task Priority
PRIORITY_MAP = {
    "P1": "P1 - Must Have",
    "P2": "P2 - Nice to Have",
    "P3": "P2 - Nice to Have",
}

# Config file path to persist DB ID
CONFIG_PATH = os.path.expanduser("~/.claude/skills/devops:infra-pm/assets/config.json")


def get_token():
    token = NOTION_TOKEN
    if not token:
        print("Error: NOTION_TOKEN environment variable not set", file=sys.stderr)
        print("Tip: NOTION_TOKEN=$(op read 'op://Employee/Notion API Token/credential') python3 ...", file=sys.stderr)
        sys.exit(1)
    return token


def notion_request(token, method, path, body=None):
    url = f"https://api.notion.com/v1{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"HTTP {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)


def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_db_id():
    db_id = ASSESSMENT_DB_ID
    if not db_id:
        config = load_config()
        db_id = config.get("assessment_db_id", "")
    if not db_id:
        print("Error: Assessment DB ID not configured.", file=sys.stderr)
        print("Run 'notion-infra-pm.py create-db' first.", file=sys.stderr)
        sys.exit(1)
    return db_id


def cmd_create_db(args):
    token = get_token()

    parent_page_id = getattr(args, "parent_page_id", None)
    if not parent_page_id:
        # Try to get from config
        config = load_config()
        parent_page_id = config.get("parent_page_id", "")

    if not parent_page_id:
        print("Error: --parent-page-id is required for first setup.", file=sys.stderr)
        print("Tip: Find a Notion page ID from the page URL (32-char hex after last /)", file=sys.stderr)
        sys.exit(1)

    # Create Assessment DB
    db_body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "Infra PM Assessment DB"}}],
        "properties": {
            "이름": {"title": {}},
            "Date": {"date": {}},
            "Dimension": {
                "select": {
                    "options": [
                        {"name": "Reliability", "color": "red"},
                        {"name": "Operability", "color": "blue"},
                        {"name": "Security", "color": "orange"},
                        {"name": "Observability", "color": "green"},
                        {"name": "Cost", "color": "yellow"},
                        {"name": "Scalability", "color": "purple"},
                    ]
                }
            },
            "Cluster": {
                "select": {
                    "options": [
                        {"name": "infra-k8s-prod", "color": "red"},
                        {"name": "infra-k8s-idc", "color": "orange"},
                        {"name": "infra-k8s-global", "color": "blue"},
                    ]
                }
            },
            "Score": {"number": {"format": "number"}},
            "Findings": {"rich_text": {}},
            "Improvements": {"rich_text": {}},
            "Metrics": {"rich_text": {}},
        },
    }

    resp = notion_request(token, "POST", "/databases", db_body)
    db_id = resp["id"]

    config = load_config()
    config["assessment_db_id"] = db_id
    config["parent_page_id"] = parent_page_id
    save_config(config)

    print(json.dumps({
        "created": True,
        "db_id": db_id,
        "db_url": resp.get("url", ""),
        "message": "Assessment DB created. DB ID saved to config.",
    }, ensure_ascii=False, indent=2))


def cmd_save_assessment(args):
    token = get_token()
    db_id = get_db_id()

    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in --data: {e}", file=sys.stderr)
        sys.exit(1)

    dimension = data.get("dimension", "unknown").capitalize()
    cluster = data.get("cluster", "unknown")
    score = data.get("score")
    metrics = data.get("metrics", {})
    findings = data.get("findings", [])
    improvement_items = data.get("improvement_items", [])

    today = date.today().isoformat()
    week_num = datetime.now().isocalendar()[1]
    year = datetime.now().year
    page_title = f"{year}-W{week_num:02d} {cluster} {dimension}"

    findings_text = "\n".join(findings[:20]) if findings else "No findings"
    improvements_text = json.dumps(improvement_items[:20], ensure_ascii=False) if improvement_items else "[]"
    metrics_text = json.dumps(metrics, ensure_ascii=False) if metrics else "{}"

    properties = {
        "이름": {"title": [{"text": {"content": page_title}}]},
        "Date": {"date": {"start": today}},
        "Dimension": {"select": {"name": dimension}},
        "Cluster": {"select": {"name": cluster}},
        "Findings": {"rich_text": [{"text": {"content": findings_text[:2000]}}]},
        "Improvements": {"rich_text": [{"text": {"content": improvements_text[:2000]}}]},
        "Metrics": {"rich_text": [{"text": {"content": metrics_text[:2000]}}]},
    }

    if score is not None:
        properties["Score"] = {"number": score}

    resp = notion_request(token, "POST", "/pages", {
        "parent": {"database_id": db_id},
        "properties": properties,
    })

    print(json.dumps({
        "saved": True,
        "page_id": resp["id"],
        "title": page_title,
        "score": score,
        "dimension": dimension,
        "cluster": cluster,
    }, ensure_ascii=False, indent=2))


def cmd_list_assessments(args):
    token = get_token()
    db_id = get_db_id()

    filters = []

    dimension = getattr(args, "dimension", "all")
    if dimension and dimension != "all":
        filters.append({
            "property": "Dimension",
            "select": {"equals": dimension.capitalize()},
        })

    cluster = getattr(args, "cluster", "all")
    if cluster and cluster != "all":
        cluster_map = {
            "prod": "infra-k8s-prod",
            "idc": "infra-k8s-idc",
            "global": "infra-k8s-global",
        }
        cluster_name = cluster_map.get(cluster, cluster)
        filters.append({
            "property": "Cluster",
            "select": {"equals": cluster_name},
        })

    query_body = {
        "sorts": [{"property": "Date", "direction": "descending"}],
        "page_size": getattr(args, "limit", 20) or 20,
    }
    if len(filters) == 1:
        query_body["filter"] = filters[0]
    elif len(filters) > 1:
        query_body["filter"] = {"and": filters}

    resp = notion_request(token, "POST", f"/databases/{db_id}/query", query_body)
    items = resp.get("results", [])

    assessments = []
    for item in items:
        props = item.get("properties", {})
        title_parts = props.get("이름", {}).get("title", [])
        title = "".join(t.get("plain_text", "") for t in title_parts)
        date_val = props.get("Date", {}).get("date", {})
        dim_val = props.get("Dimension", {}).get("select", {})
        cluster_val = props.get("Cluster", {}).get("select", {})
        score_val = props.get("Score", {}).get("number")
        findings_val = props.get("Findings", {}).get("rich_text", [])
        findings_text = "".join(f.get("plain_text", "") for f in findings_val)

        assessments.append({
            "page_id": item["id"],
            "title": title,
            "date": date_val.get("start") if date_val else None,
            "dimension": dim_val.get("name") if dim_val else None,
            "cluster": cluster_val.get("name") if cluster_val else None,
            "score": score_val,
            "findings_preview": findings_text[:200],
        })

    print(json.dumps({
        "count": len(assessments),
        "assessments": assessments,
    }, ensure_ascii=False, indent=2))


def search_existing_tasks(token, title_keyword):
    """Task DB에서 유사 제목의 기존 Task를 검색한다 (중복 방지용)."""
    keyword = title_keyword[:30]
    body = {
        "filter": {
            "property": "이름",
            "title": {"contains": keyword},
        },
        "page_size": 5,
    }
    try:
        resp = notion_request(token, "POST", f"/databases/{TASK_DB_ID}/query", body)
        return resp.get("results", [])
    except SystemExit:
        return []  # 검색 실패 시 중복 없는 것으로 처리


def cmd_list_improvements(args):
    """최근 Assessment DB에서 improvement_items를 집계하여 반환한다."""
    token = get_token()
    db_id = get_db_id()

    limit = getattr(args, "limit", 12) or 12
    resp = notion_request(token, "POST", f"/databases/{db_id}/query", {
        "sorts": [{"property": "Date", "direction": "descending"}],
        "page_size": limit,
    })
    items = resp.get("results", [])

    all_improvements = []
    seen_titles = set()

    for item in items:
        props = item.get("properties", {})
        dim_val = props.get("Dimension", {}).get("select", {})
        cluster_val = props.get("Cluster", {}).get("select", {})
        improvements_val = props.get("Improvements", {}).get("rich_text", [])
        improvements_text = "".join(f.get("plain_text", "") for f in improvements_val)

        dimension = dim_val.get("name") if dim_val else "unknown"
        cluster = cluster_val.get("name") if cluster_val else "unknown"

        if not improvements_text or improvements_text == "[]":
            continue

        try:
            improvement_items = json.loads(improvements_text)
        except json.JSONDecodeError:
            continue

        for imp in improvement_items:
            title = imp.get("title", "").strip()
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            all_improvements.append({
                "title": title,
                "priority": imp.get("priority", "P2"),
                "dimension": dimension,
                "cluster": cluster,
            })

    # P1 → P2 → P3 순 정렬
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    all_improvements.sort(key=lambda x: priority_order.get(x["priority"], 99))

    print(json.dumps({
        "count": len(all_improvements),
        "items": all_improvements,
    }, ensure_ascii=False, indent=2))


def cmd_create_backlog(args):
    """improvement_items를 Notion Task DB에 적재한다 (중복 Task는 스킵)."""
    token = get_token()

    try:
        items = json.loads(args.items)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in --items: {e}", file=sys.stderr)
        sys.exit(1)

    dry_run = getattr(args, "dry_run", False)

    # 기본 Due Date: 다음 월요일
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    next_monday = (today + timedelta(days=days_until_monday)).isoformat()

    created = []
    skipped = []

    for item in items:
        title = item.get("title", "").strip()
        priority = item.get("priority", "P2")
        cluster = item.get("cluster", "")

        if not title:
            continue

        # 클러스터 단축명 포함한 Task 이름
        if cluster:
            short_cluster = cluster.replace("infra-k8s-", "")
            task_name = f"[{short_cluster}] {title}"
        else:
            task_name = f"[Infra PM] {title}"

        # 중복 체크: 원본 title 앞 25자로 검색
        existing = search_existing_tasks(token, title[:25])
        if existing:
            skipped.append({
                "title": task_name,
                "reason": "duplicate",
                "existing_id": existing[0]["id"],
            })
            continue

        if dry_run:
            created.append({"title": task_name, "priority": priority, "dry_run": True})
            continue

        # Task 생성
        notion_priority = PRIORITY_MAP.get(priority, "P2 - Nice to Have")
        resp = notion_request(token, "POST", "/pages", {
            "parent": {"database_id": TASK_DB_ID},
            "properties": {
                "이름": {"title": [{"text": {"content": task_name}}]},
                "Priority": {"select": {"name": notion_priority}},
                "Group": {"select": {"name": "WORK"}},
                "Due Date": {"date": {"start": next_monday}},
            },
        })
        created.append({
            "title": task_name,
            "page_id": resp["id"],
            "priority": notion_priority,
            "due": next_monday,
        })

    print(json.dumps({
        "created_count": len(created),
        "skipped_count": len(skipped),
        "dry_run": dry_run,
        "created": created,
        "skipped": skipped,
    }, ensure_ascii=False, indent=2))


def cmd_gap_report(args):
    """최근 Assessment 점수와 North Star 목표를 비교하여 Gap 리포트를 반환한다."""
    token = get_token()
    db_id = get_db_id()

    resp = notion_request(token, "POST", f"/databases/{db_id}/query", {
        "sorts": [{"property": "Date", "direction": "descending"}],
        "page_size": 50,
    })
    items = resp.get("results", [])

    # 최신 점수 매트릭스 구성
    score_matrix = {}
    for item in items:
        props = item.get("properties", {})
        dim_val = props.get("Dimension", {}).get("select", {})
        cluster_val = props.get("Cluster", {}).get("select", {})
        score_val = props.get("Score", {}).get("number")
        date_val = props.get("Date", {}).get("date", {})

        dim = dim_val.get("name") if dim_val else None
        cluster = cluster_val.get("name") if cluster_val else None

        if dim and cluster:
            key = f"{dim}:{cluster}"
            if key not in score_matrix:
                score_matrix[key] = {
                    "dimension": dim,
                    "cluster": cluster,
                    "score": score_val,
                    "date": date_val.get("start") if date_val else None,
                }

    # Gap 계산
    gaps = []
    for key, entry in score_matrix.items():
        dim = entry["dimension"]
        score = entry["score"]
        target = NORTH_STAR_TARGETS.get(dim)
        if score is not None and target is not None:
            gap = target - score
            grade = "Excellent" if score >= 90 else "Good" if score >= 75 else "Fair" if score >= 60 else "Poor"
            gaps.append({
                "dimension": dim,
                "cluster": entry["cluster"],
                "score": score,
                "target": target,
                "gap": gap,
                "grade": grade,
                "date": entry["date"],
            })

    # Gap 큰 순서로 정렬
    gaps.sort(key=lambda x: -x["gap"])

    print(json.dumps({
        "gaps": gaps,
        "north_star_targets": NORTH_STAR_TARGETS,
    }, ensure_ascii=False, indent=2))


def cmd_dashboard(args):
    token = get_token()
    db_id = get_db_id()

    # Get latest assessment per (dimension, cluster) combination
    resp = notion_request(token, "POST", f"/databases/{db_id}/query", {
        "sorts": [{"property": "Date", "direction": "descending"}],
        "page_size": 50,
    })
    items = resp.get("results", [])

    # Build latest score matrix
    score_matrix = {}
    for item in items:
        props = item.get("properties", {})
        dim_val = props.get("Dimension", {}).get("select", {})
        cluster_val = props.get("Cluster", {}).get("select", {})
        score_val = props.get("Score", {}).get("number")
        date_val = props.get("Date", {}).get("date", {})

        dim = dim_val.get("name") if dim_val else None
        cluster = cluster_val.get("name") if cluster_val else None

        if dim and cluster:
            key = f"{dim}:{cluster}"
            if key not in score_matrix:
                score_matrix[key] = {
                    "dimension": dim,
                    "cluster": cluster,
                    "score": score_val,
                    "date": date_val.get("start") if date_val else None,
                }

    # Format as structured output
    dimensions = ["Reliability", "Operability"]
    clusters = ["infra-k8s-prod", "infra-k8s-idc", "infra-k8s-global"]

    table = []
    for dim in dimensions:
        row = {"dimension": dim}
        for cluster in clusters:
            key = f"{dim}:{cluster}"
            entry = score_matrix.get(key, {})
            row[cluster] = {
                "score": entry.get("score"),
                "date": entry.get("date"),
            }
        table.append(row)

    print(json.dumps({
        "dashboard": table,
        "total_records": len(score_matrix),
        "clusters": clusters,
        "dimensions": dimensions,
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Notion Infra PM CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-db
    create_p = subparsers.add_parser("create-db", help="Create Assessment DB in Notion")
    create_p.add_argument("--parent-page-id", default=None, help="Parent page ID (32-char Notion page ID)")

    # save-assessment
    save_p = subparsers.add_parser("save-assessment", help="Save assessment result to Notion")
    save_p.add_argument("--data", required=True, help="JSON string with assessment data")

    # list-assessments
    list_p = subparsers.add_parser("list-assessments", help="List recent assessments")
    list_p.add_argument("--dimension", choices=["reliability", "operability", "security", "observability", "cost", "scalability", "all"], default="all")
    list_p.add_argument("--cluster", choices=["prod", "idc", "global", "all"], default="all")
    list_p.add_argument("--limit", type=int, default=20, help="Max results to return")

    # dashboard
    subparsers.add_parser("dashboard", help="Show latest score matrix for all dimensions and clusters")

    # list-improvements
    li_p = subparsers.add_parser("list-improvements", help="Aggregate improvement_items from recent assessments")
    li_p.add_argument("--limit", type=int, default=12, help="Max recent assessments to scan (default: 12)")

    # create-backlog
    cb_p = subparsers.add_parser("create-backlog", help="Create Notion Tasks from improvement_items")
    cb_p.add_argument("--items", required=True, help="JSON array of improvement items")
    cb_p.add_argument("--dry-run", action="store_true", help="Preview without creating tasks")

    # gap-report
    subparsers.add_parser("gap-report", help="Compare latest scores against North Star targets")

    args = parser.parse_args()

    cmd_map = {
        "create-db": cmd_create_db,
        "save-assessment": cmd_save_assessment,
        "list-assessments": cmd_list_assessments,
        "dashboard": cmd_dashboard,
        "list-improvements": cmd_list_improvements,
        "create-backlog": cmd_create_backlog,
        "gap-report": cmd_gap_report,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
