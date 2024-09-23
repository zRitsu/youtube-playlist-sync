import enum
import json
import os
import re
import sys
import tempfile
import time
import traceback
from typing import Optional

import emoji
import psutil
from discoIPC.ipc import DiscordIPC
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4

yt_playlist_regex = re.compile(r'(?<=list=)[a-zA-Z0-9_-]+')

yt_video_regex = re.compile(r'(?:^|(?<=\W))[-a-zA-Z0-9_]{11}(?:$|(?=\W))')


players = {
    "potplayermini64.exe": {
        "name": "Daum PotPlayer (x64)",
        "icon": "https://upload.wikimedia.org/wikipedia/commons/e/e0/PotPlayer_logo_%282017%29.png"
    },
    "potplayermini.exe": {
        "name": "Daum PotPlayer",
        "icon": "https://upload.wikimedia.org/wikipedia/commons/e/e0/PotPlayer_logo_%282017%29.png"
    },
    "mpc-hc64.exe": {
        "name": "Media Player Classic HC-x64",
        "icon": "https://upload.wikimedia.org/wikipedia/commons/7/76/Media_Player_Classic_logo.png"
    },
    "mpc-hc.exe": {
        "name": "Media Player Classic HC",
        "icon": "https://upload.wikimedia.org/wikipedia/commons/7/76/Media_Player_Classic_logo.png"
    },
    "foobar2000.exe": {
        "name":"foobar2000",
        "icon": "https://i.sstatic.net/JowsQ.jpg"
    },
    "vlc.exe": {
        "name": "VLC Player",
        "icon": "https://cdn1.iconfinder.com/data/icons/metro-ui-dock-icon-set--icons-by-dakirby/512/VLC_Media_Player.png"
    },
    "winamp.exe": {
        "name": "Winamp",
        "icon": "https://iili.io/dsKTaUB.md.png"
    },
    "aimp.exe": {
        "name": "AIMP",
        "icon": "https://iili.io/dsKpuSV.md.png"
    },
    "musicbee.exe": {
        "name": "MusicBee",
        "icon": "https://iili.io/dsf9KQe.png"
    },
    "mediamonkeyengine.exe": {
        "name": "Media Monkey",
        "icon": "https://iili.io/dsfaPs9.png",
    },
    "kmplayer.exe": {
        "name": "KM Player",
        "icon": "https://cdn6.aptoide.com/imgs/b/4/8/b48d248dc9514b23279b87e3e3c70c7d_icon.png?w=512",
    },

    # os players do windows tem um problema que ocasionalmente fica lendo todos os arquivos de música
    # do pc o que faz com que as informações de arquivos de músicas em uso pelo processo confunda a música ativa no momento.

    #"wmplayer.exe": {
    #    "name": "Windows Media Player (Legacy)",
    #    "icon": "https://iili.io/dsfd18x.png"
    #},
    #"microsoft.media.player.exe": {
    #    "name": "Microsoft Media Player",
    #    "icon": "https://iili.io/dsfqJvs.md.png"
    #}
}

class ActivityType(enum.Enum):
    playing = 0
    listening = 2
    watching = 3
    competing = 5

class MyDiscordIPC(DiscordIPC):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _send(self, opcode, payload):

        encoded_payload = self._encode(opcode, payload)

        try:
            if self.platform == 'windows':
                self.socket.write(encoded_payload)
                try:
                    self.socket.flush()
                except OSError:
                    raise IPCError(f'Não foi possivel enviar dados ao discord via IPC.', client=self)
            else:
                self.socket.send(encoded_payload)
        except Exception as e:
            raise IPCError(f'Não foi possivel enviar dados ao discord via IPC | Erro: {repr(e)}.', client=self)

    def update_activity(self, activity=None):

        if activity:
            self.last_data = activity
        else:
            self.last_data.clear()

        try:
            super().update_activity(activity=activity)
        except Exception as e:
            self.last_data.clear()
            raise e

    def _get_ipc_path(self, id=0):
        # credits: pypresence https://github.com/qwertyquerty/pypresence/blob/31718fb442e563f879160c16e0215c7c1fa16f23/pypresence/utils.py#L25
        ipc = f"discord-ipc-{id}"

        if sys.platform in ('linux', 'darwin'):
            tempdir = (os.environ.get('XDG_RUNTIME_DIR') or tempfile.gettempdir())
            paths = ['.', 'snap.discord', 'app/com.discordapp.Discord', 'app/com.discordapp.DiscordCanary']
        elif sys.platform == 'win32':
            tempdir = r'\\?\pipe'
            paths = ['.']
        else:
            return

        for path in paths:
            full_path = os.path.abspath(os.path.join(tempdir, path))
            if sys.platform == 'win32' or os.path.isdir(full_path):
                for entry in os.scandir(full_path):
                    if entry.name.startswith(ipc) and os.path.exists(entry):
                        return entry.path

