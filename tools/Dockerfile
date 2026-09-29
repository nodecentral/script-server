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
    && rm -rf /var/lib/apt/lists/*

# websocat isn't packaged for Debian at all - install the static binary directly.
# NOTE: wkhtmltopdf was dropped - Debian removed it from the archive (unmaintained
# upstream). If you need it, install the standalone package from
# https://github.com/wkhtmltopdf/packaging/releases instead (a .deb download + dpkg
# install, since apt can no longer resolve it).
RUN curl -fsSL -o /usr/local/bin/websocat \
      https://github.com/vi/websocat/releases/download/v1.14.1/websocat.x86_64-unknown-linux-musl \
    && chmod +x /usr/local/bin/websocat

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
#   defaults/runners/   conf/runners/*.json
#   defaults/scripts/   scripts/ (incl. shared/ and preload/)
#   defaults/data/      data/.gitkeep
# Every source path is spelled out (no `COPY conf/`) and .dockerignore drops runtime state, so a
# checkout that has been run or used as a live mount can't leak conf/.htpasswd or
# data/secrets.json into the image.
COPY tools/default-conf.json /app/defaults/conf/conf.json
COPY conf/logging.json conf/capabilities.json conf/secrets_defaults.json /app/defaults/conf/
COPY conf/runners/ /app/defaults/runners/
COPY scripts/ /app/defaults/scripts/
COPY data/.gitkeep /app/defaults/data/.gitkeep
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

EXPOSE 5000
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD [ "python3", "launcher.py" ]
