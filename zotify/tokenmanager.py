"""
Spotify Token Manager for personal API credentials

Solution provided by @IsaacAgulhas
https://github.com/Googolplexed0/zotify/issues/135#issuecomment-3686587380

This allows users to use their own Spotify Developer credentials instead of
shared credentials, avoiding rate limiting issues.
"""

import base64
import requests
import time

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

class SpotifyTokenManager:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.expires_at = 0

    def get_token(self):
        if self.access_token and time.time() < self.expires_at:
            return self.access_token

        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        response = requests.post(
            SPOTIFY_TOKEN_URL,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )

        response.raise_for_status()
        data = response.json()

        self.access_token = data["access_token"]
        self.expires_at = time.time() + data["expires_in"] - 30
        return self.access_token
