---
name: dependency-audit
description: Audit project dependencies for CVEs, outdated versions, unused packages, and license issues. Runs available package audit tools (npm audit, pip-audit, nancy, trivy). Produces prioritized findings report with upgrade commands. Invoke as: /dependency-audit
---

# Dependency Audit

Scan all dependencies for vulnerabilities, outdated versions, and issues.

## Steps
1. Detect package managers: package.json (npm/yarn/pnpm), requirements.txt/pyproject.toml (pip), go.mod (Go), *.csproj (.NET)
2. Run available audit tools:
   - Node: `npm audit --json` or `yarn audit --json`
   - Python: `pip-audit --format=json` or `safety check`
   - Go: `nancy sleuth` or `govulncheck ./...`
   - Docker: `trivy image {image}` if Dockerfile exists
3. Parse results and categorize:
   - **Critical/High CVE** — immediate upgrade required
   - **Outdated (major)** — breaking change needed, plan upgrade
   - **Outdated (minor/patch)** — safe to upgrade
   - **Unused** — can remove (check with depcheck/pip-autoremove)

## Output Format
```
Dependency Audit: {project}
Critical: N | High: N | Medium: N | Outdated: N

[CRITICAL] lodash 4.17.15 — CVE-2021-23337 (prototype pollution)
  Fix: npm update lodash  → 4.17.21

[HIGH] pillow 9.0.0 — CVE-2023-44271 (uncontrolled resource consumption)
  Fix: pip install "pillow>=10.0.1"

[OUTDATED-MAJOR] react 17.0.2 → 18.3.1
  Migration guide: react.dev/blog/2022/03/08/react-18-upgrade-guide
```

## Anti-Patterns
- Do NOT blindly upgrade all major versions — they may have breaking changes
- Do NOT ignore Critical/High CVEs in production

## Related Skills
- /security-audit — application code security scan
- /docker-setup — container image vulnerability scanning
