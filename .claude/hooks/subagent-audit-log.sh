#!/bin/bash
# SubagentStop hook: append to audit log
mkdir -p docs 2>/dev/null
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] subagent-stop" >> docs/.sdlc-audit.log 2>/dev/null
exit 0
