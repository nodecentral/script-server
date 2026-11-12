# ---- Stage 1: build the web frontend ----
FROM node:20-slim AS web-builder

ENV NODE_OPTIONS=--openssl-legacy-provider
WORKDIR /src/web-src

COPY web-src/package.json web-src/package-lock.json ./
RUN npm ci

COPY web-src/ ./
RUN npm run build

# ---- Stage 2: runtime image ----
FROM python:3.9-slim

ENV DEBIAN_FRONTEND=noninteractive

# OS packages needed by scripts run through script-server (networking/diagnostics,
# file/doc conversion, OCR, finance-quote lookups, Lua/HTTPS support, and a build
# toolchain for any pip packages that need to compile native extensions).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      autoconf \
      rustc \
      cargo \
      ca-certificates \
      openssl \
      curl \
      wget \
      git \
      tree \
      file \
      dialog \
      iputils-ping \
      nmap \
      arp-scan \
      net-tools \
      iproute2 \
      inotify-tools \
      ffmpeg \
      poppler-utils \
      tesseract-ocr \
      tesseract-ocr-eng \
      libgl1 \
      libreadline-dev \
      libsqlite3-dev \
      sqlite3 \
      libssl-dev \
      librsvg2-bin \
      lua5.1 \
      luarocks \
      lua-sec \
      lua-socket \
      libfinance-quote-perl \
      libfinance-quotehist-perl \
      sudo \
    && rm -rf /var/lib/apt/lists/*

# websocat isn't packaged for Debian at all - install the static binary directly.
# NOTE: wkhtmltopdf was dropped - Debian removed it from the archive (unmaintained
# upstream). If you need it, install the standalone package from
# https://github.com/wkhtmltopdf/packaging/releases instead (a .deb download + dpkg
# install, since apt can no longer resolve it).
RUN curl -fsSL -o /usr/local/bin/websocat \
      https://github.com/vi/websocat/releases/download/v1.14.1/websocat.x86_64-unknown-linux-musl \
    && chmod +x /usr/local/bin/websocat

# Lua modules used by sibling-repo scripts. The app runs as PUID (not root) on the NAS, so a
# script's own ensure_module.lua can't luarocks-install anything at run time - every Lua module a
# script needs has to be baked in here. lsqlite3: ss_photo_file_management (Photo Dashboard).
# Builds against libsqlite3-dev + build-essential from the apt list above.
RUN luarocks install lsqlite3

# Python packages used by scripts (spreadsheet/PDF handling, OCR, browser automation),
# installed before the app code is copied so they cache independently of app changes.
RUN pip install --no-cache-dir \
      openpyxl \
      requests \
      pandas \
      pdfplumber \
      pymupdf \
      pdf2image \
      pillow \
      pytesseract \
      paddlepaddle \
      paddleocr \
      playwright \
      plotly \
    && playwright install-deps chromium \
    && playwright install chromium

WORKDIR /app

COPY launcher.py requirements.txt ./
# version.txt is what the UI shows as the version (sidebar footer, admin header); CHANGELOG.md is
# served at /changelog for the "What's new" page. Both are read from the working dir (/app).
COPY version.txt CHANGELOG.md ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY conf/logging.json ./conf/logging.json
COPY --from=web-builder /src/web ./web

RUN mkdir -p conf/runners

# ---- First-run seeding: defaults for the bind mounts ----
# Users bind-mount host folders over /app/conf, /app/scripts and /app/data (and usually
# /app/logs). A bind mount doesn't inherit image content, so on a fresh install those folders
# are empty - no conf.json, no runners, no scripts. Everything a working install needs is
# therefore also shipped under /app/defaults, a path no mount covers, and
# tools/docker-entrypoint.sh copies it into the mounts at start: user content fill-if-missing,
# the files listed in PLATFORM_FILES refreshed per file. Layout (the entrypoint maps it onto
# /app/conf, /app/conf/runners, /app/scripts, /app/data):
#   defaults/conf/      conf.json + logging.json + capabilities.json + secrets_defaults.json
#                       + categories.json
#   defaults/runners/   conf/runners/*.json
#   defaults/scripts/   scripts/ (incl. shared/ and preload/)
#   defaults/data/      data/.gitkeep
# Every source path is spelled out (no `COPY conf/`) and .dockerignore drops runtime state, so a
# checkout that has been run or used as a live mount can't leak conf/.htpasswd or
# data/secrets.json into the image.
COPY tools/default-conf.json /app/defaults/conf/conf.json
COPY conf/logging.json conf/capabilities.json conf/secrets_defaults.json conf/categories.json /app/defaults/conf/
COPY conf/runners/ /app/defaults/runners/
COPY scripts/ /app/defaults/scripts/
COPY data/.gitkeep /app/defaults/data/.gitkeep
# Default look for this fork (indigo, v2.0.0+): user content like the rest of defaults/conf, so
# seeded only if /app/conf/theme/theme.css is missing - edit or empty it on the NAS to change it.
COPY samples/themes/indigo/theme.css /app/defaults/conf/theme/theme.css
COPY tools/PLATFORM_FILES /app/defaults/PLATFORM_FILES

# Fail the build if the manifest names a file the image doesn't ship (a typo or a rename would
# otherwise silently stop that file being kept current); merely notify about shared/preload
# files that aren't listed, since those are seeded once but never refreshed.
RUN cd /app/defaults \
    && grep -v -e '^#' -e '^[[:space:]]*$' PLATFORM_FILES | while IFS= read -r f; do \
         [ -f "$f" ] || { echo "PLATFORM_FILES lists $f but it is not in the image" >&2; exit 1; }; \
       done \
    && for f in scripts/shared/* scripts/preload/*; do \
         [ -f "$f" ] || continue; \
         grep -qxF "$f" PLATFORM_FILES || echo "NOTICE: $f is not in PLATFORM_FILES (seeded if missing, never refreshed)"; \
       done

# The entrypoint. Strip CR in case the repo was checked out or unzipped on Windows, where a \r
# after the shebang makes the script unrunnable. It relies on setpriv (drop to PUID/PGID), cmp,
# find and mktemp - all in the base image today; checked here so a base-image change fails the
# build instead of the first container start.
COPY tools/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && for c in setpriv cmp find mktemp; do command -v "$c" >/dev/null || { echo "missing: $c" >&2; exit 1; }; done

# Scripts install what they need without root (the app runs as PUID on the NAS):
#   - apt-get/apt: wrappers that go through sudo, allowed for apt-get only (ALLOW_APT=false on the
#     container removes the rule). Lost when the container is recreated; ensure_binary.lua
#     reinstalls on the next run.
#   - luarocks: a wrapper that installs into /app/data/.deps/lua, found via LUA_PATH/LUA_CPATH.
#   - pip: PIP_USER + PYTHONUSERBASE install into /app/data/.deps/python, which Python adds to
#     sys.path itself. The server runs with `python3 -s` (no user site), so nothing a script
#     installs there can replace the server's own packages.
# Both /app/data/.deps folders are on the data mount, so they survive recreating the container.
COPY tools/rootless/apt-get tools/rootless/luarocks /usr/local/bin/
RUN sed -i 's/\r$//' /usr/local/bin/apt-get /usr/local/bin/luarocks \
    && chmod 755 /usr/local/bin/apt-get /usr/local/bin/luarocks \
    && ln -s apt-get /usr/local/bin/apt \
    && printf '%s\n' \
         '# Script Server: scripts may install system packages (see /usr/local/bin/apt-get)' \
         'Defaults env_keep += "DEBIAN_FRONTEND"' \
         'ALL ALL=(root) NOPASSWD: /usr/bin/apt-get, /usr/bin/apt' \
         > /etc/sudoers.d/script-server-apt \
    && chmod 440 /etc/sudoers.d/script-server-apt \
    && visudo -cf /etc/sudoers.d/script-server-apt
ENV SCRIPT_DEPS_DIR=/app/data/.deps \
    PYTHONUSERBASE=/app/data/.deps/python \
    PIP_USER=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    LUA_PATH="/app/data/.deps/lua/share/lua/5.1/?.lua;/app/data/.deps/lua/share/lua/5.1/?/init.lua;;" \
    LUA_CPATH="/app/data/.deps/lua/lib/lua/5.1/?.so;;"

EXPOSE 5000
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD [ "python3", "-s", "launcher.py" ]
