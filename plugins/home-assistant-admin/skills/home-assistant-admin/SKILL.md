---
name: home-assistant-admin
description: Administer and troubleshoot Home Assistant installations using a connected Home Assistant app/MCP. Use for HA YAML, automations, packages, dashboards, AppDaemon, custom_components, integration diagnostics, logs, configuration validation, reloads, restarts, backups, rollback, and Solis/Eimo energy integration troubleshooting.
compatibility: Requires a connected Home Assistant app/MCP for live read/write actions. File editing capabilities may be provided by Home Assistant File Editor, SSH, Samba, or equivalent app tools.
metadata:
  author: celadondeep
  version: "1.0.0"
---

# Home Assistant Admin

Use this skill whenever the user asks to inspect, modify, repair, optimize, or troubleshoot Home Assistant.

## Core principle

Prefer working directly in the connected Home Assistant instance instead of asking the user to manually copy commands or files.

Never claim a change was applied until the write/action result has been verified.

## Tool availability

Read `references/ha-mcp-connection.md` when the HA app/MCP is installed but its tools are missing, or when reconnecting a new chat/workspace.

1. Look for an already connected Home Assistant app/MCP first.
2. If the app exposes a Home Assistant best-practices or skill-guide tool, read it before the first live write.
3. If the app is connected but its tools are unavailable in the current runtime, say that clearly. Do not pretend a write occurred.
4. A Skill supplies workflow knowledge; the connected app/MCP supplies live read/write capability.

## Default change workflow

For any persistent configuration or code change:

1. **Inspect**
   - Read current state and relevant file/config entry first.
   - Inspect related entities, automations, logs, and integration state if they materially affect the change.

2. **Back up**
   - Preserve the original content before overwriting.
   - Prefer a timestamped sibling copy for filesystem changes, e.g. `file.py.bak-YYYYMMDD-HHMMSS`.
   - For small edits, retaining exact original content in the working context is acceptable if the connected tool does not expose filesystem copy.

3. **Modify minimally**
   - Change only what is needed.
   - Preserve existing naming and structure unless redesign is explicitly requested.
   - Never write credentials, tokens, passwords, or secrets into reusable skill/reference files.

4. **Validate**
   - YAML/package/automation changes: run Home Assistant configuration validation when available.
   - Python custom integration/AppDaemon changes: run syntax/compile validation when available.
   - JSON: parse before applying.
   - Do not restart after a failed validation.

5. **Apply**
   - Reload the smallest possible subsystem if a reload is sufficient.
   - Restart Home Assistant for changes to Python code under `custom_components/` unless the integration explicitly supports a reliable unload/reload path and the change does not require module re-import.
   - AppDaemon code normally uses AppDaemon reload/restart semantics where supported.

6. **Verify**
   - Check integration/config-entry state.
   - Check affected entity states.
   - Inspect fresh logs for errors and expected API/action paths.
   - Confirm the requested behavior, not merely that the service restarted.

7. **Rollback on regression**
   - Restore the backup/original content.
   - Revalidate.
   - Reapply reload/restart.
   - Report the concrete failure observed.

## Important Home Assistant paths

Common config root paths are `/config` or `/homeassistant`. Determine the live instance's actual root from the connected tools instead of assuming.

Typical locations:
- `configuration.yaml`
- `automations.yaml`
- `scripts.yaml`
- `packages/`
- `custom_components/`
- `appdaemon/` or the AppDaemon add-on's configured apps directory
- `.storage/` — do not edit directly unless there is no supported API/config path and the user explicitly accepts the risk.

## Automations and packages

Prefer native Home Assistant constructs:
- triggers / conditions / actions
- helpers
- scripts
- template entities
- packages

When editing a package:
- preserve unrelated package content;
- validate the complete resulting YAML;
- reload only the relevant domains when safe;
- use a full restart if integration/platform initialization changed.

## Custom integrations

For `custom_components/<domain>/`:

1. Inspect `manifest.json`, `__init__.py`, coordinator/client modules, entity modules, and config flow as relevant.
2. Keep network discovery separate from live polling when possible.
3. Avoid all-or-nothing startup dependencies if partial operation can recover later.
4. Handle unavailable/None coordinator data explicitly.
5. Use bounded retries and distinguish:
   - timeout/connectivity
   - device offline
   - authentication/signature
   - rate limit
   - malformed/empty discovery responses
6. After Python edits, clear stale `__pycache__` only if needed and restart Home Assistant.
7. Verify both setup state and actual entity/data updates after restart.

## Logs

When troubleshooting:
- establish the first failure in time, not only the last exception;
- group repeated retries instead of treating each as a separate cause;
- compare successful historical request paths with failing current paths;
- note HTTP/API result code, endpoint, retry budget, and timing;
- verify whether the problem is discovery, authentication, polling, parsing, or device-side availability.

## Solis / Eimo troubleshooting

Read `references/solis-eimo.md` when the task involves SolisCloud, Eimo, Solis hybrid inverter control, stale cloud data, polling, `solis_cloud_control`, or `solis` integrations.

## File Editor safety

Read `references/file-editing.md` before using a File Editor style API to overwrite a large file.

## Communication style

Be technical and concise.
For live changes, tell the user what has actually been changed and verified.
Avoid asking for confirmation repeatedly when the user has already authorized the requested modification.
