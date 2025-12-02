# src/shuffler/spotify_client.py
"""
Minimal Spotify client with PKCE dev flow.
Real app should persist refresh tokens securely.
"""

import base64
import hashlib
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlparse, parse_qs

import requests
import time

SPOTIFY_ACCT = "https://accounts.spotify.com"
SPOTIFY_API = "https://api.spotify.com/v1"


def _code_challenge(verifier: str) -> str:
    h = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(h).rstrip(b"=").decode()


class OAuthServerHandler(BaseHTTPRequestHandler):
    """small HTTP server to catch Spotify redirect in dev"""
    server_verifier = None
    auth_code = None

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        if "code" in qs:
            OAuthServerHandler.auth_code = qs["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK - you can close this tab")
        else:
            self.send_response(400)
            self.end_headers()


class SpotifyClient:
    def __init__(self, client_id: str, redirect_uri="http://127.0.0.1:8080/cb"):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0

    def start_pkce_flow(self, scopes=("playlist-modify-private", "playlist-read-private", "user-library-read")):
        verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode()
        challenge = _code_challenge(verifier)
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
        auth_url = SPOTIFY_ACCT + "/authorize?" + urlencode(params)
        print("Open this URL in a browser and authorize the app:\n\n", auth_url, "\n")

        # start local server to catch the redirect
        srv = HTTPServer(("127.0.0.1", 8080), OAuthServerHandler)
        thr = threading.Thread(target=srv.handle_request)  # single request
        thr.start()
        thr.join(timeout=120)  # wait for user auth
        srv.server_close()

        code = OAuthServerHandler.auth_code
        if not code:
            raise RuntimeError("Auth code not received - timed out or denied")

        # exchange code for tokens
        token_url = SPOTIFY_ACCT + "/api/token"
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": verifier,
        }
        r = requests.post(token_url, data=payload, timeout=10)
        r.raise_for_status()
        data = r.json()
        self._save_tokens(data)

    def _save_tokens(self, data):
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token")
        self.expires_at = time.time() + data.get("expires_in", 3600) - 60

    def _ensure_token(self):
        if not self.access_token or time.time() > self.expires_at:
            # refresh
            if not self.refresh_token:
                raise RuntimeError("No refresh token, re-run auth flow")
            payload = {"grant_type": "refresh_token", "refresh_token": self.refresh_token, "client_id": self.client_id}
            r = requests.post(SPOTIFY_ACCT + "/api/token", data=payload, timeout=10)
            r.raise_for_status()
            self._save_tokens(r.json())

    def _get(self, url, params=None):
        self._ensure_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        r = requests.get(url, headers=headers, params=params or {}, timeout=10)
        r.raise_for_status()
        return r.json()

    def get_playlist_tracks(self, playlist_id: str):
        # paginate through tracks
        url = f"{SPOTIFY_API}/playlists/{playlist_id}/tracks"
        out = []
        params = {"limit": 100, "offset": 0}
        while True:
            data = self._get(url, params=params)
            items = data.get("items", [])
            for it in items:
                if it.get("track"):
                    out.append(it["track"])
            if data.get("next"):
                params["offset"] += params["limit"]
            else:
                break
        return out

    def create_playlist(self, user_id: str, name: str, public=False, desc=""):
        # change url later??, are url/variables correct?
        url = f"{SPOTIFY_API}/users/{user_id}/playlists"
        self._ensure_token()
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        payload = {"name": name, "public": public, "description": desc}
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        return r.json()

    def add_tracks_to_playlist(self, playlist_id: str, uris: list):
        # chunk to 100 per request
        self._ensure_token()
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        for i in range(0, len(uris), 100):
            chunk = uris[i : i + 100]
            url = f"{SPOTIFY_API}/playlists/{playlist_id}/tracks"
            r = requests.post(url, json={"uris": chunk}, headers=headers, timeout=10)
            r.raise_for_status()
        return True

