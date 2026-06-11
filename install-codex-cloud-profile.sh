#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_DIR="$SCRIPT_DIR/profile"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
AGENTS_HOME="${AGENTS_HOME:-$HOME/.agents}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

backup_if_exists() {
  local target="$1"
  if [ -e "$target" ] || [ -L "$target" ]; then
    cp -R "$target" "$target.backup-$STAMP"
  fi
}

render_template() {
  local src="$1"
  local dst="$2"
  python3 - "$src" "$dst" "$CODEX_HOME" <<'PY'
from pathlib import Path
import sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
codex_home = sys.argv[3]
text = src.read_text(encoding="utf-8").replace("__CODEX_HOME__", codex_home)
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(text, encoding="utf-8")
PY
}

mkdir -p "$CODEX_HOME" "$CODEX_HOME/hooks" "$CODEX_HOME/agents" "$CODEX_HOME/rules" "$CODEX_HOME/skills" "$AGENTS_HOME/skills"

backup_if_exists "$CODEX_HOME/AGENTS.md"
backup_if_exists "$CODEX_HOME/config.toml"
backup_if_exists "$CODEX_HOME/hooks.json"
backup_if_exists "$CODEX_HOME/rules/default.rules"

cp "$PROFILE_DIR/codex-home/AGENTS.md" "$CODEX_HOME/AGENTS.md"
cp "$PROFILE_DIR/codex-home/model_catalog.override.json" "$CODEX_HOME/model_catalog.override.json"
cp "$PROFILE_DIR/codex-home/agents/"*.toml "$CODEX_HOME/agents/"
cp "$PROFILE_DIR/codex-home/hooks/"*.py "$CODEX_HOME/hooks/"
render_template "$PROFILE_DIR/codex-home/config.toml.template" "$CODEX_HOME/config.toml"
render_template "$PROFILE_DIR/codex-home/hooks.json.template" "$CODEX_HOME/hooks.json"
render_template "$PROFILE_DIR/codex-home/rules/default.rules.template" "$CODEX_HOME/rules/default.rules"

for skill_dir in "$PROFILE_DIR/skills/"*; do
  [ -d "$skill_dir" ] || continue
  [ -f "$skill_dir/SKILL.md" ] || continue
  name="$(basename "$skill_dir")"
  dest="$CODEX_HOME/skills/$name"
  backup_if_exists "$dest"
  mkdir -p "$dest"
  cp -R "$skill_dir/." "$dest/"

  agents_skill="$AGENTS_HOME/skills/$name"
  if [ -L "$agents_skill" ]; then
    ln -sfn "$dest" "$agents_skill"
  elif [ ! -e "$agents_skill" ]; then
    ln -s "$dest" "$agents_skill"
  fi
done

echo "Installed Codex cloud profile into $CODEX_HOME"
echo "Installed skill links under $AGENTS_HOME/skills where no local skill already existed"
