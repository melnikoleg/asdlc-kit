# MCP Configuration Stubs

Ready-to-paste MCP server configs for each editor. These add `codebase-memory-mcp` — a local binary that gives agents persistent memory of your project structure across sessions.

## 1. Install codebase-memory-mcp

```bash
# macOS / Linux — download the binary from DeusData releases
INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

ARCH=$(uname -m)
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
[ "$ARCH" = "x86_64" ] && ARCH="amd64"
[ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ] && ARCH="arm64"

curl -fsSL \
  "https://github.com/DeusData/codebase-memory-mcp/releases/latest/download/codebase-memory-mcp_${OS}_${ARCH}" \
  -o "$INSTALL_DIR/codebase-memory-mcp"
chmod +x "$INSTALL_DIR/codebase-memory-mcp"

# Verify
codebase-memory-mcp --version
```

---

## 2. Claude Desktop (`~/.config/claude/mcp.json`)

```json
{
  "mcpServers": {
    "codebase-memory": {
      "command": "/home/YOUR_USER/.local/bin/codebase-memory-mcp",
      "args": [],
      "transport": "stdio"
    }
  }
}
```

> **macOS path:** `~/.config/claude/mcp.json` (create if absent)
> Replace `YOUR_USER` with your username, or use `$HOME` in shell expansion.

---

## 3. Cursor (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "codebase-memory": {
      "command": "/home/YOUR_USER/.local/bin/codebase-memory-mcp",
      "args": [],
      "transport": "stdio"
    }
  }
}
```

---

## 4. GitHub Copilot (`~/.config/github-copilot/mcp.json`)

```json
{
  "mcpServers": {
    "codebase-memory": {
      "command": "/home/YOUR_USER/.local/bin/codebase-memory-mcp",
      "args": [],
      "transport": "stdio"
    }
  }
}
```

---

## 5. Claude Code (project-local, `.claude/mcp.json`)

To scope the MCP server to a single project rather than globally:

```json
{
  "mcpServers": {
    "codebase-memory": {
      "command": "/home/YOUR_USER/.local/bin/codebase-memory-mcp",
      "args": [],
      "transport": "stdio"
    }
  }
}
```

Place this file at the repo root. Claude Code picks it up automatically.

---

## Merging with existing configs

If you already have an `mcp.json`, add only the `codebase-memory` key inside `mcpServers` — do not overwrite the whole file:

```bash
# Using jq to merge safely
jq '.mcpServers["codebase-memory"] = {
  "command": ($home + "/.local/bin/codebase-memory-mcp"),
  "args": [],
  "transport": "stdio"
}' --arg home "$HOME" ~/.config/claude/mcp.json > /tmp/mcp_merged.json \
  && mv /tmp/mcp_merged.json ~/.config/claude/mcp.json
```

---

## After installation

Restart your editor (or run `/reload-plugins` in Claude Code) to activate the MCP server. You should see `codebase-memory` listed in the active MCP servers panel.
