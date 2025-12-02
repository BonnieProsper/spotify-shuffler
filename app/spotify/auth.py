# app/spotify/auth.py
"""
Spotify Auth manager (Authorization Code with PKCE).

Features:
- PKCE (S256) code challenge generation
- Spins a tiny local HTTP server to receive the redirect (dev)
- Exchanges code for tokens and refreshes tokens when needed
- Persists tokens in a local JSON file (simple persistence for demo)

Notes for user:
- For production, don't persist refresh tokens to plaintext files.
- Make sure the redirect URI is registered in your Spotify app settings.
"""

from __future__ import annotations
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

import requests

# Constants (kept here to be explicit)
SPOTIFY_ACCOUNTS = "https://accounts.spotify.com"
TOKEN_URL = SPOTIFY_ACCOUNTS + "/api/token"
AUTHORIZE_URL = SPOTIFY_ACCOUNTS + "/authorize"

DEFAULT_TOKEN_FILE = os.path.expanduser("~/.spotify_shuffler_tokens.json")


def _b64_urlsafe_no_pad(b: bytes) -> str:
    """URL-safe base64 without '=' padding (PKCE uses that)."""
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _sha256_hex(s: str) -> bytes:
    return hashlib.sha256(s.encode("ascii")).digest()


@dataclass
class TokenSet:
    access_token: str
    refresh_token: Optional[str]
    expires_at: float  # epoch seconds

    def to_json(self):
        return {"access_token": self.access_token, "refresh_token": self.refresh_token, "expires_at": self.expires_at}

    @classmethod
    def from_json(cls, obj):
        return cls(access_token=obj["access_token"], refresh_token=obj.get("refresh_token"), expires_at=obj.get("expires_at", 0.0))


class _RedirectHandler(BaseHTTPRequestHandler):
    """
    Small handler that captures the 'code' query param from Spotify redirect
    and stores it on the server class for the caller to pick up.
    """
    server_version = "SpotifyPKCEServer/0.1"
    code = None
    state = None

    def do_GET(self):
        # naive parsing for small dev server
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if "error" in qs:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization failed or was cancelled. You may close this window.")
            _RedirectHandler.code = None
            return

        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        _RedirectHandler.code = code
        _RedirectHandler.state = state

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorization complete. You may close this tab/window.")


class SpotifyAuth:
    """
    Manages PKCE-based auth.
    Usage pattern:
      auth = SpotifyAuth(client_id, redirect_uri, token_file=...)
      if not auth.load_tokens(): auth.start_auth_flow()
      access = auth.get_access_token()
    """

    def __init__(self, client_id: str, redirect_uri: str = "http://127.0.0.1:8888/callback", token_file: str = DEFAULT_TOKEN_FILE):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.token_file = token_file
        self._tokens: Optional[TokenSet] = None

    # Token storage -------------------------------------
    def save_tokens(self):
        if not self._tokens:
            return
        try:
            with open(self.token_file, "w", encoding="utf8") as fh:
                json.dump(self._tokens.to_json(), fh)
        except Exception:
            # don't make this fatal, best effort persist
            pass

    def load_tokens(self) -> bool:
        if not os.path.exists(self.token_file):
            return False
        try:
            with open(self.token_file, "r", encoding="utf8") as fh:
                data = json.load(fh)
            self._tokens = TokenSet.from_json(data)
            return True
        except Exception:
            return False

    # PKCE helpers -----------------------------------------------
    @staticmethod
    def _make_code_verifier(length: int = 64) -> str:
        # per RFC-7636: 43-128 chars from [A-Z / a-z / 0-9 / "-" / "." / "_" / "~"]
        return _b64_urlsafe_no_pad(secrets.token_bytes(length))[:128]

    @staticmethod
    def _make_code_challenge(verifier: str) -> str:
        digest = _sha256_hex(verifier)
        return _b64_urlsafe_no_pad(digest)

    # Auth flow ------------------------------------------------ 
    def start_auth_flow(self, scopes=("playlist-modify-private", "playlist-read-private", "user-read-private")) -> None:
        """
        Starts interactive PKCE auth:
        - constructs authorize URL with code_challenge
        - spins a tiny local HTTP server to catch the redirect
        - exchanges code for tokens
        """
        verifier = self._make_code_verifier()
        challenge = self._make_code_challenge(verifier)
        state = secrets.token_urlsafe(16)

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
        }
        from urllib.parse import urlencode

        auth_url = AUTHORIZE_URL + "?" + urlencode(params)
        print("\nOpen this URL in your browser and authorize the app:\n")
        print(auth_url + "\n")
        print("Waiting for the redirect... (will timeout in ~120s)\n")

        # small local server to handle single GET request
        parsed = self.redirect_uri.split(":")
        if parsed[1].startswith("//"):
            # very simple port extraction
            hostport = parsed[1].lstrip("//")
            host, port = hostport.split(":")[0], int(hostport.split(":")[1].split("/")[0])
        else:
            host, port = "127.0.0.1", 8888

        srv = HTTPServer((host, port), _RedirectHandler)
        # run single handle_request on separate thread to time out
        thr = threading.Thread(target=srv.handle_request, daemon=True)
        thr.start()
        thr.join(timeout=120)
        try:
            srv.server_close()
        except Exception:
            pass

        code = _RedirectHandler.code
        got_state = _RedirectHandler.state
        _RedirectHandler.code = None
        _RedirectHandler.state = None

        if not code:
            raise RuntimeError("Authorization code not received (timed out or denied).")

        if got_state != state:
            # warn but continue — state is a CSRF protection; mismatch indicates something odd.
            print("Warning: state mismatch in PKCE flow (continuing anyway).")

        # exchange code for token
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": verifier,
        }
        r = requests.post(TOKEN_URL, data=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        self._tokens = TokenSet(access_token=data["access_token"], refresh_token=data.get("refresh_token"), expires_at=time.time() + int(data.get("expires_in", 3600)) - 60)
        # persist for later runs
        self.save_tokens()

    # Token refresh/access ---------------------------------------------------
    def _refresh(self) -> None:
        if not self._tokens or not self._tokens.refresh_token:
            raise RuntimeError("No refresh token available: re-run auth flow.")
        payload = {"grant_type": "refresh_token", "refresh_token": self._tokens.refresh_token, "client_id": self.client_id}
        r = requests.post(TOKEN_URL, data=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        # note: refresh responses sometimes omit refresh_token (Spotify docs). Update what we have.
        new_refresh = data.get("refresh_token", self._tokens.refresh_token)
        self._tokens = TokenSet(access_token=data["access_token"], refresh_token=new_refresh, expires_at=time.time() + int(data.get("expires_in", 3600)) - 60)
        self.save_tokens()

    def get_access_token(self) -> str:
        """
        Returns a valid access token (refreshes it if expired).
        Call this before making API calls.
        """
        if not self._tokens:
            raise RuntimeError("No tokens loaded — call load_tokens() or start_auth_flow() first.")
        if time.time() > self._tokens.expires_at:
            # attempt to refresh
            self._refresh()
        return self._tokens.access_token
