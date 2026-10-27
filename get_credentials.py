#!/usr/bin/env python3
"""Obtain an Auth0 refresh token for the Shark Matrix integration.

Uses the normal Authorization-Code + PKCE flow (the same one the SharkClean app
uses), so YOU complete the login in your own browser — passing Cloudflare and any
2FA interactively. Password/ROPC grants are blocked by bot detection, which is why
this interactive flow is the supported path.

No third-party dependencies (stdlib only).

Steps:
  1. Run this script. It prints an authorize URL.
  2. Open it in a browser, log in to your SharkClean account.
  3. The browser will try to redirect to a `com.sharkninja.shark://...` URL and
     fail to open it (that's fine). Copy that full redirect URL from the address
     bar (it contains `?code=...`) and paste it back here.
  4. The script exchanges the code and prints your refresh_token.
"""
import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import urllib.request

AUTH_HOST = "login.sharkninja.com"
CLIENT_ID = "wsguxrqm77mq4LtrTrwg8ZJUxmSrexGi"
SCOPE = "openid profile email offline_access"
# Auth0 Android redirect format: {scheme}://{domain}/android/{package}/callback
REDIRECT_URI = (
    "com.sharkninja.shark://login.sharkninja.com/android/com.sharkninja.shark/callback"
)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    verifier = _b64url(os.urandom(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)

    authorize = f"https://{AUTH_HOST}/authorize?" + urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "nonce": nonce,
            "prompt": "login",
        }
    )

    print("\n1) Open this URL in your browser and log in:\n")
    print(authorize)
    print(
        "\n2) After login the browser will try to open a "
        "'com.sharkninja.shark://...' link and fail — that's expected."
        "\n   Copy that full URL (or just the value of its `code=` parameter)."
    )
    pasted = input("\n3) Paste the redirect URL (or the code) here:\n> ").strip()

    if pasted.startswith("com.sharkninja.shark://") or "code=" in pasted:
        q = urllib.parse.urlparse(pasted).query or pasted
        params = urllib.parse.parse_qs(q)
        code = params.get("code", [pasted])[0]
    else:
        code = pasted

    token_req = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        }
    ).encode()

    req = urllib.request.Request(
        f"https://{AUTH_HOST}/oauth/token",
        data=token_req,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as err:
        print("\nToken exchange failed:", err.read().decode()[:500])
        return

    rt = data.get("refresh_token")
    if not rt:
        print("\nNo refresh_token returned. Full response:")
        print(json.dumps(data, indent=2)[:800])
        return

    print("\n=== SUCCESS ===")
    print("refresh_token:\n", rt)
    print(
        "\nUse this as the 'Auth0 refresh token' in the integration config."
        "\nYou also need your household_id (see the README)."
    )


if __name__ == "__main__":
    main()
