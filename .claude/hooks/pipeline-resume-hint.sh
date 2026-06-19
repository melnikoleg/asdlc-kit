#!/bin/bash
# Stop hook: remind about paused pipelines
find docs/ -name "STATE.json" 2>/dev/null | while read f; do
  PHASE=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('phase','done'))" 2>/dev/null)
  if [ "$PHASE" != "done" ] && [ "$PHASE" != "escalated" ]; then
    ISSUE=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('issue','unknown'))" 2>/dev/null)
    echo "[SDLC] Pipeline '$ISSUE' paused at phase='$PHASE'. Resume: /factory $ISSUE --resume" >&2
  fi
done
exit 0
