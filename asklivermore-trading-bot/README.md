# AskLivermore Trading Bot

Production-grade, fully autonomous LangGraph multi-agent day trading bot built around the `@asklivermore` methodology (Livermore 5-step + bull flag / VCP / Golden Pocket / RVOL / RS confluence).

> **Disclaimer**: This project automates trade *research and execution*. You are responsible for paper-trading validation, broker compliance, capital at risk, and regulatory adherence in your jurisdiction. The defaults are conservative (2% risk per trade, kill switches enabled) but no software substitutes for human oversight.

---

## Architecture

Nine LangGraph agents arranged in a directed graph with a self-evaluation loop and persistent memory:

```
                ┌───────────────────────────────────────────┐
                │        Graphify (persistent memory)       │
                └───────────────────────────────────────────┘
                                  ▲
                                  │ read/write
   Scanner ──► Confluence ──► Social ──► Memory ──► Zodchiii ──► Peers ──► Reasoning ──► Risk ──► Monitor
      (1)        (2)           (3)       (4)         (5)         (6)         (7)         (8)        (9)
                                              ▲                                                       │
                                              └───────────── self-eval feedback ◄──────────────────────┘
```

**Decision rule**: a setup must satisfy `confluence_score >= 4`, `sentiment >= 0`, and match at least one canonical AskLivermore pattern before reaching the RiskExecutor. Otherwise it is journaled and discarded.

---

## Quick start

### 1. Clone and configure

```bash
git clone https://github.com/BuckeyeBizHub/asklivermore-trading-bot.git
cd asklivermore-trading-bot
cp .env.example .env
# Fill in API keys: ANTHROPIC_API_KEY, POLYGON_API_KEY, ALPACA_*, IBKR_*, TELEGRAM_*, GRAPHIFY_*
```

### 2. Pull the external skills/repos

These are kept as git submodules / sibling installs because they evolve independently:

```bash
# Persistent memory
git clone https://github.com/safishamsi/graphify.git external/graphify
# Social-media skill pack
git clone https://github.com/charlie947/social-media-skills.git external/social-media-skills
# Peer messaging
git clone https://github.com/so-ainsight/claude-peers.git external/claude-peers
```

The adapters in `core/` import from these paths. If you put them elsewhere, override `EXTERNAL_PATH_*` in `.env`.

### 3. Run paper-trading locally

```bash
docker compose up --build
```

This launches the agent loop against Alpaca paper. To go live, set `EXECUTION_MODE=live` and `BROKER=ibkr` in `.env`.

### 4. Run on an NYC VPS (recommended for live)

```bash
# On the VPS:
git clone https://github.com/BuckeyeBizHub/asklivermore-trading-bot.git
cd asklivermore-trading-bot
./scripts/deploy_vps.sh
```

The deploy script installs Docker, pulls images, sets up systemd, and configures log rotation.

---

## Providing CSV exports from the AskLivermore dashboard

If you'd rather feed the bot manually exported watchlists / scans rather than running the live scanner:

1. Export your CSV from `https://asklivermore.com/dashboard`.
2. Drop it into `data/csv_imports/` (any filename ending in `.csv`).
3. The `MemoryGraphAgent` picks up new files on each loop iteration and ingests them into Graphify.
4. Column mapping is configured in `core/csv_schema.yaml` — adjust if AskLivermore changes their export format.

The bot will treat CSV-sourced tickers as **candidates** that still must pass confluence + sentiment + reasoning gates. CSV ingestion does not bypass risk checks.

---

## File layout

```
asklivermore-trading-bot/
├── agents/                    # The 9 LangGraph agents
│   ├── scanner_agent.py
│   ├── confluence_validator_agent.py
│   ├── social_sentiment_agent.py
│   ├── memory_graph_agent.py
│   ├── zodchiii_best_practices_agent.py
│   ├── peer_coordinator_agent.py
│   ├── reasoning_agent.py
│   ├── risk_executor_agent.py
│   └── monitor_journal_agent.py
├── core/                      # Shared infra
│   ├── graph.py               # LangGraph wiring
│   ├── state.py               # Typed AgentState
│   ├── config.py              # Settings (pydantic)
│   ├── llm.py                 # Claude client
│   ├── csv_ingest.py          # AskLivermore CSV import
│   ├── csv_schema.yaml
│   └── adapters/
│       ├── graphify_adapter.py
│       ├── social_skill_adapter.py
│       ├── peers_adapter.py
│       ├── polygon_adapter.py
│       ├── alpaca_adapter.py
│       └── ibkr_adapter.py
├── skills/                    # Local skill packs (mirrors .claude/skills)
├── knowledge/                 # AskLivermore patterns, Livermore rules, etc.
├── data/                      # Mounted volumes
│   ├── csv_imports/
│   ├── journal/
│   └── graphify/
├── scripts/                   # Deployment + ops
├── tests/
├── .claude/                   # CLAUDE.md governance + custom skills
│   ├── skills/
│   └── settings.json
├── docker/
│   ├── Dockerfile
│   └── entrypoint.sh
├── docker-compose.yml
├── pyproject.toml
├── CLAUDE.md
├── .env.example
└── README.md
```

---

## Operating modes

| Mode | Description | Set with |
| --- | --- | --- |
| `scan-only` | Runs scanner + confluence + sentiment, journals candidates, places no orders | `EXECUTION_MODE=scan-only` |
| `paper` | Full pipeline against Alpaca paper account | `EXECUTION_MODE=paper` |
| `live` | Full pipeline against IBKR or Alpaca live | `EXECUTION_MODE=live` |
| `replay` | Re-runs the agent graph against a CSV export for backtesting/journaling | `EXECUTION_MODE=replay` |

---

## Kill switches

The `RiskExecutorAgent` enforces, in order:

1. **Per-trade risk cap**: position sized so worst-case loss ≤ `MAX_RISK_PCT` of equity (default 2%).
2. **Daily loss cap**: halts new entries if realized + unrealized PnL ≤ `-MAX_DAILY_LOSS_PCT` (default -3%).
3. **Drawdown cap**: halts the bot if account equity drops `MAX_DRAWDOWN_PCT` below the high-water mark (default 8%).
4. **Heartbeat**: if the LangGraph loop stalls > `HEARTBEAT_TIMEOUT_S`, the watchdog flattens all positions.
5. **Manual kill**: touch `data/KILL` to halt immediately. The MonitorJournalAgent checks this each tick.

---

## Self-evaluation loop

After every closed trade, `MonitorJournalAgent` writes the outcome to Graphify and triggers a weekly review where the ReasoningAgent reads the past week's journal, scores its own decisions, and proposes adjustments to the confluence weights in `knowledge/asklivermore_patterns.yaml`. Proposed changes are written to `data/journal/proposed_changes/` for human approval — never auto-applied.

---

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy .
```

Pre-commit hooks (installed via `scripts/install_hooks.sh`) enforce structured JSON outputs, type hints, and `CLAUDE.md` policy compliance on every commit.

---

## License

MIT. See `LICENSE`.
