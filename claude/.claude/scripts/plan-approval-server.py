#!/usr/bin/env python3
"""Plan approval server.

Usage: plan-approval-server.py <plan.md> [--pause-out FILE] [--port N] [--no-open]

Serves the plan as HTML with 승인 / 논의 / 거부 buttons. Blocks until the user
submits (or the timeout fires), then prints exactly one bare word to stdout:

  approve | pause | reject | timeout

stdout stays a single word on purpose. plan-preview.sh reads it with
`DECISION=$(...)` and its `case` has a catch-all that falls back to the terminal
prompt, so any stray print here would silently turn an approval into "the hook
did nothing". The 논의 payload therefore travels via --pause-out, not stdout.
"""
import argparse
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import importlib.util
from http.server import HTTPServer, BaseHTTPRequestHandler

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# The shell hook's timeout must exceed this so the server always dies first and
# the shell still has time to emit its JSON. Invariant:
#   SERVER_TIMEOUT + 60 <= settings.json PreToolUse(ExitPlanMode) timeout
SERVER_TIMEOUT = 840

MAX_POST_BYTES = 512 * 1024
ABANDON_GRACE = 8  # seconds to wait after a tab close, in case it was a reload
DECIDE_GRACE = 3   # seconds after a decision, so /done can still be served

server_instance = None
plan_html_content = ""
_decision = None            # "approve" | "pause" | "reject"
_pause_out = None
_csrf = secrets.token_urlsafe(16)
_origin = None
_abandon_at = None
_last_load = 0.0


def load_plan_to_html():
    path = os.path.join(SCRIPTS_DIR, "plan-to-html.py")
    spec = importlib.util.spec_from_file_location("plan_to_html", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DONE_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Plan {label}</title>
<style>
:root {{ --paper: #F6F7F9; --ink: #171A21; --muted: #5B6472; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --paper: #14161B; --ink: #E7E9EE; --muted: #8A93A3; }}
}}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;display:flex;
       align-items:center;justify-content:center;height:100vh;margin:0;background:var(--paper) }}
.msg {{ text-align:center;color:{color};font-size:1.5rem;font-weight:700;letter-spacing:-.02em }}
.sub {{ color:var(--muted);font-size:0.95rem;margin-top:8px;font-weight:400 }}
</style>
</head><body>
<div>
  <div class="msg">Plan {label}</div>
  <div class="sub">{sub}</div>
