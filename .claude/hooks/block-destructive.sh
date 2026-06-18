#!/bin/bash
# PreToolUse(Bash): block dangerous shell commands
INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('command',''))" 2>/dev/null)
for pat in "rm -rf /" "rm -rf ~" "git push --force" "git push -f" "> /dev/sda" "mkfs" "format c:"; do
  if echo "$CMD" | grep -qF "$pat"; then
    echo '{"decision":"block","reason":"Destructive command blocked by SDLC guardrail"}'
    exit 2
  fi
done
exit 0
