# File editing safety

Use this reference for Home Assistant File Editor, SSH, Samba, or equivalent file-write workflows.

## Before overwrite

- Read the current complete file.
- Preserve a backup or exact original content.
- Confirm the target path belongs to the active Home Assistant config root.
- Avoid writing a truncated payload.

## Large files

Some file-editor APIs or intermediaries may have payload limits. For a large dashboard/YAML/code file:

1. Compare source and written byte/line counts if the tool exposes them.
2. Re-read the tail of the written file.
3. Prefer filesystem copy/SSH/Samba mechanisms for large payloads if the editor API is known to truncate.
4. Do not reload/restart until the post-write file passes validation.

## Python

For custom integration Python files:
- preserve indentation and encoding;
- validate with Python compile/syntax tooling if available;
- restart Home Assistant after code replacement;
- inspect the first startup traceback if import fails.

## Rollback

A rollback is not complete until:
1. original content is restored;
2. configuration/syntax validation passes;
3. the relevant subsystem is reloaded/restarted;
4. the integration/entity state is checked.
