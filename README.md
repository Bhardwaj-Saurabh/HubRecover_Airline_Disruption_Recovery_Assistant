# HubRecover

Synthetic Airline Disruption Recovery Assistant for a fictional OCC Duty Manager.

The selected implementation is a local Python/Google ADK backend with a web review interface. Development has started with the deterministic domain foundation; the interface and end-to-end recovery loop are not yet built. See [BUILD-STATUS.md](BUILD-STATUS.md) for observed checks and remaining work.

## Development

Requires Python 3.11+ and uv.

```sh
uv sync --locked
uv run pytest -q
```

Tests run offline without an API key. The ADK compatibility tests invoke function nodes and a human pause, but do not call a model. No credentials are required for this increment.

Read [AGENT.md](AGENT.md) before implementation changes. [PRD.md](PRD.md) owns product requirements and [ARCHITECTURE-ADK.md](ARCHITECTURE-ADK.md) defines the backend contracts. [START-HERE.md](START-HERE.md) explains the separate LMS profile.

All operational policies are fictional teaching defaults. This project has no live airline integrations or authority to perform operational actions.
