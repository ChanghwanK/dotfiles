#!/bin/bash
# claude-mem 로그 로테이션 — 7일 이상 된 로그 삭제
find ~/.claude-mem/logs/ -name "*.log" -mtime +7 -delete
