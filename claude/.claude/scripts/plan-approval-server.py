#!/usr/bin/env python3
"""
Plan approval server.
Usage: plan-approval-server.py <plan.md>

Serves the plan as HTML with Approve/Reject buttons.
Blocks until the user clicks a button (or 5-min timeout), then prints one of:
  approve | reject | timeout
to stdout and exits.

Parent process (plan-preview.sh) reads this output to decide the hook response.
"""
import sys
import os
import subprocess
import threading
import socket
import time
import importlib.util
from http.server import HTTPServer, BaseHTTPRequestHandler

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

server_instance = None
plan_html_content = ""
_decision = None        # "approve" | "reject"
_decision_event = threading.Event()


def load_plan_to_html():
    path = os.path.join(SCRIPTS_DIR, "plan-to-html.py")
    spec = importlib.util.spec_from_file_location("plan_to_html", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
        global _decision

        if self.path == '/':
            body = plan_html_content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == '/approve':
            _decision = 'approve'
            self.send_response(302)
            self.send_header('Location', '/done?action=approve')
            self.end_headers()

        elif self.path == '/reject':
            _decision = 'reject'
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
            # Signal main thread to shut down after the done page is delivered
            threading.Thread(target=_delayed_shutdown, daemon=True).start()

        else:
            self.send_response(404)
            self.end_headers()


def _delayed_shutdown():
    time.sleep(1.5)
    if server_instance:
        server_instance.shutdown()


def _timeout_shutdown(seconds):
    time.sleep(seconds)
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

    try:
        mod = load_plan_to_html()
        static_out = mod.convert(md_path)
        with open(static_out, encoding='utf-8') as f:
            base_html = f.read()
    except Exception as e:
        print(f"HTML generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    plan_html_content = base_html.replace('<body>', '<body>' + TOOLBAR_HTML, 1)

    server_instance = HTTPServer(('127.0.0.1', port), PlanHandler)

    # Auto-shutdown after 5 minutes (timeout)
    threading.Thread(target=_timeout_shutdown, args=(300,), daemon=True).start()

    subprocess.Popen(['open', f'http://127.0.0.1:{port}/'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Block until approve/reject/timeout
    server_instance.serve_forever()

    # Output the decision for the parent shell script to read
    print(_decision or 'timeout', flush=True)


if __name__ == '__main__':
    main()
