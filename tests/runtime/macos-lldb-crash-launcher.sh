#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-only
# Runs the given command (soffice and its arguments) under lldb in batch mode. When the process crashes, lldb prints
# every thread's backtrace, the registers, the disassembly around the crashing instruction and of the crashing
# function, then kills it. Used as --launcher of the macOS runtime checks to get a crash cause on CI runners.
set -u
exec lldb --batch \
  -o "process handle SIGPIPE SIGUSR1 SIGUSR2 -n false -p true -s false" \
  -o "run" \
  -k "thread backtrace all" \
  -k "register read" \
  -k "disassemble --pc --count 12" \
  -k "disassemble --frame" \
  -k "frame variable" \
  -k "image lookup --address \$pc --verbose" \
  -k "kill" \
  -k "quit 1" \
  -o "quit 0" \
  -- "$@"
