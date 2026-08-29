# Two runtimes in one image: bun runs the portal search CLIs, Python runs the
# MCP server.
FROM oven/bun:1 AS bun

FROM python:3.13-slim
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml /app/pyproject.toml
COPY mcp_server/jobsearch_mcp/ /app/mcp_server/jobsearch_mcp/
COPY README.md /app/README.md

# [oauth] pulls the Entra sign-in dependencies. They are unused unless you set
# MCP_AUTH=oauth, but installing them here means switching auth mode is an
# environment-variable change rather than an image rebuild.
RUN pip install --no-cache-dir ".[oauth]"

# Portal CLIs, staged from .agents/skills by deploy.sh.
COPY mcp_server/portals/ /app/portals/

# Profile documents are bind-mounted at /app/profile.
# State (database, audit log, profile snapshots) lives on a volume at /data.
RUN mkdir -p /app/profile /data /config

ENV JOBSEARCH_STATE_DIR=/data \
    JOBSEARCH_DB=/data/jobsearch.db \
    JOBSEARCH_CONFIG=/config/jobsearch.config.json \
    PROFILE_DIR=/app/profile \
    PROFILE_BACKUPS=/data/profile_revisions \
    PORTAL_DIR=/app/portals \
    MCP_OAUTH_STORE=/data/oauth-store \
    MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8791

# Run as a non-root user. Nothing here needs root, and the container mounts the
# profile read-write, so a compromise should not also own those files.
# UID 1001 is a common default for the first non-root host account, which keeps
# bind-mount permissions lined up; override with --build-arg if yours differs.
ARG APP_UID=1001
RUN useradd -u ${APP_UID} -m -s /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app /data /config
USER appuser

EXPOSE 8791
CMD ["jobsearch-mcp"]
