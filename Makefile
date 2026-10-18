.PHONY: run test evidence live-evidence
run:
	uv run python -m hubrecover
test:
	uv run pytest -q
	node --check hubrecover/web/app.js
evidence:
	uv run python -m evaluation.held_out
	uv run python -m evaluation.benchmark

live-evidence:
	uv run python -m evaluation.live_ai
