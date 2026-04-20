#!/usr/bin/env python3
"""TODO: Replace this placeholder script.

Harness conventions (do not remove):
- Mutating subcommands MUST honor --dry-run (preview-only, no side effects).
- Destructive operations MUST require an explicit --confirm flag.
- All output: JSON via ok()/err() helpers.
"""
import argparse, json, sys

def ok(data):
    print(json.dumps({"success": True, **data}, ensure_ascii=False, indent=2))

def err(msg, **extra):
    print(json.dumps({"success": False, "error": msg, **extra}, ensure_ascii=False, indent=2))
    sys.exit(1)

def cmd_run(args):
    if args.dry_run:
        ok({"dry_run": True, "would_do": "TODO: describe planned action"})
        return
    # TODO: implement actual mutation here
    ok({"message": "TODO: implement"})

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--dry-run", action="store_true",
                       help="Preview without making changes")
    args = parser.parse_args()
    {"run": cmd_run}[args.command](args)

if __name__ == "__main__":
    main()
