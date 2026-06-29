#!/usr/bin/env bash
# Entrypoint for the self-contained Agentic SDLC pipeline image.
#
# Modes (ASDLC_MODE):
#   autonomous (default) — start the pipeline, auto-approve the gate, run to
#                          completion, then exit with the pipeline's status code.
#   server               — run the FastAPI server; approve via the HTTP API.
#   manual               — stay idle; drive it yourself with `docker exec`.
#
# Any extra args passed to `docker run` override all of this and are exec'd.
set -euo pipefail

# Explicit command override: `docker run <image> python -m runtime.cli ...`
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

MODE="${ASDLC_MODE:-autonomous}"

# Auth preflight: either an API key (service-account path) or mounted Claude
# subscription credentials. Warn loudly rather than fail with a cryptic SDK
# error 20 minutes into a run.
if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ ! -f "${HOME}/.claude/.credentials.json" ]; then
    echo "WARNING: no ANTHROPIC_API_KEY and no ${HOME}/.claude/.credentials.json found." >&2
    echo "         Set ANTHROPIC_API_KEY, or mount your Claude subscription creds:" >&2
    echo "         docker-compose.yml -> volumes -> - \${HOME}/.claude:/home/appuser/.claude" >&2
fi

case "$MODE" in
    server)
        echo ">> asdlc: HTTP server on :${PORT:-8000} (POST /pipelines, /pipelines/{issue}/approve)"
        exec uvicorn runtime.server:app --host 0.0.0.0 --port "${PORT:-8000}"
        ;;

    autonomous)
        : "${ASDLC_ISSUE:?autonomous mode requires ASDLC_ISSUE (kebab-case issue name)}"
        : "${ASDLC_REQUIREMENT:?autonomous mode requires ASDLC_REQUIREMENT (the requirement text)}"

        echo ">> asdlc: starting pipeline '${ASDLC_ISSUE}' (runs to the approval gate)…"
        python -m runtime.cli "$ASDLC_ISSUE" "$ASDLC_REQUIREMENT"

        if [ "${ASDLC_AUTO_APPROVE:-1}" = "1" ]; then
            echo ">> asdlc: auto-approving and running to completion…"
            exec python -m runtime.cli "$ASDLC_ISSUE" --approve
        fi
        echo ">> asdlc: paused at approval gate. Approve with:"
        echo "     docker exec <container> python -m runtime.cli ${ASDLC_ISSUE} --approve"
        ;;

    manual)
        echo ">> asdlc: manual mode. Drive the pipeline with, e.g.:"
        echo "     docker exec <container> python -m runtime.cli <issue> \"<requirement>\""
        exec tail -f /dev/null
        ;;

    *)
        echo "asdlc: unknown ASDLC_MODE='${MODE}' (expected autonomous|server|manual)" >&2
        exit 2
        ;;
esac
