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
    && playwright install-deps chromium \
    && playwright install chromium

WORKDIR /app

COPY launcher.py requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY conf/logging.json ./conf/logging.json
COPY --from=web-builder /src/web ./web

RUN mkdir -p conf/runners

EXPOSE 5000
CMD [ "python3", "launcher.py" ]