</div>
</body></html>"""

DONE_VARIANTS = {
    "approve": ("Approved", "#16a34a", "You can close this window"),
    "reject": ("Rejected", "#dc2626", "You can close this window"),
    "pause": ("Paused for discussion", "#3A55A6",
              "논의 내용을 Claude에게 전달했습니다. 터미널로 돌아가십시오."),
}


def build_pause_reason(fields):
    """Compose the prose handed back to Claude as permissionDecisionReason.

    Built here rather than in the shell so the user's text never passes through
    a shell command line. Emitted as plain UTF-8; plan-preview.sh reads the file
    and lets json.dumps do the escaping.

    The user's own words go inside a code fence: pasted text that happens to be
    shaped like an instruction should read as data, not as a directive.
    """
    questions = []
    for k in sorted(fields, key=lambda s: (len(s), s)):
        if not k.startswith("quiz_"):
            continue
        n = k[len("quiz_"):]
        label = (fields.get(f"quizq_{n}") or [""])[0].strip()
        answer = (fields.get(k) or [""])[0].strip()
        questions.append((n, label, answer))

    answered = [q for q in questions if q[2]]
    skipped = [q[0] for q in questions if not q[2]]

    parts = [
        "[PLAN PAUSED] 사용자가 승인을 보류하고 논의를 요청했습니다.",
        "플랜은 아직 승인되지 않았습니다. plan mode를 유지하고, 코드나 파일을 수정하지 마십시오.",
        "",
        "아래 순서를 그대로 따르십시오.",
        "",
    ]

    step = 1
    if answered:
        parts += [f"## {step}. 이해 점검 답변 채점 (먼저 수행)", ""]
        for n, label, answer in answered:
            parts.append(f"### Q{n}: {label}" if label else f"### Q{n}")
            parts.append("사용자 답변:")
            parts.append("```")
            parts.extend(answer.splitlines())
            parts.append("```")
            parts.append("")
        if skipped:
            parts += [f"미응답: Q{', Q'.join(skipped)} (채점하지 않습니다)", ""]
        parts += [
            "각 문항을 정답 / 부분정답 / 오답으로 판정하고, 부분정답과 오답은 1~2문장으로 교정하십시오.",
            "채점 결과를 먼저 출력한 뒤 다음 단계로 넘어갑니다.",
            "",
        ]
        step += 1

    discussion = (fields.get("discussion") or [""])[0].strip()
    parts += [f"## {step}. 논의 사항 (사용자 입력 원문)", "", "```"]
    parts.extend((discussion or "(없음)").splitlines())
    parts += ["```", ""]

    parts += [
        f"## {step + 1}. 플랜 수정 후 재제출",
        "",
        "위 내용을 반영해 플랜을 수정하고 ExitPlanMode를 다시 호출하십시오.",
        "플랜 전체를 폐기하지 말고, 무엇을 바꿨는지 '변경점' 목록으로 먼저 제시한 뒤 재제출합니다.",
        "동일한 플랜을 그대로 재제출하지 마십시오.",
    ]
    return "\n".join(parts)[:8000]


class PlanHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body=b"", ctype="text/html; charset=utf-8"):
        self.send_response(code)
        if body:
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        global _last_load
        path = self.path.split("?", 1)[0]

        if path == "/":
            _last_load = time.time()
            self._send(200, plan_html_content.encode("utf-8"))
            return

        if path == "/done":
            action = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query).get("action", [""])[0]
            label, color, sub = DONE_VARIANTS.get(action, DONE_VARIANTS["reject"])
            body = DONE_HTML.format(label=label, color=color, sub=sub).encode("utf-8")
            self._send(200, body)
            try:
                self.wfile.flush()
            except OSError:
                pass
            threading.Thread(target=_delayed_shutdown, daemon=True).start()
            return

        self._send(404)

    def do_POST(self):
        global _decision, _abandon_at
        path = self.path.split("?", 1)[0]

        if path == "/abandon":
            # Tab closed without deciding. Not acted on immediately: a reload
            # also fires pagehide, and shutting down there would break the page
            # the user is coming back to.
            if _decision is None:
                _abandon_at = time.time()
            self._send(204)
            return

        if path != "/decide":
            self._send(404)
            return

        # Any page the user has open can POST to localhost. Without these two
        # checks a drive-by request could approve a plan nobody read.
        origin = self.headers.get("Origin")
        if origin and origin != _origin:
            self._send(403)
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send(400)
            return
        if length > MAX_POST_BYTES:
            self._send(413)
            return

        raw = self.rfile.read(length).decode("utf-8", "replace")
        fields = urllib.parse.parse_qs(raw, keep_blank_values=True)

        if (fields.get("csrf") or [""])[0] != _csrf:
            self._send(403)
            return

        action = (fields.get("action") or ["pause"])[0]
        if action not in ("approve", "pause", "reject"):
            action = "pause"
        _decision = action

        if action == "pause" and _pause_out:
            try:
                with open(_pause_out, "w", encoding="utf-8") as f:
                    f.write(build_pause_reason(fields))
            except OSError as exc:
                print(f"pause payload write failed: {exc}", file=sys.stderr)

        # 303 so the redirect is a GET; refreshing /done must not re-POST.
        self.send_response(303)
        self.send_header("Location", f"/done?action={action}")
        self.end_headers()

        # The decision itself is the shutdown trigger, not the /done page. If a
        # client does not follow the redirect the decision is already made, and
        # waiting for a page that will never be requested would hang the hook
        # until its timeout. /done's own shutdown normally fires first.
        threading.Thread(target=_delayed_shutdown, args=(DECIDE_GRACE,),
                         daemon=True).start()


def _delayed_shutdown(delay=1.5):
    time.sleep(delay)
    if server_instance:
        server_instance.shutdown()


def _timeout_shutdown(seconds):
    time.sleep(seconds)
    if server_instance:
        server_instance.shutdown()


def _orphan_watchdog():
    """Exit if the parent shell died. The shell's EXIT trap covers a clean exit
    but not SIGKILL, and an orphan would hold its port and could later pop a
    stale page for a plan nobody is waiting on."""
    while True:
        time.sleep(5)
        if _decision:
            return
        if os.getppid() == 1 and server_instance:
            server_instance.shutdown()
            return


def _abandon_watchdog():
    while True:
        time.sleep(2)
        if _decision:
            return
        if (_abandon_at and time.time() - _abandon_at > ABANDON_GRACE
                and _last_load < _abandon_at and server_instance):
            server_instance.shutdown()
            return


def main():
    global server_instance, plan_html_content, _pause_out, _origin

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("plan")
    ap.add_argument("--pause-out")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    md_path = os.path.expanduser(args.plan)
    if not os.path.exists(md_path):
        print(f"File not found: {md_path}", file=sys.stderr)
        sys.exit(1)
    _pause_out = args.pause_out

    try:
        mod = load_plan_to_html()
        plan_html_content = mod.render(md_path, mode="server").replace("__CSRF__", _csrf)
    except Exception as exc:
        print(f"HTML generation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # A renderer refactor that dropped the form would otherwise serve a page
    # with no way to approve, and the only symptom would be a long hang.
    if 'id="plan-form"' not in plan_html_content:
        print("WARN: decision form missing from rendered plan", file=sys.stderr)

    # Port 0 lets the OS assign. Probing for a free port and closing the socket
    # before binding left a window where two concurrent sessions collided.
    server_instance = HTTPServer(("127.0.0.1", args.port), PlanHandler)
    port = server_instance.server_address[1]
    _origin = f"http://127.0.0.1:{port}"

    threading.Thread(target=_timeout_shutdown, args=(SERVER_TIMEOUT,), daemon=True).start()
    threading.Thread(target=_orphan_watchdog, daemon=True).start()
    threading.Thread(target=_abandon_watchdog, daemon=True).start()

    if args.no_open:
        print(f"{_origin}/", file=sys.stderr)
    else:
        subprocess.Popen(["open", f"{_origin}/"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    server_instance.serve_forever()

    print(_decision or "timeout", flush=True)


if __name__ == "__main__":
    main()
