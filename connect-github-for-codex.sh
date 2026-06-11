#!/usr/bin/env bash
set -euo pipefail

API_ROOT="${GITHUB_API_URL:-https://api.github.com}"
KEYCHAIN_SERVICE="codex-github-token"
TOKEN_ACCOUNT="${USER:-codex}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

need curl
need git
need osascript
need python3
need security

get_token_from_dialog() {
  osascript <<'APPLESCRIPT'
set tokenDialog to display dialog "Paste a GitHub token for Codex.\n\nRequired for full repo operations: repo scope. The token will be stored in macOS Keychain and will not be printed." default answer "" with hidden answer buttons {"Cancel", "OK"} default button "OK" cancel button "Cancel"
return text returned of tokenDialog
APPLESCRIPT
}

json_get() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

path = sys.argv[1].split(".")
value = json.loads(sys.argv[2])
for part in path:
    value = value[part]
print(value)
PY
}

TOKEN="$(get_token_from_dialog)"
if [ -z "$TOKEN" ]; then
  echo "No token entered." >&2
  exit 1
fi

tmp_response="$(mktemp)"
trap 'rm -f "$tmp_response"' EXIT

status="$(
  curl -sS -o "$tmp_response" -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$API_ROOT/user"
)"

if [ "$status" != "200" ]; then
  echo "GitHub token test failed. HTTP $status:" >&2
  cat "$tmp_response" >&2
  exit 1
fi

LOGIN="$(json_get login "$(cat "$tmp_response")")"

security add-generic-password \
  -a "$TOKEN_ACCOUNT" \
  -s "$KEYCHAIN_SERVICE" \
  -w "$TOKEN" \
  -U >/dev/null

git config --global credential.helper osxkeychain
printf 'protocol=https\nhost=github.com\nusername=x-access-token\npassword=%s\n\n' "$TOKEN" | git credential approve

CODEX_BIN_DIR="${CODEX_HOME:-$HOME/.codex}/bin"
mkdir -p "$CODEX_BIN_DIR"
cat >"$CODEX_BIN_DIR/github-token" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
security find-generic-password -a "${USER:-codex}" -s codex-github-token -w
SH
chmod 700 "$CODEX_BIN_DIR/github-token"

cat >"$CODEX_BIN_DIR/github-api" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
METHOD="${1:?method required}"
PATH_PART="${2:?path required}"
BODY="${3:-}"
TOKEN="$(security find-generic-password -a "${USER:-codex}" -s codex-github-token -w)"
API_ROOT="${GITHUB_API_URL:-https://api.github.com}"
if [ -n "$BODY" ]; then
  curl -sS \
    -X "$METHOD" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -d "$BODY" \
    "$API_ROOT$PATH_PART"
else
  curl -sS \
    -X "$METHOD" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$API_ROOT$PATH_PART"
fi
SH
chmod 700 "$CODEX_BIN_DIR/github-api"

echo "GitHub connected for Codex as: $LOGIN"
echo "Token stored in macOS Keychain service: $KEYCHAIN_SERVICE"
echo "Git credential helper configured for github.com HTTPS operations."
echo "Helper scripts:"
echo "- $CODEX_BIN_DIR/github-token"
echo "- $CODEX_BIN_DIR/github-api"
