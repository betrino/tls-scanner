FROM python:3.11-slim

# 1. System-Updates & Abhängigkeiten für testssl.sh installieren
# bsdmainutils = hexdump (zwingend nötig)
# socat = besseres Networking für testssl
# git, openssl, etc. = Standardbedarf
RUN apt-get update && apt-get install -y \
    bash \
    git \
    openssl \
    procps \
    dnsutils \
    bsdmainutils \
    socat \
    && rm -rf /var/lib/apt/lists/*

# 2. testssl.sh herunterladen
RUN git clone --depth 1 https://github.com/drwetter/testssl.sh.git /opt/testssl.sh

# 3. WICHTIG: Python Libraries installieren (das fehlte eben)
RUN pip install --no-cache-dir requests

# 4. Arbeitsverzeichnis setzen
WORKDIR /app

# 5. Skript kopieren
COPY scanner.py /app/scanner.py

# 6. Startbefehl mit absolutem Pfad
CMD ["python", "/app/scanner.py"]

