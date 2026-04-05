# UI UX Pro Max – Setup for Cursor

## Cursor version

- Use **Cursor 2.3.5 or newer**. Upgrade via **Help → Check for Updates** (or [cursor.com](https://cursor.com)).

## Where this skill lives

- **Project skill (this repo):** `.cursor/skills/ui-ux-pro-max/SKILL.md`  
  The agent will use it when this project is open.

- **Personal skill (all projects):** Copy the skill to your user directory:
  - **Windows:** `%USERPROFILE%\.cursor\skills\ui-ux-pro-max\`
  - **macOS/Linux:** `~/.cursor/skills/ui-ux-pro-max/`
  - Create the folder and copy `SKILL.md` (and optionally this `SETUP.md`) there.

Note: For Cursor, use **`.cursor/skills/`** (not `~/.claude/skills/`). The `~/.claude/skills` path is for Claude Code.

## Restart Cursor

After adding or changing skills, restart Cursor so it rescans Agent Skills.

## Verify in Settings

1. Open **Settings** (Ctrl+, or Cmd+,).
2. Go to **Rules** (or **Cursor Settings → General**).
3. Confirm the **Agent Skills** section exists and that **ui-ux-pro-max** (or your project/personal skills) are listed.

## Files in this project

| Path | Purpose |
|------|--------|
| `.cursor/skills/ui-ux-pro-max/SKILL.md` | Agent skill: when to apply, design system workflow, checklist |
| `.cursor/commands/ui-ux-pro-max.md` | Custom command: type `/ui-ux-pro-max` in chat to run the workflow |

## Full install (optional)

For the full UI UX Pro Max toolkit (Python design-system script, data files), use the official CLI:

```bash
npm install -g uipro-cli
cd /path/to/your/project
uipro init --ai cursor
```

This adds scripts and data under `.cursor/skills/ui-ux-pro-max/` (or the platform-specific path the CLI uses). The `SKILL.md` in this repo is a standalone Cursor skill that works without the CLI.

## Reference

- [UI UX Pro Max on GitHub](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
