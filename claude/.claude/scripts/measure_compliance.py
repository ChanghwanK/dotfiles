"""규칙이 실제로 지켜졌는지 산출물(플랜·장부·피드백 메모리)로 잰다."""
import datetime as dt
import pathlib
import re

HOME = pathlib.Path.home()
PLANS = HOME / ".claude/plans"
LEDGER = HOME / ".dotfiles/claude/.claude/docs/hypothesis-ledger.md"
MEM = HOME / ".claude/projects/-Users-changhwan-workspace-riiid-kubernetes/memory"
SINCE = dt.date(2026, 10, 14)  # 장부 도입일
TODAY = dt.date(2026, 10, 22)

# 1) 장부 도입 이후 '문제와 가설'을 쓴 플랜 수 vs 장부 행 수
plans = []
for p in PLANS.glob("*.md"):
    mtime = dt.date.fromtimestamp(p.stat().st_mtime)
    text = p.read_text(errors="ignore")
    status = re.search(r"(?m)^status:\s*(\w+)", text)
    plans.append((p.name, mtime, "## 문제와 가설" in text, "## 후속 판정" in text, status.group(1) if status else "-"))
recent = [x for x in plans if x[1] >= SINCE]
print("plans total", len(plans), "| since 10-14", len(recent),
      "| with 문제와 가설", sum(x[2] for x in recent), "| with 후속 판정", sum(x[3] for x in recent))
from collections import Counter
print("status (all):", dict(Counter(x[4] for x in plans)))

rows = [l for l in LEDGER.read_text().splitlines() if l.startswith("| 20")]
since_rows = [r for r in rows if r[2:12] >= str(SINCE)]
print("ledger rows", len(rows), "| dated since 10-14", len(since_rows))

# 2) 판정일이 지났는데 결과가 미판정인 행
overdue = 0
for r in rows:
    cols = [c.strip() for c in r.split("|")]
    due = re.findall(r"20\d\d-\d\d-\d\d", cols[4])
    if due and "미판정" in cols[5] and all(dt.date.fromisoformat(d) < TODAY for d in due):
        overdue += 1
        print("  overdue:", cols[1], cols[4], "|", cols[2][:50])
print("overdue unjudged", overdue)

# 3) 피드백 메모리: 생성 월별 건수와 '재발'·'정정' 언급
fb = sorted(MEM.glob("feedback_*.md"))
months = Counter(dt.date.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m") for p in fb)
print("feedback memories by mtime month:", dict(sorted(months.items())))
recur = [p.name for p in fb if re.search(r"재발|다시 |또 |반복|위반", p.read_text(errors="ignore"))]
print("feedback mentioning recurrence/violation:", len(recur))
