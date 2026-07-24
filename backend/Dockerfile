# =============================================================================
# Invigilo backend — production image
# =============================================================================
#
# Phase 0. Single image for both dev (bind-mounted source) and prod
# (Render free-tier). The bind-mount in docker-compose.yml mounts only
# /app (the WORKDIR); the .dockerignore keeps .venv, pyc, __pycache__,
# and other dev-time junk out of the build context so the image stays
# small and the venv installed here isn't shadowed by a host venv on
# bind-mount.
#
# Why python:3.12-slim (not alpine):
#   * psycopg[binary] ships pre-built wheels for manylinux; on alpine
#     it has to be built from source, which means adding libpq-dev,
#     postgresql-dev, gcc, musl-dev — 4 packages and 5 min of compile
#     time saved by going manylinux.
#   * The console email backend + sse-starlette + anyio have no C
#     extensions, so the smaller image is mostly empty bytes anyway.
# =============================================================================
FROM python:3.12-slim

# build-essential + libpq-dev are only needed to build psycopg from
# source on architectures that lack a manylinux wheel. The
# psycopg[binary] extra normally avoids this, but we add the build
# deps anyway as a safety net for ARM (e.g. Apple Silicon, AWS Graviton).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# requirements first — cached layer when only source changes.
WORKDIR /app
COPY requirements/ ./requirements/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements/prod.txt

# Source. In dev the bind-mount in docker-compose.yml overlays this,
# but the image is the source of truth for production (Render).
COPY . .

# entrypoint waits for postgres, runs migrations, then execs gunicorn.
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

# Default command is the entrypoint. ``docker compose`` overrides this
# with ``command: bash /app/docker/entrypoint.sh`` so the same image
# can be used both for compose (with the wait + migrate dance) and for
# Render (which runs the image directly and doesn't need the wait).
CMD ["bash", "/app/docker/entrypoint.sh"]
