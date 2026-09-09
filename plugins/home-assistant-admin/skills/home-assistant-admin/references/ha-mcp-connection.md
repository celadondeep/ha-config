# HA-MCP connection and recovery

Use this reference when the Home Assistant app/MCP is installed but its tools are not available in the current ChatGPT runtime, or when a new chat/workspace needs to reconnect.

## Canonical integration

HACS custom repository:

`https://github.com/homeassistant-ai/ha-mcp-integration`

Home Assistant integration name:

**HA-MCP Custom Component**

Recommended server entry:

**HA-MCP Server**

Privileged filesystem/YAML entry:

**HA-MCP File & YAML Tools**

The in-process HA-MCP Server is the preferred server. Do not run a second competing ha-mcp server unless there is a deliberate migration plan.

## Remote Connect URL

Open:

**Settings → Devices & Services → HA-MCP Custom Component → HA-MCP Server → Configure**

Copy the generated **Connect URL**.

Expected remote shape:

`https://<home-assistant-domain>/api/webhook/<secret-webhook-id>`

The component also prints the URL in the Home Assistant log when the server starts.

For LAN clients there may also be a direct address shaped like:

`http://<ha-ip>:9584/private_<secret-path>`

Do not commit either secret URL to GitHub, a reusable Skill, docs, or public logs. The URL itself acts as a credential.

## OAuth / ChatGPT compatibility

Current HA-MCP advertises PKCE S256 and the OAuth discovery metadata required by modern remote MCP clients.

If ChatGPT reports that OAuth metadata does not advertise PKCE/S256, first update the HA-MCP Custom Component and restart Home Assistant rather than creating ad-hoc OAuth proxies.

A normal Home Assistant automation webhook is NOT an MCP endpoint. A URL such as a manually created `/api/webhook/<automation-webhook-id>` must not be substituted for the generated HA-MCP Connect URL.

## File editing

The **HA-MCP File & YAML Tools** entry must be configured when direct filesystem/YAML tools are required.

When file tools are available:
1. Read current content.
2. Back up.
3. Write.
4. Re-read/verify.
5. Validate.
6. Reload/restart the smallest required subsystem.
7. Verify logs and resulting state.

## Runtime missing tools

If the HA app is known to be installed and authorized but no HA tool namespace is exposed in the current runtime:
- do not claim the connection is broken inside Home Assistant;
- do not invent an app ID or webhook ID;
- use the generated Connect URL from the HA-MCP Server Configure screen to reconnect the app;
- once tools appear, continue the pending live operation without asking the user to re-explain the task.

## Plugin app binding

A plugin `.app.json` mapping must use the canonical connected app ID, normally shaped like `connector_...` or `asdk_app_...`.

Do not use the display name `HA` as an invented app ID.

A declared app dependency also does not prove that the app is installed or callable in the current runtime. Verify the actual runtime tool inventory before claiming live access.

Until the canonical private HA app ID is available, keep this plugin skills-only and rely on the user's separately connected HA app/MCP for live actions.
