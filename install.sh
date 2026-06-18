#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  Agentic SDLC Kit — One-Command Installer
#  Usage: curl -fsSL <url>/install.sh | bash
#     or: bash install.sh [--global] [--project /path/to/project]
# ============================================================

REPO_URL="https://github.com/YOUR_ORG/agentic-sdlc-kit"
KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL_CLAUDE="$HOME/.claude"
MODE="project"
PROJECT_DIR="$(pwd)"

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --global)   MODE="global"; shift ;;
    --project)  PROJECT_DIR="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: bash install.sh [--global] [--project /path]"
      echo "  --global    Install agents/hooks globally (~/.claude/)"
      echo "  --project   Install into specific project dir (default: cwd)"
      exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Target directory ──────────────────────────────────────────────────────────
if [ "$MODE" = "global" ]; then
  TARGET="$GLOBAL_CLAUDE"
  echo "Installing GLOBALLY to $TARGET"
else
  TARGET="$PROJECT_DIR/.claude"
  echo "Installing to PROJECT: $PROJECT_DIR"
fi

# ── Backup existing .claude if present ────────────────────────────────────────
if [ -d "$TARGET" ]; then
  BACKUP="${TARGET}.bak.$(date +%Y%m%d_%H%M%S)"
  echo "Backing up existing .claude → $BACKUP"
  cp -r "$TARGET" "$BACKUP"
fi

# ── Create directory structure ────────────────────────────────────────────────
mkdir -p "$TARGET/agents"
mkdir -p "$TARGET/commands"
mkdir -p "$TARGET/hooks"
mkdir -p "$TARGET/skills/sdlc-review"
mkdir -p "$TARGET/skills/sdlc-plan"
mkdir -p "$TARGET/rules"
mkdir -p "$TARGET/sdlc/templates"

# ── Copy files ────────────────────────────────────────────────────────────────
echo "Copying agents..."
cp -r "$KIT_DIR/.claude/agents/"*    "$TARGET/agents/"

echo "Copying commands..."
cp -r "$KIT_DIR/.claude/commands/"*  "$TARGET/commands/"

echo "Copying hooks..."
cp -r "$KIT_DIR/.claude/hooks/"*     "$TARGET/hooks/"
chmod +x "$TARGET/hooks/"*.sh

echo "Copying skills..."
cp -r "$KIT_DIR/.claude/skills/"*    "$TARGET/skills/"

echo "Copying rules..."
cp -r "$KIT_DIR/.claude/rules/"*     "$TARGET/rules/"

echo "Copying templates..."
cp -r "$KIT_DIR/.claude/sdlc/"*      "$TARGET/sdlc/"

# ── Merge settings.json ───────────────────────────────────────────────────────
KIT_SETTINGS="$KIT_DIR/.claude/settings.json"
TARGET_SETTINGS="$TARGET/settings.json"

if [ -f "$TARGET_SETTINGS" ]; then
  echo "Merging settings.json (preserving existing permissions)..."
  python3 - "$TARGET_SETTINGS" "$KIT_SETTINGS" << 'PYEOF'
import sys, json
existing = json.load(open(sys.argv[1]))
kit = json.load(open(sys.argv[2]))
# Merge hooks: append kit hooks, don't overwrite existing
for event, hook_list in kit.get("hooks", {}).items():
    existing.setdefault("hooks", {}).setdefault(event, [])
    for h in hook_list:
        if h not in existing["hooks"][event]:
            existing["hooks"][event].append(h)
# Merge permissions: union allow, preserve deny
for key in ["allow", "deny"]:
    existing.setdefault("permissions", {}).setdefault(key, [])
    kit_items = kit.get("permissions", {}).get(key, [])
    existing["permissions"][key] = list(set(existing["permissions"][key] + kit_items))
with open(sys.argv[1], 'w') as f:
    json.dump(existing, f, indent=2)
print("Merged OK")
PYEOF
else
  echo "Installing settings.json..."
  cp "$KIT_SETTINGS" "$TARGET_SETTINGS"
fi

# ── Copy CLAUDE.md (warn if exists) ───────────────────────────────────────────
TARGET_CLAUDEMD="$PROJECT_DIR/CLAUDE.md"
if [ -f "$TARGET_CLAUDEMD" ]; then
  echo "WARNING: CLAUDE.md already exists. Kit CLAUDE.md saved as CLAUDE.sdlc.md"
  cp "$KIT_DIR/CLAUDE.md" "$PROJECT_DIR/CLAUDE.sdlc.md"
  echo "Merge sections from CLAUDE.sdlc.md into your CLAUDE.md manually."
else
  cp "$KIT_DIR/CLAUDE.md" "$TARGET_CLAUDEMD"
fi

# ── Verify installation ───────────────────────────────────────────────────────
echo ""
echo "Verifying installation..."
AGENTS=$(ls "$TARGET/agents/"*.md 2>/dev/null | wc -l | tr -d ' ')
COMMANDS=$(ls "$TARGET/commands/"*.md 2>/dev/null | wc -l | tr -d ' ')
HOOKS=$(ls "$TARGET/hooks/"*.sh 2>/dev/null | wc -l | tr -d ' ')
SKILLS=$(find "$TARGET/skills/" -name "SKILL.md" 2>/dev/null | wc -l | tr -d ' ')
RULES=$(ls "$TARGET/rules/"*.md 2>/dev/null | wc -l | tr -d ' ')

echo "  Agents:   $AGENTS/8"
echo "  Commands: $COMMANDS/3"
echo "  Hooks:    $HOOKS/5"
echo "  Skills:   $SKILLS/2"
echo "  Rules:    $RULES/2"

echo ""
echo "✅ Agentic SDLC Kit installed successfully!"
echo ""
echo "Quick start:"
echo "  Open your project in Claude Code"
echo "  Run: /factory my-feature \"Build a REST API for user auth\""
echo "  Check status: /factory-status"
echo "  List artifacts: /factory-artifacts my-feature"
echo ""
echo "Docs: $TARGET/sdlc/BEST_PRACTICES.md"
