# Codex Cloud Setup From Another Repo

Use this when Codex Cloud is running in a different repository and needs to install this private profile repo.

## 1. Add A Cloud Secret

In the Codex Cloud environment settings, add a secret:

```text
CODEX_GITHUB_TOKEN
```

Its value must be a GitHub token that can read:

```text
https://github.com/fr3iheit/codex-cloud-local-profile
```

For a classic PAT, `repo` scope is enough.

## 2. Use This Setup Script

Paste this into the Codex Cloud environment setup script:

```bash
set -euo pipefail

PROFILE_REPO="https://github.com/fr3iheit/codex-cloud-local-profile.git"
PROFILE_DIR="/tmp/codex-cloud-local-profile"
ASKPASS="/tmp/codex-github-askpass.sh"

cat > "$ASKPASS" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  *Username*) printf '%s\n' "x-access-token" ;;
  *Password*) printf '%s\n' "$CODEX_GITHUB_TOKEN" ;;
  *) printf '%s\n' "" ;;
esac
EOF
chmod 700 "$ASKPASS"

rm -rf "$PROFILE_DIR"
GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 git clone --depth 1 "$PROFILE_REPO" "$PROFILE_DIR"
rm -f "$ASKPASS"

bash "$PROFILE_DIR/install-codex-cloud-profile.sh"
```

## If The Profile Repo Is The Selected Cloud Repo

If Codex Cloud is running directly on `fr3iheit/codex-cloud-local-profile`, use only:

```bash
bash install-codex-cloud-profile.sh
```
