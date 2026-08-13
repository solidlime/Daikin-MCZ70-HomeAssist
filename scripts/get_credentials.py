#!/usr/bin/env python3
"""Obtain Daikin Smart DB cloud credentials for the MCZ70 Home Assistant integration.

Runs the dsioti OAuth2 flow (authorize -> auth -> token exchange) directly
against Daikin's servers -- no phone or proxy capture needed -- and prints
the values for the HA config flow (mainly the refresh token).

Credentials are only printed to stdout, never written to disk.

Usage:
    $env:DAIKIN_USER="you@example.com"; $env:DAIKIN_PW="secret"; python scripts/get_credentials.py --ip 192.168.1.50
    DAIKIN_USER=you@example.com DAIKIN_PW=secret python3 scripts/get_credentials.py

Environment (both required):
    DAIKIN_USER   Daikin Smart DB account e-mail
    DAIKIN_PW     Daikin Smart DB account password

Optional arguments:
    --ip <addr>   Also fetch id/pw/port from the device's LAN basic_info
                  (http://<addr>/common/basic_info) and print them.
"""

import argparse
import base64
import hashlib
import http.cookiejar
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

# Endpoint shared by the authorize / auth / token steps.
BASE = "https://prod-dsioti.daikinsmartdb.jp/dsioti/oauth2"

# Public constants embedded in the Daikin Smart APP APK. Keep in sync with
# custom_components/daikin_mcz70/const.py.
CLIENT_ID = "i66rposkjbceagakohlncsnus"
CLIENT_SECRET = "bp3c3lpt05tnoimqpsq1c73uhegl9vhei0voks58bphlqisjjqd"
REDIRECT_URI = "daikinsmartapp://callback"
UUID = "49ffb6aa-88fe-4fb4-a9aa-63499e130f51"  # not validated by the server
DEVICE_ID = "DEVICE_ID_0000019E9D29009D"  # fixed client device id from the APK

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "Chrome/116.0 Mobile Safari/537.36"
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not follow 302s: the flow relies on reading their Location."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def get_location(opener, req) -> tuple[int, str, str]:
    """Send a request; return (status, Location header, body excerpt)."""
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, r.headers.get("Location", ""), ""
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        return e.code, e.headers.get("Location", ""), body


def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


def fetch_basic_info(ip: str) -> dict:
    """Parse the LAN /common/basic_info key=value response."""
    url = f"http://{ip}/common/basic_info"
    text = ""
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception as err:
        die(f"basic_info request failed ({url}): {err}")
    info: dict[str, str] = {}
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key.strip():
            info[key.strip()] = urllib.parse.unquote(value.strip())
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ip", metavar="ADDR", help="device IP to fetch id/pw/port from basic_info")
    args = parser.parse_args()

    username = os.environ.get("DAIKIN_USER", "").strip()
    password = os.environ.get("DAIKIN_PW", "")
    if not username or not password:
        parser.print_help()
        die("DAIKIN_USER and DAIKIN_PW environment variables are both required")

    print("Tokens will be printed to stdout. Do not share them.")

    verifier, challenge = pkce_pair()
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(cj))

    # 1. authorize: server ignores our state and issues its own
    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": secrets.token_hex(32),
        "client_device_id": DEVICE_ID,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "display": "daikinsmartapp",
        "lang": "ja",
        "uuid": UUID,
    })
    status, loc, body = get_location(opener, urllib.request.Request(BASE + "/authorize?" + query))
    m = re.search(r"state=([^&\s]+)", loc or "")
    state = m.group(1) if m else ""
    if status != 302 or not state:
        die(f"authorize failed (HTTP {status}){f': {body[:200]}' if body else ''}")
    print(f"[1/3] authorize OK (server state {state[:16]}...)")

    # 2. auth: exchange the e-mail/password for a code
    req = urllib.request.Request(
        BASE + "/auth",
        data=json.dumps({
            "username": username,
            "password": password,
            "state": state,
            "uuid": UUID,
        }).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    status, loc, body = get_location(opener, req)
    m = re.search(r"code=([^&\s]+)", loc or "")
    code = m.group(1) if m else ""
    if status != 302 or not code:
        die(f"auth failed (HTTP {status}){f': {body[:200]}' if body else ''}")
    print(f"[2/3] auth OK (code {len(code)} chars)")

    # 3. token exchange (form-encoded, PKCE verifier included)
    req = urllib.request.Request(
        BASE + "/token",
        data=urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code_verifier": verifier,
            "redirect_uri": REDIRECT_URI,
        }).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", USER_AGENT)
    tokens: dict = {}
    try:
        with opener.open(req, timeout=20) as r:
            tokens = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        die(f"token exchange failed (HTTP {e.code}): {e.read().decode('utf-8', 'replace')[:200]}")
    refresh = tokens.get("refresh_token", "")
    if not refresh:
        die(f"token exchange failed: no refresh_token in response: {tokens}")
    print(f"[3/3] token exchange OK (expires_in={tokens.get('expires_in')}s)")

    # 4. report the values needed by the HA config flow
    print("\n=== Config flow input ===\n")
    print(f"Refresh Token: {refresh}")
    print(f"Token lifetime: {tokens.get('expires_in')}s (auto-refreshed by the integration)")
    print("Access token: managed automatically by the integration (not printed)")
    print("Terminal ID: leave empty")
    print("UUID / Client ID / Client Secret / Redirect URI: pre-filled defaults")

    if args.ip:
        info = fetch_basic_info(args.ip)
        for key, label in (("id", "ID"), ("pw", "SPW"), ("port", "Port")):
            value = info.get(key, "")
            if not value:
                print(f"WARNING: '{key}' not found in basic_info from {args.ip}", file=sys.stderr)
            print(f"{label}: {value}")
    else:
        print("\nTip: pass --ip <device-ip> to also print id/spw/port "
              "(otherwise they are auto-filled from basic_info during setup)")


if __name__ == "__main__":
    main()
