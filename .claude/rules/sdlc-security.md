# Security Rules (Always Active)

- Never hardcode secrets, tokens, passwords, API keys in code or artifacts
- Never write to .env, *.pem, id_rsa, kubeconfig, .aws/credentials
- Never run: rm -rf on root/home, git push --force, git reset --hard on main
- Every Dockerfile must use non-root user and multi-stage build
- All env vars documented in DEPLOY.md
- SQL queries must use parameterized statements
- Auth endpoints must be rate-limited
- OWASP Top 10 checked by reviewer-agent on every implementation
