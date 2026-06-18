#!/bin/bash
# PreToolUse(Write): block writes to sensitive files
INPUT=$(cat)
FP=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)
for pat in ".env" "id_rsa" "id_ed25519" ".pem" "kubeconfig" ".aws/credentials" "secrets.yml"; do
  if [[ "$FP" == *"$pat"* ]]; then
    echo '{"decision":"block","reason":"Write to sensitive file blocked by SDLC guardrail"}'
    exit 2
  fi
done
exit 0
