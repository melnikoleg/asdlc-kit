#!/bin/bash
# PostToolUse(Write): warn if SDLC artifacts missing required sections
INPUT=$(cat)
FP=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)
case "$FP" in
  */PRD.md)
    grep -q "Acceptance Criteria" "$FP" 2>/dev/null || echo "[SDLC] WARNING: PRD.md missing Acceptance Criteria section" >&2 ;;
  */PLAN.md)
    grep -q "Validation:" "$FP" 2>/dev/null || echo "[SDLC] WARNING: PLAN.md missing Validation commands" >&2 ;;
  */REVIEW.md|*/QA.md|*/DEPLOY.md)
    grep -qE "Verdict: (APPROVED|NEEDS_FIX)" "$FP" 2>/dev/null || echo "[SDLC] WARNING: Missing Verdict line in $FP" >&2 ;;
esac
exit 0
