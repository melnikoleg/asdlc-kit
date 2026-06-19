#!/bin/bash
# PostToolUse(Write): warn if SDLC artifacts are missing required content.
# Checks go beyond heading presence where possible (e.g. real evidence blocks),
# so the "evidence required" guarantee is not satisfiable by an empty heading.
INPUT=$(cat)
FP=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)
case "$(basename "$FP")" in
  PRD.md)
    grep -q "Acceptance Criteria" "$FP" 2>/dev/null || echo "[SDLC] WARNING: PRD.md missing 'Acceptance Criteria' section" >&2 ;;
  PLAN.md)
    grep -q "Validation:" "$FP" 2>/dev/null || echo "[SDLC] WARNING: PLAN.md missing 'Validation:' commands" >&2 ;;
  REVIEW.md|QA.md|DEPLOY.md)
    grep -qE "Verdict: (APPROVED|NEEDS_FIX)" "$FP" 2>/dev/null || echo "[SDLC] WARNING: $FP missing Verdict line" >&2 ;;
  IMPLEMENTATION.md)
    if ! grep -q "Validation Evidence" "$FP" 2>/dev/null; then
      echo "[SDLC] WARNING: IMPLEMENTATION.md missing 'Validation Evidence' section" >&2
    elif ! grep -q '```' "$FP" 2>/dev/null; then
      echo "[SDLC] WARNING: IMPLEMENTATION.md has no command-output block — evidence must be real captured output, not a heading" >&2
    fi ;;
esac
exit 0
