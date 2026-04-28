#!/usr/bin/env bash
# scripts/install_hooks.sh
# Installs pre-commit, pre-push, and commit-msg hooks per CLAUDE.md §5.
set -euo pipefail

HOOKS_DIR=".git/hooks"
mkdir -p "$HOOKS_DIR"

cat > "$HOOKS_DIR/pre-commit" <<'EOF'
#!/usr/bin/env bash
set -e
echo "[pre-commit] ruff"
ruff check .
echo "[pre-commit] mypy"
mypy --no-incremental .
echo "[pre-commit] CLAUDE.md presence"
test -f CLAUDE.md
echo "[pre-commit] forbid hardcoded keys"
if git diff --cached -U0 | grep -E "(sk-ant-[A-Za-z0-9_-]{20,}|ALPACA_API_KEY=[A-Za-z0-9])" >/dev/null; then
  echo "Refusing: looks like a secret in the diff." && exit 1
fi
EOF

cat > "$HOOKS_DIR/pre-push" <<'EOF'
#!/usr/bin/env bash
set -e
echo "[pre-push] pytest"
pytest -q
EOF

cat > "$HOOKS_DIR/commit-msg" <<'EOF'
#!/usr/bin/env bash
msg_file="$1"
first_line=$(head -n1 "$msg_file")
if ! echo "$first_line" | grep -Eq "^(feat|fix|chore|refactor|docs|test|risk):"; then
  echo "Commit message must start with feat:|fix:|chore:|refactor:|docs:|test:|risk:"
  exit 1
fi
# risk-relevant changes require risk: prefix
if git diff --cached --name-only | grep -E "^(agents/risk_executor_agent\.py|knowledge/)" >/dev/null; then
  if ! echo "$first_line" | grep -Eq "^risk:"; then
    echo "Edits to risk_executor or knowledge/ require a 'risk:' commit prefix."
    exit 1
  fi
fi
EOF

chmod +x "$HOOKS_DIR"/{pre-commit,pre-push,commit-msg}
echo "Hooks installed in $HOOKS_DIR"
