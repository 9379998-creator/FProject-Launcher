"""
license_guard.py - Trial Period & Anti-Tamper License Guard for F.E.R.O. Launcher
Part of the FERO safe distribution and compilation pipeline.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# When False, launcher operates in unrestricted internal development mode.
# When True (set during protected build), enforces expiration date & anti-tamper clock check.
TRIAL_ENABLED: bool = False

# Hardcoded expiration date in ISO format YYYY-MM-DD (overridden during build)
TRIAL_EXPIRY_DATE: str = "2029-12-31"

# Product name & contact for renewal
CONTACT_EMAIL: str = "info@ferospb.ru"
PRODUCT_NAME: str = "F.E.R.O. Launcher"


def _get_runtime_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data) / "FEngineering_Launcher" / "runtime"
    else:
        base = Path(__file__).resolve().parent.parent.parent / "runtime"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_hardware_id() -> str:
    """Generate a stable machine fingerprint (Hardware ID)."""
    raw_parts = [
        platform.node(),
        platform.machine(),
        platform.processor(),
    ]
    try:
        if platform.system() == "Windows":
            cmd = 'powershell -NoProfile -Command "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"'
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3, shell=True)
            if res.returncode == 0 and res.stdout.strip():
                raw_parts.append(res.stdout.strip())
    except Exception:
        pass

    seed = ":".join(raw_parts).encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest().upper()
    return f"FERO-{digest[:4]}-{digest[4:8]}-{digest[8:12]}"


def _get_state_file() -> Path:
    return _get_runtime_dir() / ".license_ts"


def check_trial_status() -> Dict[str, Any]:
    """
    Validates trial expiration and anti-tamper clock consistency.
    Returns status dict with active, expired, tampered, days_left, message.
    """
    if not TRIAL_ENABLED:
        return {
            "trial_enabled": False,
            "active": True,
            "expired": False,
            "tampered": False,
            "days_left": 9999,
            "message": "Режим разработки (неограниченная лицензия)",
            "hwid": get_hardware_id(),
        }

    now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()

    # 1. Anti-tamper clock check
    state_file = _get_state_file()
    tampered = False
    if state_file.exists():
        try:
            raw = state_file.read_text(encoding="utf-8").strip()
            decoded = json.loads(base64.b64decode(raw).decode("utf-8"))
            last_ts = float(decoded.get("ts", 0))
            if now_ts < (last_ts - 120):  # Clock moved back more than 2 minutes
                tampered = True
        except Exception:
            pass

    # Save current timestamp
    try:
        payload = json.dumps({"ts": now_ts, "hwid": get_hardware_id()})
        state_file.write_text(base64.b64encode(payload.encode("utf-8")).decode("utf-8"), encoding="utf-8")
    except Exception:
        pass

    if tampered:
        return {
            "trial_enabled": True,
            "active": False,
            "expired": False,
            "tampered": True,
            "days_left": 0,
            "message": "Обнаружено изменение системного времени. Программа заблокирована. Обратитесь: " + CONTACT_EMAIL,
            "hwid": get_hardware_id(),
        }

    # 2. Expiration date check
    try:
        expiry_dt = datetime.strptime(TRIAL_EXPIRY_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        expiry_dt = datetime(2027, 1, 1, tzinfo=timezone.utc)

    diff = expiry_dt - now_utc
    days_left = max(0, diff.days)

    if now_utc > expiry_dt:
        return {
            "trial_enabled": True,
            "active": False,
            "expired": True,
            "tampered": False,
            "days_left": 0,
            "message": f"Срок действия ознакомительной версии истёк ({TRIAL_EXPIRY_DATE}). Для продления обратитесь: {CONTACT_EMAIL}",
            "hwid": get_hardware_id(),
        }

    return {
        "trial_enabled": True,
        "active": True,
        "expired": False,
        "tampered": False,
        "days_left": days_left,
        "expires_on": TRIAL_EXPIRY_DATE,
        "message": f"Ознакомительная версия активна (осталось дней: {days_left})",
        "hwid": get_hardware_id(),
    }
