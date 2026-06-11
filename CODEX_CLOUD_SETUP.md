# Codex Cloud Setup From Another Repo

Use this when Codex Cloud is running in a different repository and needs to install this public profile repo.

## Setup Script

Paste this into the Codex Cloud environment setup script:

```bash
set -euo pipefail

PROFILE_REPO="https://github.com/fr3iheit/codex-cloud-local-profile.git"
PROFILE_DIR="/tmp/codex-cloud-local-profile"

rm -rf "$PROFILE_DIR"
git clone --depth 1 "$PROFILE_REPO" "$PROFILE_DIR"

bash "$PROFILE_DIR/install-codex-cloud-profile.sh"
```

## If The Profile Repo Is The Selected Cloud Repo

If Codex Cloud is running directly on `fr3iheit/codex-cloud-local-profile`, use only:

```bash
bash install-codex-cloud-profile.sh
```
