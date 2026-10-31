# Isolated sandbox for Codex CLI: runs the locally built HST Office (mounted read-only) under Xvfb with a
# SoftHSM2 virtual token, so Codex can implement and test extension work end to end with full access
# inside the container only. No host secrets, no other projects, no push credentials are mounted.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 python3-venv xvfb xauth dbus dbus-x11 xdotool x11-utils imagemagick \
      softhsm2 opensc libnss3-tools libnss3 libnspr4 p11-kit \
      libgtk-3-0t64 libcups2t64 libxinerama1 libxrandr2 libxslt1.1 libgl1 libegl1 libsm6 libice6 \
      libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libpython3.12t64 \
      fonts-dejavu fonts-liberation fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 2000 codex
WORKDIR /work
