#!/bin/bash
set -e

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL_DIR="$HOME/.claude"
MODE="project"

# ─── Args ─────────────────────────────────────────────────────────────────────
for arg in "$@"; do
  case $arg in
    --global)  MODE="global"; TARGET_DIR="$GLOBAL_DIR" ;;
    --project) MODE="project" ;;
    --project=*) MODE="project"; TARGET_DIR="${arg#--project=}" ;;
    --help|-h)
      echo "Usage: bash install.sh [--global] [--project=/path]"
      echo "  --global           Install to ~/.claude (all projects)"
      echo "  --project=/path    Install to /path/.claude"
      echo "  (default)          Install to ./.claude (current directory)"
      exit 0 ;;
  esac
done

if [ -z "$TARGET_DIR" ]; then
  TARGET_DIR="$(pwd)/.claude"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║    Agentic SDLC Kit — Installer v2.0         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
info "Mode: $MODE"
info "Target: $TARGET_DIR"
echo ""

# ─── Backup ──────────────────────────────────────────────────────────────────
if [ -d "$TARGET_DIR" ]; then
  BACKUP="${TARGET_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
  warn "Existing .claude found — backing up to $BACKUP"
  cp -r "$TARGET_DIR" "$BACKUP"
  success "Backup created"
fi

# ─── Copy files ──────────────────────────────────────────────────────────────
info "Copying skills, agents, commands, hooks, rules..."
mkdir -p "$TARGET_DIR"

for dir in agents commands hooks rules skills sdlc; do
  src="$SCRIPT_DIR/.claude/$dir"
  dst="$TARGET_DIR/$dir"
  if [ -d "$src" ]; then
    mkdir -p "$dst"
    cp -r "$src/." "$dst/"
    count=$(find "$dst" -name "*.md" -o -name "*.sh" -o -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
    success "Copied $dir/ ($count files)"
  fi
done

# ─── Merge settings.json (don't overwrite existing) ─────────────────────────
SRC_SETTINGS="$SCRIPT_DIR/.claude/settings.json"
DST_SETTINGS="$TARGET_DIR/settings.json"

if [ -f "$DST_SETTINGS" ] && command -v python3 &>/dev/null; then
  info "Merging settings.json (preserving existing hooks/permissions)..."
  SRC_SETTINGS="$SRC_SETTINGS" DST_SETTINGS="$DST_SETTINGS" python3 - <<'PYEOF'
import json, os

src_path = os.environ["SRC_SETTINGS"]
dst_path = os.environ["DST_SETTINGS"]

try:
    with open(src_path) as f: src = json.load(f)
    with open(dst_path) as f: dst = json.load(f)

    # Merge permissions
    if "permissions" in src:
        if "permissions" not in dst: dst["permissions"] = {}
        for k in ["allow", "deny"]:
            if k in src["permissions"]:
                existing = set(dst["permissions"].get(k, []))
                new_items = [x for x in src["permissions"][k] if x not in existing]
                dst["permissions"][k] = dst["permissions"].get(k, []) + new_items

    # Merge hooks
    if "hooks" in src:
        if "hooks" not in dst: dst["hooks"] = {}
        for event, hooks_list in src["hooks"].items():
            if event not in dst["hooks"]: dst["hooks"][event] = hooks_list
            else:
                existing_cmds = set()
                for h in dst["hooks"][event]:
                    for hh in h.get("hooks", []):
                        existing_cmds.add(hh.get("command",""))
                for h in hooks_list:
                    new_hooks = [hh for hh in h.get("hooks",[]) if hh.get("command","") not in existing_cmds]
                    if new_hooks:
                        dst["hooks"][event].append({**h, "hooks": new_hooks})

    with open(dst_path, "w") as f: json.dump(dst, f, indent=2)
    print("Settings merged successfully")
except Exception as e:
    print(f"Merge failed: {e} — using source settings")
    import shutil; shutil.copy(src_path, dst_path)
PYEOF
  success "settings.json merged"
else
  cp "$SRC_SETTINGS" "$DST_SETTINGS"
  success "settings.json installed"
fi

# ─── Chmod hooks ─────────────────────────────────────────────────────────────
find "$TARGET_DIR/hooks" -name "*.sh" -exec chmod +x {} \; 2>/dev/null
success "Hook permissions set"

# ─── Create docs/ ─────────────────────────────────────────────────────────────
if [ "$MODE" = "project" ] && [ "$TARGET_DIR" != "$GLOBAL_DIR" ]; then
  PROJ_DIR="$(dirname "$TARGET_DIR")"
  mkdir -p "$PROJ_DIR/docs"
  success "docs/ directory created"
fi

# ─── Copy CLAUDE.md if missing ───────────────────────────────────────────────
DST_PARENT="$(dirname "$TARGET_DIR")"
if [ ! -f "$DST_PARENT/CLAUDE.md" ] && [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
  cp "$SCRIPT_DIR/CLAUDE.md" "$DST_PARENT/CLAUDE.md"
  success "CLAUDE.md installed"
fi

# ─── Verify ──────────────────────────────────────────────────────────────────
echo ""
info "Verification..."
SKILLS_COUNT=$(find "$TARGET_DIR/skills" -name "SKILL.md" 2>/dev/null | wc -l | tr -d ' ')
AGENTS_COUNT=$(find "$TARGET_DIR/agents" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
HOOKS_COUNT=$(find "$TARGET_DIR/hooks" -name "*.sh" 2>/dev/null | wc -l | tr -d ' ')
COMMANDS_COUNT=$(find "$TARGET_DIR/commands" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
RULES_COUNT=$(find "$TARGET_DIR/rules" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║              Installation Complete           ║"
echo "╠══════════════════════════════════════════════╣"
printf "║  %-12s %3s skills                      ║\n" "Skills:" "$SKILLS_COUNT"
printf "║  %-12s %3s agents                      ║\n" "Agents:" "$AGENTS_COUNT"
printf "║  %-12s %3s hooks                       ║\n" "Hooks:" "$HOOKS_COUNT"
printf "║  %-12s %3s commands                    ║\n" "Commands:" "$COMMANDS_COUNT"
printf "║  %-12s %3s rules                       ║\n" "Rules:" "$RULES_COUNT"
echo "╠══════════════════════════════════════════════╣"
echo "║  Quick start (in Claude Code):               ║"
echo "║                                              ║"
echo "║  /factory auth-api \"build JWT auth API\"    ║"
echo "║  /sdlc-status                                ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
