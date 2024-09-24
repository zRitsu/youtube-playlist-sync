# -*- coding: utf-8 -*-
import asyncio
import base64
import json
import os.path
import time
from tempfile import gettempdir
from typing import Optional, Union

import aiofiles
from aiohttp import ClientSession


class SpotifyClient:

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, playlist_extra_page_limit: int = 0):

        self.spotify_cache_file = os.path.join(gettempdir(), ".spotify_cache.json")

        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.spotify.com/v1"
        self.spotify_cache = {}
        self.type = "api" if client_id and client_secret else "visitor"
        self.token_refresh = False
        self.playlist_extra_page_limit = playlist_extra_page_limit

        try:
            with open(self.spotify_cache_file) as f:
                self.spotify_cache = json.load(f)
        except FileNotFoundError:
            pass

    async def request(self, path: str, params: dict = None):

        headers = {'Authorization': f'Bearer {await self.get_valid_access_token()}'}

        async with ClientSession() as session:
            async with session.get(f"{self.base_url}/{path}", headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    await self.get_access_token()
                    return await self.request(path=path, params=params)
                else:
                    response.raise_for_status()

    async def get_recommendations(self, seed_tracks: Union[list, str], limit=10):
        if isinstance(seed_tracks, str):
            track_ids = seed_tracks
        else:
            track_ids = ",".join(seed_tracks)

        return await self.request(path='recommendations', params={
            'seed_tracks': track_ids, 'limit': limit
        })

    async def track_search(self, query: str):
        return await self.request(path='search', params = {
        'q': query, 'type': 'track', 'limit': 10
        })

    async def get_access_token(self):

        if self.token_refresh:
            while self.token_refresh:
                await asyncio.sleep(1)
            return

        self.token_refresh = True

        try:
            if not self.client_id or not self.client_secret:
                access_token_url = "https://open.spotify.com/get_access_token?reason=transport&productType=embed"
                async with ClientSession() as session:
                    async with session.get(access_token_url) as response:
                        data = await response.json()
                        self.spotify_cache = {
                            "access_token": data["accessToken"],
                            "expires_in": data["accessTokenExpirationTimestampMs"],
                            "expires_at": time.time() + data["accessTokenExpirationTimestampMs"],
                            "type": "visitor",
                        }
                        self.type = "visitor"
                        print("🎶 - Access token do spotify obtido com sucesso do tipo: visitante.")

            else:
                token_url = 'https://accounts.spotify.com/api/token'

                headers = {
                    'Authorization': 'Basic ' + base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
                }

                data = {
                    'grant_type': 'client_credentials'
                }

                async with ClientSession() as session:
                    async with session.post(token_url, headers=headers, data=data) as response:
                        data = await response.json()

                    if data.get("error"):
                        print(f"⚠️ - Spotify: Ocorreu um erro ao obter token: {data['error_description']}")
                        self.client_id = None
                        self.client_secret = None
                        await self.get_access_token()
                        return

                    self.spotify_cache = data

                    self.type = "api"

                    self.spotify_cache["type"] = "api"

                    self.spotify_cache["expires_at"] = time.time() + self.spotify_cache["expires_in"]

                    print("🎶 - Access token do spotify obtido com sucesso via API Oficial.")

        except Exception as e:
            self.token_refresh = False
            raise e

        self.token_refresh = False

        async with aiofiles.open(self.spotify_cache_file, "w") as f:
            await f.write(json.dumps(self.spotify_cache))

    async def get_valid_access_token(self):
        if not (exp_date := self.spotify_cache.get("expires_at")) or time.time() >= exp_date:
            await self.get_access_token()
        return self.spotify_cache["access_token"]
