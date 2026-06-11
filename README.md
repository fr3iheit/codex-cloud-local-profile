# Codex Cloud Local Profile

This bundle exports the safe parts of the local Codex behavior profile for use in Codex Cloud.

## Recommended Cloud Setup

Copy this folder into a private repository or a private setup-assets repo, then add this to the Codex Cloud environment setup script:

```bash
bash path/to/codex-cloud-local-profile/install-codex-cloud-profile.sh
```

If Codex Cloud is running in a different repository, use the remote GitHub setup snippet in `CODEX_CLOUD_SETUP.md`.

The installer writes:

- `AGENTS.md`, `config.toml`, hooks, rules, model catalog and subagent profiles under `CODEX_HOME`.
- Custom skills under `CODEX_HOME/skills`.
- Skill links under `$HOME/.agents/skills` when that skill name does not already exist.

## Repo-Only Fallback

If you cannot run a setup script, copy the contents of `profile/repo-overlay/` into the root of a repo. This gives Cloud the global operating rules plus repo-scoped `ralph` and `ralphone` skills.

## Limits

This does not export login state, connector credentials, browser sessions, local app binaries, logs, memories, SQLite state or private runtime caches. Those are intentionally excluded. Plugins and app connectors still need to be installed or authorized in the Codex or ChatGPT UI when Cloud requires them.

After changing an environment setup script in Codex Cloud, reset the environment cache or start a new task so the updated profile is applied.

## Publish To A Private GitHub Repo

Run this locally from this folder:

```bash
./publish-private-github-repo.sh
```

The script asks for a GitHub token with hidden input, creates a private repo, commits this bundle, and pushes it to `main`.

Do not paste the token into chat or commit it to a repo. For a classic GitHub token, use `repo` scope. For organization-owned repos, the token also needs permission to create repositories in that organization.

After publishing, configure Codex Cloud to use that private repo, then set the environment setup script to:

```bash
bash install-codex-cloud-profile.sh
```
