# Excluded Local Codex State

This export is intentionally a behavior profile, not a clone of the local Codex home.

Excluded categories:

- Authentication files and connector credentials.
- Conversation history, session indexes, browser sessions and archived sessions.
- SQLite runtime state for logs, goals, memory, app state and caches.
- Attachments, generated images, shell snapshots and transient temp files.
- Local macOS app binary paths and notification commands.
- Per-project trust entries pointing to local filesystem paths.
- Plugin or connector authorization state. Install and authorize those from the Codex or ChatGPT UI.

The included `config.toml.template` keeps the behavioral preferences that can be reasonably applied in Cloud, while dropping local-only paths.
