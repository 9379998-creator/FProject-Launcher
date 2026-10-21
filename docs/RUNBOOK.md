# Runbook

## Start of next work session

Before making product changes, read:

1. `AGENTS.md`
2. `docs/RUNBOOK.md`
3. `docs/ENCODING.md`
4. `docs/HANDOFF_2026-08-12.md`
5. `docs/ROADMAP.md`
6. `docs/DECISIONS.md`

Then summarize the current accepted state and propose the next implementation plan.

## Local launch target

Preferred local workspace:

```text
C:\FEngineering_Launcher_v3
```

## Port policy

Use one active development port for v3. Proposed default:

```text
http://127.0.0.1:8780/
```

Old ports such as `8766`, `8768`, and `8770` are legacy/donor contexts unless explicitly restarted for comparison.

## Start on Windows

Use the project launcher script so PowerShell, Python, and backend output are forced into UTF-8:

```powershell
.\scripts\start_windows.cmd
```

Do not start the backend with random inline PowerShell snippets when Russian paths or labels are involved.

This is a hard project rule for people and agents. Random launches can reintroduce mojibake or pass broken Cyrillic paths into Python/Poppler. If the server was started another way, stop it and restart through:

```powershell
.\scripts\start_windows.cmd
```

## Encoding check

Run before and after editing Russian UI/backend text:

```powershell
.\scripts\check_encoding.cmd
```

If this check fails, fix encoding first. Do not continue product changes on top of corrupted Cyrillic.

## Current accepted PDF workflow

Current accepted PDF model:

- mass overview render: `150 DPI`;
- active/opened page render: `300 DPI`;
- cache is used for both levels;
- viewer shows the current quality state;
- wide tree mode is used for browsing long file names before display;
- after pressing `Отобразить`, the right side returns to the viewer.

Do not replace this with all-pages-at-300-DPI rendering unless the user explicitly asks.

## Current working URL

```text
http://127.0.0.1:8780/
```
