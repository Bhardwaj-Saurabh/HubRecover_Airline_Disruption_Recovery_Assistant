#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
  uv sync --locked
  print 'Open http://127.0.0.1:8765 in your browser. Press Ctrl+C to stop.'
  exec uv run python -m hubrecover
elif [[ -x .venv/bin/python ]]; then
  print 'Open http://127.0.0.1:8765 in your browser. Press Ctrl+C to stop.'
  exec .venv/bin/python -m hubrecover
else
  print 'Python 3.11+ and uv are required. See README.md for setup.'
  read '?Press Enter to close.'
fi
