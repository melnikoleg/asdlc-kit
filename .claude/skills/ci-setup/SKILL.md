---
name: ci-setup
description: Create GitHub Actions CI/CD pipeline with lint, test, build, security scan, and deploy stages. Auto-detects stack and test commands. Produces .github/workflows/ci.yml. Invoke as: /ci-setup
---

# CI Setup

GitHub Actions pipeline: lint → test → security → build → deploy.

## Steps
1. Detect stack: package.json (Node), pyproject.toml (Python), go.mod (Go), *.csproj (.NET)
2. Detect test command: npm test / pytest / go test ./... / dotnet test
3. Detect lint command: eslint / ruff / golangci-lint / dotnet format
4. Generate `.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lint
        run: {detected-lint-command}

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - name: Test
        run: {detected-test-command}
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  security:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - name: Dependency audit
        run: {npm audit --audit-level=high | pip-audit | nancy}

  build:
    runs-on: ubuntu-latest
    needs: [test, security]
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t app:${{ github.sha }} .
```

## Security Rules
- Secrets via `${{ secrets.SECRET_NAME }}` only — never hardcoded
- Pin action versions to SHA: `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`
- Run security scan on every PR

## Anti-Patterns
- NEVER hardcode tokens in workflow files
- NEVER use `latest` for action versions in production

## Related Skills
- /docker-setup — Dockerfile for the build stage
- /sdlc-deploy — full deployment runbook
