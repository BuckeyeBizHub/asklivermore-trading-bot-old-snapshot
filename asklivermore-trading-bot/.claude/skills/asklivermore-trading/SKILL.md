---
name: asklivermore-trading
description: Use when modifying any file in this trading bot. Enforces CLAUDE.md governance, the 9-agent architecture, structured JSON outputs, the confluence gate (score >= 4 + positive sentiment), risk caps (2% / 3% / 8%), and forbids ad-hoc broker calls outside RiskExecutorAgent. Read before touching agents/, core/, or knowledge/.
---

# AskLivermore Trading Bot — coding skill

## Before changing anything

1. Read `CLAUDE.md` in repo root. The rules there override anything I say in chat.
2. Identify which of the 9 agents (or shared core) you are touching. Each has a single responsibility.
3. Run `pytest -q` first to know the baseline.

## Hard rules

- **Confluence gate**: a setup needs `confluence_score >= 4` AND positive sentiment AND a matching pattern from `knowledge/asklivermore_patterns.yaml` AND a clean policy check. Never lower this in code; lower it in YAML and commit with a `risk:` prefix.
- **Risk caps**: 2% per trade, 3% daily, 8% drawdown — encoded in `.env` and `core/config.py`. Don't hardcode bypasses.
- **Orders only via RiskExecutorAgent.** Any broker call elsewhere is a bug.
- **All inter-agent IO is structured JSON** validated against `core/state.py` schemas.
- **No `print()`** in production paths. Use `core.logging.get_logger`.

## Adding a new agent

1. Add a Pydantic model for its output to `core/state.py` and a key in `AgentState`.
2. Create `agents/<name>_agent.py` with a class exposing `__call__(state) -> state`.
3. Wire it in `core/graph.py`.
4. Add unit tests in `tests/test_<name>.py` covering: happy path, degraded (external dep down), and a malformed-input rejection.
5. Update CLAUDE.md §2 Output contracts table.

## Adding a new pattern

1. Edit `knowledge/asklivermore_patterns.yaml`.
2. Update the system prompt in `agents/confluence_validator_agent.py` if needed.
3. Add a fixture CSV in `tests/fixtures/` and a regression test that confirms the new pattern is detected.

## Self-evaluation

Don't auto-apply weight changes. Write proposals to `data/journal/proposed_changes/YYYY-WW.json`.

## Forbidden

- Disabling kill switches.
- Storing API keys in code or in tests.
- Catching exceptions and silently `pass`.
- Bypassing the LangGraph entry point with ad-hoc agent calls in scripts.
