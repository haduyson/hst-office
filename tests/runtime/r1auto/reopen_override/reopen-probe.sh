#!/bin/sh
# Probe stand-in for the product's --reopen waiter: argv = /bin/sh SCRIPT --reopen PID DEST LOG [OLD]
PID=$3; DEST=$4
exec >>"$HOME/hst-reopen-probe.log" 2>&1
while kill -0 "$PID" 2>/dev/null; do sleep 1; done
echo "$(date +%T) waiter: office $PID exited"
env | sort | sed 's/^/ENV /'
running() { pgrep -f "$DEST/Contents/MacOS/soffice"; }
try() {
    echo "$(date +%T) attempt $1"
    shift
    "$@"
    echo "$(date +%T) open exit $?"
    sleep 20
    if running; then echo "$(date +%T) running after 20 s"; exit 0; fi
    echo "$(date +%T) not running after 20 s"
}
try "1: open at once, inherited environment" open "$DEST"
try "2: open again, inherited environment" open "$DEST"
try "3: open, clean environment" env -i HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" TMPDIR="$TMPDIR" PATH=/usr/bin:/bin:/usr/sbin:/sbin open "$DEST"
exit 1
