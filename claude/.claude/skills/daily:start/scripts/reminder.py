#!/usr/bin/env python3
"""
reminder.py — Summarize recent Obsidian notes for daily reminder

Scans 02. Notes/ and 03. Resources/ for notes created in the last N days.
Returns title + first meaningful bullet as a 1-2 line summary.

Usage:
    python3 reminder.py --vault "/path/to/vault"
    python3 reminder.py --vault "/path/to/vault" --days 7 --count 5

Output JSON:
{
  "reminders": [
    {
      "title": "Aurora PostgreSQL Autovacuum",
      "date": "2026-04-17",
      "summary": "Dead tuple 정리 → bloat 방지 → 성능 유지. 트랜잭션 wrap-around 방지가 핵심.",
      "path": "02. Notes/engineering/aurora-autovacuum.md"
    }
  ]
}
"""

import json
import os
import re
import sys
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path


SCAN_DIRS = [
    "02. Notes/engineering",
    "02. Notes/others",
    "03. Resources/tech-specs",
    "03. Resources/runbooks",
    "03. Resources/troubleshooting",
    "03. Resources/cheatsheets",
]


def parse_frontmatter(content: str) -> dict:
    if not content.startswith('---'):
        return {}
    end = content.find('\n---', 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    result = {}
    current_list_key = None
    for line in fm_text.split('\n'):
        if current_list_key and re.match(r'^\s+-\s+', line):
            result[current_list_key].append(re.sub(r'^\s+-\s+', '', line).strip().strip('"\''))
            continue
        current_list_key = None
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip().strip('"\'')
        if val.startswith('[') and val.endswith(']'):
            val = [v.strip().strip('"\'') for v in val[1:-1].split(',') if v.strip()]
        elif val == '':
            result[key] = []
            current_list_key = key
            continue
        result[key] = val
    return result


def extract_summary(content: str, max_chars: int = 200) -> str:
    """Extract first 1-2 meaningful bullets from note body."""
    if content.startswith('---'):
        end = content.find('\n---', 3)
        if end != -1:
            content = content[end + 4:]

    bullets = []
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('---') or line.startswith('```'):
            continue
        if line.startswith('- ') or line.startswith('* '):
            text = line[2:].strip()
            if len(text) > 8 and not text.startswith('[[') and not text.startswith('!'):
                bullets.append(text)
                if len(bullets) >= 2:
                    break
        elif len(line) > 15 and not line.startswith('|') and not line.startswith('!'):
            bullets.append(line)
            if len(bullets) >= 2:
                break

    summary = ' '.join(bullets)
    return summary[:max_chars] if summary else ""


def scan_vault(vault_path: Path, days: int) -> list:
    cutoff = date.today() - timedelta(days=days)
    notes = []

    for rel_dir in SCAN_DIRS:
        scan_dir = vault_path / rel_dir
        if not scan_dir.exists():
            continue
        for md_file in scan_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding='utf-8')
                fm = parse_frontmatter(content)
                if fm.get('type') == 'daily':
                    continue

                note_date_str = fm.get('date', '')
                note_date = None
                if note_date_str:
                    try:
                        note_date = datetime.strptime(str(note_date_str).strip(), '%Y-%m-%d').date()
                    except ValueError:
                        pass

                if note_date is None or note_date < cutoff:
                    continue

                title = fm.get('title', md_file.stem)
                summary = extract_summary(content)

                notes.append({
                    'title': title,
                    'date': str(note_date_str),
                    'summary': summary,
                    'path': str(md_file.relative_to(vault_path)),
                    '_date_obj': note_date,
                })
            except Exception:
                continue

    # Sort by date descending (most recent first)
    notes.sort(key=lambda x: x['_date_obj'], reverse=True)
    for n in notes:
        del n['_date_obj']
    return notes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vault', required=True, help='Obsidian vault path')
    parser.add_argument('--days', type=int, default=7, help='Look back N days (default: 7)')
    parser.add_argument('--count', type=int, default=5, help='Max items to return (default: 5)')
    args = parser.parse_args()

    vault_path = Path(os.path.expanduser(args.vault))
    if not vault_path.exists():
        print(json.dumps({'error': f'vault not found: {vault_path}', 'reminders': []}))
        sys.exit(1)

    notes = scan_vault(vault_path, args.days)
    print(json.dumps({'reminders': notes[:args.count]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
