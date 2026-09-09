# Home Assistant Admin plugin

Reusable Home Assistant administration workflow for ChatGPT/Codex.

## Included

- Safe inspect → backup → modify → validate → apply → verify → rollback workflow
- Home Assistant YAML/package/automation guidance
- AppDaemon and custom integration handling
- File Editor safety
- Solis/Eimo recovery workflow

## Live access

This plugin currently contains workflow guidance only. Live Home Assistant reads/writes still require the existing Home Assistant app/MCP connection.

When the existing HA app ID is available, add a plugin-root `.app.json` and set `"apps": "./.app.json"` in `.codex-plugin/plugin.json`.