class IPCError(Exception):

    def __init__(self, error, client: MyDiscordIPC):
        self.error = error
        self.client = client

    def __repr__(self):
        return self.error

class RpcRun:

    def __init__(self):
        self.playlist_id: Optional[str] = None
        self.playlist_name: Optional[str] = None
        self.process: Optional[psutil.Process] = None
        self.author: Optional[str] = None
        self.track_name: Optional[str] = None
        self.track_number: Optional[str] = None
        self.video_id: Optional[str] = None
        self.rpc_client = None
        self.player_name = None
        self.player_icon = None
        self.activity_type = ActivityType.listening.value
        self.start_loop()

    def clear_info(self):
        self.playlist_id = None
        self.playlist_name = None
        self.author = None
        self.track_name = None
        self.video_id = None
        try:
            self.rpc_client.clear()
        except AttributeError:
            pass
        time.sleep(15)

    def start_loop(self):

        while True:

            try:
                if not self.process or not self.process.is_running():
                    self.get_process()
                    if not self.process:
                        self.clear_info()
                        continue

                elif not self.check_process(self.process):
                    self.clear_info()
                    continue

                if not self.rpc_client:
                    for i in range(10):
                        try:
                            rpc = MyDiscordIPC("1287237467400962109", pipe=i)
                            rpc.connect()
                            self.rpc_client = rpc
                            break
                        except Exception:
                            continue

                    if not self.rpc_client:
                        time.sleep(15)
                        continue

                    try:
                        print(f'Usuário conectado: {self.rpc_client.data["data"]["user"]["username"]} '
                              f'[{self.rpc_client.data["data"]["user"]["id"]}]')
                    except KeyError:
                        self.rpc_client = None
                        continue

                # Contagem de caracteres do botão consomem o dobro do limite de um caracter normal
                playlist_limit = 25 if emoji.emoji_count(self.playlist_name) < 1 else 18

                # testes
                try:
                    with open("playlist_info.json") as f:
                        playlist_data = json.load(f)
                except FileNotFoundError:
                    playlist_data = {}

                payload = {
                    "details": self.track_name,
                    "state": f"By: {', '.join(self.author.split(', ')[:4])}",
                    "assets": {
                        "large_image": f"https://img.youtube.com/vi/{self.video_id}/default.jpg",
                        "large_text": f"Via: {self.player_name}",
                        "small_image": self.player_icon,

                    },
                    "type": ActivityType.listening.value,
                    "buttons": [
                        {
                            "label": "Listen on Youtube",
                            "url": f"https://www.youtube.com/watch?v={self.video_id}&list={self.playlist_id}{playlist_data.get(self.video_id, '')}"
                        },
                        {
                            "label": self.playlist_name[:playlist_limit] if len(self.playlist_name[:playlist_limit]) > 13 else f"Playlist: {self.playlist_name[:playlist_limit]}",
                            "url": f"https://www.youtube.com/playlist?list={self.playlist_id}"
                        },
                    ]
                }

                if self.track_number:
                    try:
                        track_number = int(self.track_number.split("/")[0])-1
                    except:
                        track_number = self.track_number
                    payload["buttons"][0]["url"] += f"&index={track_number}"
                    payload["buttons"][0]["label"] += f" ({self.track_number})"

                try:
                    self.rpc_client.update_activity(payload)
                except Exception:
                    traceback.print_exc()
                    self.rpc_client = None
                    time.sleep(30)

            except Exception:
                traceback.print_exc()
                time.sleep(60)
            else:
                time.sleep(15)

    def check_process(self, proc: psutil.Process):

        for o in proc.open_files():

            if o.path.endswith((".mp3", ".mp4")) and (yt_id := yt_video_regex.search(o.path)):
                try:
                    with open(f"{os.path.dirname(o.path)}/playlist_info.json") as f:
                        playlist_info = json.load(f)
                except FileNotFoundError:
                    continue
                self.playlist_name = playlist_info["title"]
                self.playlist_id = playlist_info["id"]

                func = MP3 if o.path.endswith(".mp3") else MP4

                tags = func(o.path, ID3=EasyID3)
                self.track_name = tags["title"][0]
                self.author = tags["artist"][0]

                try:
                    self.track_number = tags.get("tracknumber")[0]
                except:
                    self.track_number = None

                self.video_id = yt_id.group()
                self.process = proc

                player_info = players.get(proc.name().lower())

                self.player_name = player_info["name"]
                self.player_icon = player_info["icon"]
                return True

    def get_process(self):

        for proc in psutil.process_iter(['pid', 'name']):

            if [p for p in players if p.lower() in (proc.name()).lower()]:

                if not self.check_process(proc):
                    continue

                return proc

        self.process = None

RpcRun()
