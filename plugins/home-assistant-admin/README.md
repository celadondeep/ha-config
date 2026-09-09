# Home Assistant Admin plugin

Reusable Home Assistant administration workflow for ChatGPT/Codex.

## Included

- Safe inspect → backup → modify → validate → apply → verify → rollback workflow
- Home Assistant YAML/package/automation guidance
- AppDaemon and custom integration handling
- File Editor safety
- HA-MCP connection/recovery guidance
- Solis/Eimo recovery workflow

## Live access

This repository intentionally **does not bundle a `.mcp.json` containing the Home Assistant Connect URL**.

The HA-MCP remote Connect URL contains a secret webhook ID and acts as a credential. Committing it to GitHub would expose the Home Assistant control endpoint.

Live Home Assistant reads/writes therefore use the user's existing connected **HA** app/MCP. If its tools are missing in a new runtime, follow:

`skills/home-assistant-admin/references/ha-mcp-connection.md`

Canonical HA-MCP source:

`homeassistant-ai/ha-mcp-integration`

The live server URL is recovered inside Home Assistant from:

**Settings → Devices & Services → HA-MCP Custom Component → HA-MCP Server → Configure**

The privileged **HA-MCP File & YAML Tools** entry must also be enabled for direct filesystem/YAML editing.

## Why there is no plugin-local MCP secret config

Current plugin MCP packaging does not provide a reliable install-time per-user secret/URL input mechanism for a plugin-provided server. The safe design is therefore:

1. keep reusable workflow knowledge in this plugin;
2. keep the generated HA-MCP Connect URL in the user's private connector/app configuration;
3. never store the secret URL in GitHub, skills, documentation, or public logs.

## Eimo Stage-1

The current repo also contains the Eimo SolisCloud Stage-1 recovery patch and safe deployment helpers:

- `scripts/deploy_eimo_solis_stage1.sh`
- `scripts/check_eimo_solis_stage1.sh`
- backup branch: `backup/eimo-solis-stage1-20260909`

GitHub changes are not considered live until they have been deployed into the active Home Assistant config directory and Home Assistant has been restarted and verified.
