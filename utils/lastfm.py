import asyncio
import hashlib
import json
import os
import pickle
import pprint
import time
import webbrowser

from aiohttp import ClientSession
from cachetools import TTLCache

cache_file = "./.lastfm_cache"


class LastFmException(Exception):
    def __init__(self, data: dict):
        self.code = data["error"]
        self.message = data["message"]


class LastFM:

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.cache: TTLCache = self.scrobble_load_cache()

    def scrobble_load_cache(self):

        cache = TTLCache(maxsize=10000, ttl=600)

        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                cache.update(pickle.load(f))

        return cache

    def scrobble_save_cache(self):
        with open(cache_file, 'wb') as f:
            pickle.dump(self.cache, f)

    def generate_api_sig(self, params: dict):
        sig = ''.join(f"{key}{params[key]}" for key in sorted(params))
        sig += self.api_secret
        return hashlib.md5(sig.encode('utf-8')).hexdigest()

    async def request_lastfm(self, params: dict):
        params["format"] = "json"
        async with ClientSession() as session:
            async with session.get("http://ws.audioscrobbler.com/2.0/", params=params) as response:
                if (data := await response.json()).get('error'):
                    raise LastFmException(data)
                return data

    async def post_lastfm(self, params: dict):
        params["format"] = "json"
        async with ClientSession() as session:
            async with session.post("http://ws.audioscrobbler.com/2.0/", params=params) as response:
                if (data := await response.json()).get('error'):
                    raise LastFmException(data)
                return data

    async def get_token(self):
        data = await self.request_lastfm(
            params={
                'method': 'auth.getToken',
                'api_key': self.api_key,
                'format': 'json',
            }
        )
        return data['token']

    async def get_session_key(self, token: str):
        params = {
            'method': 'auth.getSession',
            'api_key': self.api_key,
            'token': token,
        }
        params['api_sig'] = self.generate_api_sig(params)
        return await self.request_lastfm(params=params)

    async def track_scrobble(self, artist: str, track: str, album: str, duration: int, session_key: str,
                             chosen_by_user: bool = True):

        params = {
            "method": "track.scrobble",
            "artist[0]": artist,
            "timestamp[0]": str(int(time.time() - 30)),
            "track[0]": track,
            "api_key": self.api_key,
            "sk": session_key,
        }

        if chosen_by_user is False:
            params["chosenByUser[0]"] = "0"

        if album:
            params["album"] = album

        if duration:
            params["duration"] = str(duration)

        params['api_sig'] = self.generate_api_sig(params)

        return await self.post_lastfm(params)

    async def update_nowplaying(self, artist: str, track: str, album: str, duration: int, session_key: str):

        params = {
            "method": "track.updateNowPlaying",
            "artist": artist,
            "track": track,
            "timestamp": str(int(time.time() - 30)),
            "api_key": self.api_key,
            "sk": session_key,
        }

        if album:
            params["album"] = album
        if duration:
            params["duration"] = str(duration)

        params['api_sig'] = self.generate_api_sig(params)

        return await self.post_lastfm(params)

    async def search_track(self, track: str, artist: str = None, limit: int = 30):
        params = {
            'method': 'track.search',
            'track': track,
            'api_key': self.api_key,
            'limit': limit
        }
        if artist:
            params['artist'] = artist
        return (await self.request_lastfm(params))['results']['trackmatches']['track']

    async def get_similar_tracks(self, track: str, artist: str = None, mbid: str = None):
        params = {
            'method': 'track.getSimilar',
            'api_key': self.api_key,
            'autocorrect': 1,
        }
        if mbid:
            params['mbid'] = mbid
        else:
            params['track'] = track
            if artist:
                params['artist'] = artist

        return (await self.request_lastfm(params))['similartracks']['track']

    async def get_similar_artists(self, artist: str, mbid: str = None):
        params = {
            'method': 'artist.getSimilar',
            'api_key': self.api_key,
            'autocorrect': 1,
        }
        if mbid:
            params['mbid'] = mbid
        else:
            params['artist'] = artist

        return (await self.request_lastfm(params))['similarartists']['artist']

    async def user_info(self, session_key: str):
        return (await self.request_lastfm(
            params={
                'method': 'user.getInfo',
                'api_key': self.api_key,
                'sk': session_key,
            }))['user']

    async def open_browser_for_auth(self, user_id: int):

        token = await self.get_token()

        webbrowser.open(f"http://www.last.fm/api/auth/?api_key={self.api_key}&token={token}")

        retries = 10

        while True:
            await asyncio.sleep(10)
            try:
                resp = await self.get_session_key(token=token)
            except Exception as e:
                e = e
                retries -= 1
                if retries < 1:
                    raise e
                continue

            key = resp["session"]["key"]
            username = resp["session"]["name"]

            try:
                with open("../.lastfm_keys.json", encoding="utf-8") as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {}

            data[user_id] = {"username": username, "key": key}

            with open("./.lastfm_keys.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            print(f"Usuário do last.fm autorizado com sucesso: {username}")
            return

if __name__ == '__main__':
    from discord_rpc import MyDiscordIPC
    from dotenv import load_dotenv

    rpc_final = None
    error = None

    load_dotenv()

    lastfm_Key = os.getenv("LASTFM_KEY")
    lastfm_secret = os.getenv("LASTFM_SECRET")

    if not lastfm_Key or not lastfm_secret:
        raise Exception(
            "Você não informou uma key e secret do lastfm no arquivo .env"
        )

    for i in range(10):

        try:
            rpc = MyDiscordIPC("1287237467400962109")
            rpc.connect()
            rpc_final = rpc
            break
        except Exception as e:
            error = e

    if not rpc_final:
        raise error

    username = rpc_final.data["data"]["user"]["username"]
    user_id = rpc_final.data["data"]["user"]["id"]

    print(f"Autenticando acesso do lasf.fm para o usuário: {username} [{user_id}]")

    time.sleep(3)

    FM = LastFM(api_key=lastfm_Key, api_secret=lastfm_secret)

    asyncio.run(FM.open_browser_for_auth(user_id))
