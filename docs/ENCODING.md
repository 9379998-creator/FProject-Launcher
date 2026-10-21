# UTF-8 and Cyrillic rules

Launcher contains Russian UI labels, object names, paths, backend errors, and generated manifests. Encoding mistakes are product bugs.

## Permanent project solution

Use the project bootstrap scripts instead of ad-hoc PowerShell snippets:

```powershell
.\scripts\start_windows.cmd
```

This is mandatory for agents and recommended for manual work. If Launcher was started by a raw PowerShell command, restart it through this script before testing Cyrillic paths or PDF files from Google Drive Desktop.

For encoding checks:

```powershell
.\scripts\check_encoding.cmd
```

These scripts set:

- PowerShell input/output encoding to UTF-8;
- `$OutputEncoding` to UTF-8;
- `PYTHONUTF8=1`;
- `PYTHONIOENCODING=utf-8`.

## What this solves

It prevents the normal development path from corrupting or misdisplaying Russian text in:

- Python output;
- JSON responses;
- frontend labels;
- backend messages;
- paths shown during checks.

## Known Windows trap

Raw `Get-Content`, inline PowerShell strings, and copied Russian paths can still display or pass text incorrectly if the current console is not UTF-8. When checking Cyrillic, prefer:

```powershell
.\scripts\check_encoding.cmd
```

Do not decide that a file is broken only because a raw PowerShell command displayed mojibake.

## Backend serving rule

Static text files must include `charset=utf-8`:

```python
content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
if content_type.startswith("text/") or content_type in {"application/javascript", "text/javascript"}:
    content_type = f"{content_type}; charset=utf-8"
```

JSON responses must use:

```python
json.dumps(payload, ensure_ascii=False).encode("utf-8")
Content-Type: application/json; charset=utf-8
```

## Agent rule

Before changing Russian UI/backend text:

1. Use UTF-8 bootstrap scripts.
2. Edit files as UTF-8.
3. Run `.\scripts\check_encoding.cmd`.
4. Run syntax checks.
5. Run local API/browser smoke test.

Do not add product logic on top of corrupted Cyrillic.
