# Home Assistant repository instructions

This repository is the working Home Assistant configuration and automation source.

## Required workflow

For Home Assistant work, use the repository skill:

`.agents/skills/home-assistant-admin/SKILL.md`

When a live Home Assistant app/MCP is callable, prefer direct verified work in the connected HA instance rather than giving the user manual copy/paste steps.

For persistent changes:

1. inspect the current live state/file;
2. preserve a backup;
3. make the smallest change;
4. validate;
5. reload/restart the smallest required subsystem;
6. verify fresh logs and entity/config-entry state;
7. rollback on a concrete regression.

Never claim a Git commit is already live in Home Assistant unless live deployment and verification actually succeeded.

## Eimo current work

For current Eimo SolisCloud recovery, read:

`.agents/skills/home-assistant-admin/references/eimo-stage1.md`

The validated Git source is `main`. The pre-Stage-1 backup branch is:

`backup/eimo-solis-stage1-20260909`

Live deployment helpers:

- `scripts/deploy_eimo_solis_stage1.sh`
- `scripts/check_eimo_solis_stage1.sh`

Do not broaden Eimo-specific recovery settings to other Solis inverter entries.

## HA-MCP

For connector recovery, read:

`.agents/skills/home-assistant-admin/references/ha-mcp-connection.md`

Never commit a generated HA-MCP Connect URL, webhook ID, direct private path, Home Assistant token, or other credential.
