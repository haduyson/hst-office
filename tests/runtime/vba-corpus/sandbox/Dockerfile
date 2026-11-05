# Disposable sandbox for running macros with HST Office. No HST files inside: instdir is bind-mounted read-only (run_sandboxed.sh).
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
COPY pkgs.txt /tmp/pkgs.txt
RUN apt-get update && apt-get install -y --no-install-recommends python3 libpython3.12t64 xvfb xauth fonts-dejavu-core fontconfig $(cat /tmp/pkgs.txt) && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/pkgs.txt
RUN useradd -u 54321 -m -s /usr/sbin/nologin sandbox
USER 54321
