# Security Rules (Always Active)

- NEVER hardcode secrets, tokens, passwords, API keys in any code or artifact
- NEVER write to .env, *.pem, id_rsa, kubeconfig, .aws/credentials (hooks enforce this)
- NEVER run: rm -rf on root/home, git push --force, git reset --hard on main
- Every Dockerfile MUST use non-root user and multi-stage build
- All env vars MUST be documented in DEPLOY.md when deploy artifacts are generated (/sdlc-deploy)
- SQL queries MUST use parameterized statements (no string concatenation)
- Auth endpoints MUST be rate-limited
- reviewer-agent checks OWASP Top 10 on every implementation
