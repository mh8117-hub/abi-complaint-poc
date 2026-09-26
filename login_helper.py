"""Get an Open WebUI session token (JWT) when API keys are disabled.

Run it yourself in a terminal:   py login_helper.py
It asks for your Open WebUI email and password (the password is hidden
while you type) and signs in with POST /api/v1/auths/signin. The
returned JWT is saved to the Windows user environment variable
OPENWEBUI_API_KEY. The token and password are never printed or written to
the repository.
Endpoint source: open-webui backend/open_webui/routers/auths.py (signin route).
"""

from __future__ import annotations

import datetime as dt
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("OPENWEBUI_BASE_URL", "http://172.22.42.174:8080").rstrip("/")


def main() -> int:
    email = input(f"Open WebUI email for {BASE}: ").strip()
    password = getpass.getpass("Password (hidden): ")
    req = urllib.request.Request(
        BASE + "/api/v1/auths/signin",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Sign-in failed: HTTP {e.code} {e.read().decode(errors='replace')[:200]}")
        return 1
    except urllib.error.URLError as e:
        print(f"Cannot reach {BASE}: {e.reason}. Is the VPN connected?")
        return 1
    token = data.get("token")
    if not token:
        print("Sign-in succeeded but no token was returned.")
        return 1
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "OPENWEBUI_API_KEY", 0, winreg.REG_SZ, token)
        where = "Windows user environment variable OPENWEBUI_API_KEY"
    else:
        path = os.path.expanduser("~/.openwebui_token")
        with open(path, "w") as f:
            f.write(token)
        os.chmod(path, 0o600)
        where = path
    exp = data.get("expires_at")
    exp_s = dt.datetime.fromtimestamp(exp).isoformat() if exp else "no expiry reported"
    print(f"OK: signed in as {data.get('name')} (role: {data.get('role')}). Token saved to {where}. Expires: {exp_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
