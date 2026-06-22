#!/usr/bin/env python3
"""reconcile-progress 순수 함수 회귀 테스트 (Notion 호출 없음).

매칭·보정 로직이 결정론적임을 문서화하고 보호한다.
실행: python3 test_reconcile.py   (성공 시 exit 0)
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location("nt", os.path.join(_HERE, "notion-task.py"))
m = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(m)

_failures = []


def chk(desc, got, want):
    if got != want:
        _failures.append(f"{desc}: got={got!r} want={want!r}")


# ── 매칭: prefix 제거 + 부분일치 + 토큰 중첩 임계 ───────────────
chk("[Top 3] prefix 무시", m.match_daily_to_task("[Top 3] ES Cloud 제거", "ES Cloud 제거"), True)
chk("[검토] prefix + 부분일치", m.match_daily_to_task("[검토] GPU Operator 이관", "GPU Operator 이관 작업"), True)
chk("무관 항목 불일치", m.match_daily_to_task("점심 약속", "VictoriaMetrics 업그레이드"), False)
chk("부분문자열 일치", m.match_daily_to_task("Karpenter", "Karpenter 노드풀 정리"), True)
chk("토큰 중첩 임계 미만 불일치", m.match_daily_to_task("로그 확인", "Loki 인덱스 재구성 작업"), False)

# ── 보정 규칙: Notion status 가 진실 소스 ──────────────────────
daily = [
    {"text": "[검토] A 작업", "done": False},  # Notion 완료 → 완료로 보정 (Daily Note 지연)
    {"text": "B 배포", "done": False},          # Notion 진행 중 → 미완료 유지
    {"text": "C 정리", "done": True},           # 매칭 없음 → daily 값(완료) 유지
    {"text": "D 미정", "done": False},          # 매칭 없음 → daily 값(미완료) 유지
]
notion = [
    {"name": "A 작업", "status": "완료"},
    {"name": "B 배포 파이프라인", "status": "진행 중"},
]
rec, done, total = m.reconcile_items(daily, notion)
chk("total 항목 수", total, 4)
chk("보정 후 done", done, 2)  # A(완료 보정) + C(daily True)
chk("A correction=lag", rec[0]["correction"], "daily-note-lag")
chk("A effective_done", rec[0]["effective_done"], True)
chk("B 진행중 미완료 유지", rec[1]["effective_done"], False)
chk("C 매칭없음 daily 유지", rec[2]["effective_done"], True)
chk("D 매칭없음 미완료 유지", rec[3]["effective_done"], False)

if _failures:
    print("FAIL ✗")
    for f in _failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL PASS ✓")
