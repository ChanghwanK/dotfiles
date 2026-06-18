#!/usr/bin/env python3
"""
Plan approval server.
Usage: plan-approval-server.py <plan.md>

Serves the plan as HTML with Approve/Reject buttons.
Buttons send keystrokes back to the originating Claude Code terminal.
Auto-exits after 10 minutes.
"""
import sys
import os
import subprocess
import threading
import socket
import time
import importlib.util
from http.server import HTTPServer, BaseHTTPRequestHandler

# Capture terminal env at startup (inherited from Claude Code process)
ITERM_SESSION_ID = os.environ.get('ITERM_SESSION_ID', '')
TMUX = os.environ.get('TMUX', '')
TMUX_PANE = os.environ.get('TMUX_PANE', '')
TERM_PROGRAM = os.environ.get('TERM_PROGRAM', '')

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

server_instance = None
plan_html_content = ""


def load_plan_to_html():
    """Load plan-to-html module from scripts dir (hyphen in filename)."""
    path = os.path.join(SCRIPTS_DIR, "plan-to-html.py")
    spec = importlib.util.spec_from_file_location("plan_to_html", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def send_to_terminal(key):
    """Send 'y' or 'n' + Enter to the Claude Code terminal."""
    if TMUX and TMUX_PANE:
        subprocess.run(['tmux', 'send-keys', '-t', TMUX_PANE, key, 'Enter'],
                       check=False, capture_output=True)
        return

    if ITERM_SESSION_ID or TERM_PROGRAM == 'iTerm.app':
        # target the specific iTerm2 session by inherited session ID
        if ITERM_SESSION_ID:
            # ITERM_SESSION_ID format: "wXtXpX:UUID"
            session_uuid = ITERM_SESSION_ID.split(':')[-1] if ':' in ITERM_SESSION_ID else ''
            if session_uuid:
                script = f'''
tell application "iTerm2"
    repeat with aWindow in windows
        repeat with aTab in tabs of aWindow
            repeat with aSession in sessions of aTab
                if unique id of aSession is "{session_uuid}" then
                    tell aSession to write text "{key}"
                    return
                end if
            end repeat
        end repeat
    end repeat
end tell
'''
                result = subprocess.run(['osascript', '-e', script],
                                        capture_output=True)
                if result.returncode == 0:
                    return
        # fallback: write to current window current session
        script = (
            'tell application "iTerm2" to tell current window '
            f'to tell current session to write text "{key}"'
        )
        subprocess.run(['osascript', '-e', script], capture_output=True)
        return

    # Terminal.app fallback
    script = f'tell application "Terminal" to do script "{key}" in front window'
    subprocess.run(['osascript', '-e', script], capture_output=True)


def find_free_port(start=17823):
    for port in range(start, start + 100):
        try:
            with socket.socket() as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return None


TOOLBAR_HTML = """
  <div style="position:fixed;top:0;left:0;right:0;background:#fff;
              border-bottom:1px solid #e0e0e0;padding:10px 24px;
              display:flex;gap:12px;align-items:center;z-index:999;
              font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px">
    <span style="color:#555;flex:1;font-size:13px">Plan Review — approve or reject below</span>
    <a href="/reject"
       onclick="return confirm('Reject this plan?')"
       style="padding:5px 16px;border-radius:5px;border:1px solid #dc2626;
              color:#dc2626;text-decoration:none;font-weight:500">Reject</a>
    <a href="/approve"
       style="padding:5px 16px;border-radius:5px;background:#16a34a;
              color:#fff;text-decoration:none;font-weight:500">Approve</a>
  </div>
  <div style="height:48px"></div>
"""

DONE_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Plan {label}</title>
<style>body{{font-family:-apple-system,sans-serif;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0;background:#fff}}
.msg{{text-align:center;color:{color};font-size:1.5rem;font-weight:700;letter-spacing:-.02em}}
.sub{{color:#888;font-size:0.95rem;margin-top:8px;font-weight:400}}</style>
</head><body>
<div>
  <div class="msg">Plan {label}</div>
  <div class="sub">You can close this window</div>
</div>
</body></html>"""


class PlanHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        global server_instance

        if self.path == '/':
            body = plan_html_content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == '/approve':
            send_to_terminal('y')
            self.send_response(302)
            self.send_header('Location', '/done?action=approve')
            self.end_headers()

        elif self.path == '/reject':
            send_to_terminal('n')
            self.send_response(302)
            self.send_header('Location', '/done?action=reject')
            self.end_headers()

        elif self.path.startswith('/done'):
            approved = 'approve' in self.path
            label = 'Approved' if approved else 'Rejected'
            color = '#16a34a' if approved else '#dc2626'
            body = DONE_HTML.format(label=label, color=color).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            # shutdown AFTER the done page is fully served
            threading.Thread(target=_delayed_shutdown, daemon=True).start()

        else:
            self.send_response(404)
            self.end_headers()


def _delayed_shutdown():
    time.sleep(1.5)
    if server_instance:
        server_instance.shutdown()


def _auto_shutdown():
    time.sleep(600)  # 10 minutes
    if server_instance:
        server_instance.shutdown()


def main():
    global server_instance, plan_html_content

    if len(sys.argv) < 2:
        print("Usage: plan-approval-server.py <plan.md>", file=sys.stderr)
        sys.exit(1)

    md_path = os.path.expanduser(sys.argv[1])
    if not os.path.exists(md_path):
        print(f"File not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    port = find_free_port()
    if not port:
        print("No free port found", file=sys.stderr)
        sys.exit(1)

    # Generate base HTML via plan-to-html.py
    try:
        mod = load_plan_to_html()
        static_out = mod.convert(md_path)  # also saves .html for offline reference
        with open(static_out, encoding='utf-8') as f:
            base_html = f.read()
    except Exception as e:
        print(f"HTML generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Inject toolbar with Approve/Reject buttons
    plan_html_content = base_html.replace('<body>', '<body>' + TOOLBAR_HTML, 1)

    server_instance = HTTPServer(('127.0.0.1', port), PlanHandler)

    threading.Thread(target=_auto_shutdown, daemon=True).start()

    # Open browser
    subprocess.Popen(['open', f'http://127.0.0.1:{port}/'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    server_instance.serve_forever()


if __name__ == '__main__':
    main()
