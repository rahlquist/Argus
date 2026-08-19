#!/usr/bin/env bash
# notify_bot.sh — deliver a briefing into a local Hermes Bot's chat.
#
# Usage:
#   notify_bot.sh <bot-profile> < "briefing text"
#   notify_bot.sh <bot-profile> /path/to/briefing.md
#
# Delivers via `hermes -p <bot-profile> chat -Q -q "..."` — the same path a
# user takes to talk to a local Bot profile. The message lands in that bot's
# canonical Bot Chat. The cron job's own `deliver:` stays "local"; this script
# is invoked by the skill's DELIVER step when a tracker's delivery lists a
# `bot:<profile>` target (cron's deliver resolver has no profile-aware path).
#
# Exit codes:
#   0  delivered (or nothing to send — silent tick is success)
#   2  usage error
#   3  hermes chat failed
set -uo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: notify_bot.sh <bot-profile> < <text> | <file>" >&2
  exit 2
fi

BOT="$1"
shift

# Acquire the message: either from a file arg or stdin.
if [ "$#" -ge 1 ] && [ -f "$1" ]; then
  MSG="$(cat "$1")"
elif [ ! -t 0 ]; then
  MSG="$(cat)"
else
  echo "notify_bot.sh: no message (pipe text or pass a file path)" >&2
  exit 2
fi

# Silent tick: nothing to say, nothing to send.
if [ -z "${MSG// }" ]; then
  exit 0
fi

# Deliver. -Q = quiet (only the agent's reply on stdout); -q = single query.
if hermes -p "$BOT" chat -Q -q "$MSG" >/dev/null 2>&1; then
  exit 0
else
  echo "notify_bot.sh: hermes -p $BOT chat failed" >&2
  exit 3
fi
