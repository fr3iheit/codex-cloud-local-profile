#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_NAME="codex-cloud-local-profile"
API_ROOT="${GITHUB_API_URL:-https://api.github.com}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
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

api() {
  local method="$1"
  local path="$2"
  local body="${3:-}"
  local out="$4"
  local status
  if [ -n "$body" ]; then
    status="$(
      curl -sS -o "$out" -w "%{http_code}" \
        -X "$method" \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        -d "$body" \
        "$API_ROOT$path"
    )"
  else
    status="$(
      curl -sS -o "$out" -w "%{http_code}" \
        -X "$method" \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "$API_ROOT$path"
    )"
  fi
  printf '%s' "$status"
}

need curl
need git
need python3

echo "This publishes the Codex Cloud profile bundle as a private GitHub repository."
echo "Do not paste your token into chat. Paste it only at the hidden prompt below."
echo

if [ -z "${GITHUB_TOKEN:-}" ]; then
  printf "GitHub token: " >&2
  IFS= read -r -s GITHUB_TOKEN
  echo >&2
fi
export GITHUB_TOKEN

tmp_response="$(mktemp)"
trap 'rm -f "$tmp_response" "$ASKPASS_FILE" 2>/dev/null || true; rm -rf "$WORK_DIR" 2>/dev/null || true' EXIT
status="$(api GET /user "" "$tmp_response")"
if [ "$status" != "200" ]; then
  echo "GitHub authentication failed. HTTP $status:" >&2
  cat "$tmp_response" >&2
  exit 1
fi

login="$(json_get login "$(cat "$tmp_response")")"
printf "Owner/user [%s]: " "$login" >&2
IFS= read -r OWNER
OWNER="${OWNER:-$login}"

printf "Repository name [%s]: " "$DEFAULT_REPO_NAME" >&2
IFS= read -r REPO_NAME
REPO_NAME="${REPO_NAME:-$DEFAULT_REPO_NAME}"

printf "Create private repo %s/%s and push bundle? [y/N]: " "$OWNER" "$REPO_NAME" >&2
IFS= read -r CONFIRM
case "$CONFIRM" in
  y|Y|yes|YES) ;;
  *) echo "Aborted."; exit 0 ;;
esac

repo_json="$(
  python3 - "$REPO_NAME" <<'PY'
import json
import sys

name = sys.argv[1]
print(json.dumps({
    "name": name,
    "private": True,
    "description": "Sanitized Codex Cloud profile: settings, skills, Ralph and Ralphone.",
    "auto_init": False,
}))
PY
)"

if [ "$OWNER" = "$login" ]; then
  create_path="/user/repos"
else
  create_path="/orgs/$OWNER/repos"
fi

status="$(api POST "$create_path" "$repo_json" "$tmp_response")"
if [ "$status" != "201" ]; then
  echo "Repository creation failed. HTTP $status:" >&2
  cat "$tmp_response" >&2
  echo >&2
  echo "If the repo already exists, create a fresh empty repo name and rerun." >&2
  exit 1
fi

clone_url="$(json_get clone_url "$(cat "$tmp_response")")"
html_url="$(json_get html_url "$(cat "$tmp_response")")"

WORK_DIR="$(mktemp -d)"
ASKPASS_FILE="$(mktemp)"
cat >"$ASKPASS_FILE" <<'SH'
#!/usr/bin/env sh
case "$1" in
  *Username*) printf '%s\n' "x-access-token" ;;
  *Password*) printf '%s\n' "$GITHUB_TOKEN" ;;
  *) printf '%s\n' "" ;;
esac
SH
chmod 700 "$ASKPASS_FILE"

rsync -a \
  --exclude '.git' \
  --exclude '.DS_Store' \
  "$BUNDLE_DIR/" "$WORK_DIR/"

cd "$WORK_DIR"
git init -b main >/dev/null
git add .
git commit -m "Add Codex Cloud profile" >/dev/null
git remote add origin "$clone_url"
GIT_ASKPASS="$ASKPASS_FILE" GIT_TERMINAL_PROMPT=0 git push -u origin main

echo
echo "Published private repository:"
echo "$html_url"
echo
echo "Use this in Codex Cloud setup when the profile repo is the selected repo:"
echo "bash install-codex-cloud-profile.sh"
echo
echo "Or from another private repo that can access it:"
echo "git clone --depth 1 $clone_url /tmp/codex-cloud-local-profile"
echo "bash /tmp/codex-cloud-local-profile/install-codex-cloud-profile.sh"
