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
      wkhtmltopdf \
      poppler-utils \
      websocat \
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

COPY build/script-server /app
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
CMD [ "python3", "launcher.py" ]
