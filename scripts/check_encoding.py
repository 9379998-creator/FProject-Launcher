from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCE_PATHS = [
    "app/backend/server.py",
    "app/frontend/app.js",
    "app/frontend/index.html",
    "app/frontend/styles.css",
]

MOJIBAKE_MARKERS = [
    "\u0420\u045f",
    "\u0420\u045b",
    "\u0420\u2014",
    "\u0421\u0453",
    "\u00d0",
    "\u00d1",
]


def main() -> int:
    failed = False
    markdown_paths = [
        str(path.relative_to(REPO_ROOT))
        for folder in [REPO_ROOT, REPO_ROOT / "docs"]
        for path in sorted(folder.glob("*.md"))
    ]
    paths = sorted(set(SOURCE_PATHS + markdown_paths))
    for relative in paths:
        path = REPO_ROOT / relative
        text = path.read_text(encoding="utf-8")
        hits = [marker for marker in MOJIBAKE_MARKERS if marker in text]
        if hits:
            failed = True
            escaped = ", ".join(marker.encode("unicode_escape").decode("ascii") for marker in hits)
            print(f"{relative}: MOJIBAKE? {escaped}")
        else:
            print(f"{relative}: OK")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
