# app/spotify/client.py
import time
import requests

from app.core.settings import settings
from app.spotify.auth import TokenManager


class SpotifyClient:
    """
    Wrapper around Spotify Web API.
    Handles auth + some convenience methods.
    Not full SDK just pieces being used currently (to be updated).
    """

    BASE_URL = "https://api.spotify.com/v1"

    def __init__(self):
        self.token_mgr = TokenManager()
        self._token = None
        self._token_expiry = 0

    def _get_token(self):
        # reuse existing token if still valid
        if self._token and time.time() < self._token_expiry:
            return self._token

        data = self.token_mgr.load_token()
        if not data:
            raise RuntimeError("No Spotify token found. Run the auth flow first.")

        self._token = data["access_token"]
        self._token_expiry = time.time() + (data.get("expires_in", 3500))

        return self._token

    def _headers(self):
        token = self._get_token()
        return {"Authorization": f"Bearer {token}"}

    def _get(self, path, params=None):
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        r = requests.get(url, headers=self._headers(), params=params)

        # If expired refresh and retry once
        if r.status_code == 401:
            self.token_mgr.refresh_token()
            r = requests.get(url, headers=self._headers(), params=params)

        r.raise_for_status()
        return r.json()

    def _post(self, path, payload=None):
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        r = requests.post(url, headers=self._headers(), json=payload)

        if r.status_code == 401:
            self.token_mgr.refresh_token()
            r = requests.post(url, headers=self._headers(), json=payload)

        r.raise_for_status()
        return r.json() if r.text else None

    # Public API -----------------------------------------------------

    def current_user(self):
        return self._get("me")

    def get_playlists(self, limit=50):
        # returns the user's playlists (first page only for now)
        return self._get("me/playlists", params={"limit": limit})

    def get_playlist_tracks(self, playlist_id):
        # Spotify is paginated so fetch until done
        items = []
        url = f"playlists/{playlist_id}/tracks"
        params = {"limit": 100}
        data = self._get(url, params=params)
        items.extend(data.get("items", []))

        next_url = data.get("next")

        # follow pagination manually (simplest approach)
        while next_url:
            # Spotify provides full URL here - direct GET
            r = requests.get(next_url, headers=self._headers())
            if r.status_code == 401:
                self.token_mgr.refresh_token()
                r = requests.get(next_url, headers=self._headers())

            r.raise_for_status()
            data = r.json()
            items.extend(data.get("items", []))
            next_url = data.get("next")

        return items

    def reorder_playlist(self, playlist_id, uris):
        """
        Rebuild playlist with new order.
        Easiest approach: create a new playlist version.
        More control than Spotify's reorder endpoint.
        """
        name = f"Shuffled – {int(time.time())}"
        user_id = self.current_user()["id"]

        new_pl = self._post(f"users/{user_id}/playlists", {"name": name})
        new_id = new_pl["id"]

        # chunk inserts because Spotify only allows 100 per call
        chunk = 100
        for i in range(0, len(uris), chunk):
            group = uris[i : i + chunk]
            self._post(f"playlists/{new_id}/tracks", {"uris": group})

        return new_id

