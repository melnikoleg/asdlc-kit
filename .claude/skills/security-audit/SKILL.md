---
name: security-audit
description: Deep security audit of a codebase or specific files. Scans for OWASP Top 10, hardcoded secrets, insecure dependencies, missing auth, unsafe deserialization, and more. Produces a severity-ranked findings report. Use before any production deployment or when security review is required. Invoke as: /security-audit [path or "full"]
---

# Security Audit

Comprehensive application security scan.

## What It Scans

### Critical (P0 — fix immediately)
- Hardcoded secrets, API keys, passwords in code or config
- SQL/NoSQL injection vectors
- Command injection (exec, eval, shell=True)
- Authentication bypass
- Insecure direct object references (IDOR)

### High (P1 — fix before deploy)
- Missing input validation/sanitization
- Insecure session management
- Sensitive data in logs
- Missing HTTPS enforcement
- Broken access control

### Medium (P2 — fix soon)
- Missing rate limiting on auth endpoints
- Verbose error messages exposing internals
- Outdated dependencies with known CVEs
- Missing security headers (CSP, HSTS, X-Frame-Options)
- Weak password hashing (MD5, SHA1)

### Low (P3 — track and fix)
- Missing CSRF protection
- Overly broad CORS policy
- Debug mode enabled

## Output Format
```
Security Audit: {path}
Critical: N | High: N | Medium: N | Low: N

[P0-CRITICAL] src/db.js:12
  Issue: Hardcoded database password
  Evidence: password = "prod_secret_123"
  Fix: Move to env var DATABASE_PASSWORD

[P1-HIGH] src/api/users.js:45
  Issue: No rate limiting on POST /login
  Fix: Add express-rate-limit: max 5 req/15min
```

## Tools Used
- Grep for patterns (secrets, injection sinks)
- Read for context around findings
- Bash for running available SAST tools (npm audit, bandit, etc.)

## Anti-Patterns
- Do NOT report theoretical issues without code evidence
- Do NOT stop at first finding — scan everything

## Related Skills
- /code-reviewer — general code quality review
