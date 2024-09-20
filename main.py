import logging
import os
import re
import shutil
import time
import traceback
import concurrent.futures
from copy import deepcopy
from tempfile import gettempdir

import yt_dlp

from ffmpeg_check import check_ffmpeg_command, check_ffmpeg

logging.basicConfig(level=logging.INFO, format='%(message)s')

yt_playlist_regex = re.compile(r'(?<=list=)[a-zA-Z0-9_-]+')

yt_video_regex = re.compile(r'(?:^|(?<=\W))[-a-zA-Z0-9_]{11}(?:$|(?=\W))')

temp_dir = gettempdir()

ytdl_download_args = {
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'retries': 30,
    'extract_flat': False,
    'outtmpl': f'{temp_dir}/%(id)s.%(ext)s',
    'extractor_args': {
        'youtube': {
            'skip': [
                'hls',
                'dash'
            ]
        },
        'youtubetab': ['webpage']
    },
    'writethumbnail': True,
    'embed-thumbnail': True,
}

playlist_data = {}

m3u_data = {}

def save_m3u(out_dir: str):

    with open(out_dir, 'w', encoding="utf-8") as f:
        f.write("\n\n".join(m3u_data.values()))

def move_dir(src: str, dst:str):
    for i in os.listdir(src):
        try:
            shutil.move(f"{src}/{i}", dst)
        except Exception as e:
            if not str(e).endswith('already exists'):
                raise e
    shutil.rmtree(src)

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '-', filename).rstrip('. ')

def run():

    if not check_ffmpeg_command():
        ytdl_download_args["ffmpeg_location"] = check_ffmpeg()
        check_ffmpeg_command(ytdl_download_args["ffmpeg_location"], raise_exception=True)

    try:
        os.remove("cookies.temp")
    except FileNotFoundError:
        pass

    try:
        shutil.copy("cookies.txt", "cookies.temp")
        cookie_file = "./cookies.temp"
        print("Usando cookies.txt para obter videos de playlists privadas.")
    except FileNotFoundError:
        cookie_file = None
        print("Uso de cookies.txt ignorado (caso tenha adicionado link de alguma playlist privada da sua conta no "
              "arquivo playlists.txt ela será ignorada com erro de playlist inexistente).")

    if os.path.isfile("./playlists.txt"):
        os.rename("./playlists.txt", "./playlists_links_audio.txt")

    if os.path.isdir("./playlists.old"):
        move_dir("./playlists.old", "./playlists_audio.old")

    try:
        with open("./playlists_links_audio.txt") as f:
            playlists_audio = sorted(list(set([p for p in yt_playlist_regex.findall(f.read())])))
    except FileNotFoundError:
        playlists_audio = []
        with open("./playlists_links_audio.txt", "w") as f:
            f.write("")

    try:
        with open("playlists_audio_directory.txt") as f:
            playlists_audio_directory = [l for l in f.read().split("\n") if l][0]
            os.makedirs(playlists_audio_directory, exist_ok=True)
            if not os.path.isdir(os.path.abspath(playlists_audio_directory)):
                raise Exception(f"O diretório não existe: {playlists_audio_directory}")
    except (IndexError, FileNotFoundError):
        playlists_audio_directory = "./playlists_audio"
        with open("./playlists_audio_directory.txt", "w") as f:
            f.write(playlists_audio_directory)

    try:
        with open("./playlists_links_video.txt") as f:
            playlists_video = sorted(list(set([p for p in yt_playlist_regex.findall(f.read())])))
    except FileNotFoundError:
        playlists_video = []
        with open("./playlists_links_video.txt", "w") as f:
            f.write("")

    try:
        with open("playists_video_directory.txt") as f:
            playist_video_directory = [l for l in f.read().split("\n") if l][0]
            os.makedirs(playist_video_directory)
            if not os.path.isdir(os.path.abspath(playist_video_directory)):
                raise Exception(f"O diretório não existe: {playist_video_directory}")
    except (IndexError, FileNotFoundError):
        playist_video_directory = "./playlists_video"
        with open("./playists_video_directory.txt", "w") as f:
            f.write(playist_video_directory)

    if not playlists_audio and not playlists_video:
        print("Abra o arquivo playlists_links_audio.txt e cole os links das suas playlists do youtube (pra download de "
              "vídeos cole os links de playlists no playlists_links_video.txt).")
        return

    if os.path.isdir("./playlists"):
        print(f"Movendo músicas da pasta playlists para a pasta {playlists_audio_directory}")
        move_dir("./playlists", playlists_audio_directory)

    download_playlist(file_list=playlists_audio, out_dir=playlists_audio_directory, only_audio=True,
                      cookie_file=cookie_file)

    download_playlist(file_list=playlists_video, out_dir=playist_video_directory, only_audio=False,
                      cookie_file=cookie_file)


def download_playlist(file_list: list, out_dir: str, only_audio=True, **kwargs):

    os.makedirs(out_dir, exist_ok=True)

    ytdl_download_args_final = deepcopy(ytdl_download_args)

    if only_audio:
        old_dir = "./playlists_audio.old"
        ext = "mp3"
        ytdl_download_args_final.update(
            {
                'format': 'bestaudio',
                'postprocessors': [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                    {'key': 'FFmpegMetadata', 'add_metadata': 'True'},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                ]
            }
        )
    else:
        old_dir = "./playlists_video.old"
        ext = "mp4"
        ytdl_download_args_final.update(
            {
                'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]',
                'postprocessors': [
                    {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'},
                    {'key': 'EmbedThumbnail'},
                    {'key': 'FFmpegMetadata'},
                ],
            }
        )

    os.makedirs(old_dir, exist_ok=True)

    for yt_pl_id in file_list:

        data = playlist_data.get(yt_pl_id)

        if not data:

            print(f"Obtendo informações da playlist: https://www.youtube.com/playlist?list={yt_pl_id}")

            with yt_dlp.YoutubeDL(
                    {
                        'extract_flat': True,
                        'quiet': True,
                        'no_warnings': True,
                        'lazy_playlist': True,
                        'simulate': True,
                        'skip_download': True,
                        'cookiefile': kwargs.get('cookie_file'),
                        'allowed_extractors': [
                            r'.*youtube.*',
                        ],
                    }
            ) as ydl:

                try:
                    data = ydl.extract_info(f"https://www.youtube.com/playlist?list={yt_pl_id}", download=False)
                except Exception:
                    traceback.print_exc()
                    continue

                playlist_data[yt_pl_id] = data

        playlist_name = sanitize_filename(data["title"])
        playlist_id = data["id"]

        print("\n" + "#"*(pn:=len(playlist_name) + 50) + "\n### Sincronizando playlist" + (" (Áudios)" if only_audio else " (Vídeos)")+ f":\n### {playlist_name} [ID: {playlist_id}]\n" + "#"*pn + "\n")

        # mover pastas que estão no padrão da versão anterior desse script.
        for dir_ in os.listdir(out_dir):

            if dir_.endswith(".m3u"):
                if playlist_id in dir_ and os.path.isfile(f"{out_dir}/{dir_}"):
                    os.remove(f"{out_dir}/{dir_}")
                continue

            if not os.path.isdir(f"{out_dir}/{dir_}"):
                continue
            if playlist_id in dir_:
                os.makedirs(f"{out_dir}/.synced_playlist_data_{ext}/{playlist_id}", exist_ok=True)
                print(f"Movendo pasta: {dir_}\nPara  -> {out_dir}.synced_playlist_data_{ext}/{playlist_id}")
                move_dir(f"{out_dir}/{dir_}", f"{out_dir}/.synced_playlist_data_{ext}/{playlist_id}")
                break

        new_tracks = {
            t["id"]: {
                "name": t['title'],
                "duration": t["duration"],
                "uploader": t["uploader"],
            } for c, t in enumerate(data["entries"]) if not t["live_status"] and not t["live_status"]
        }

        playlist_dir = f"{out_dir}/.synced_playlist_data_{ext}/{playlist_id}"

        os.makedirs(playlist_dir, exist_ok=True)

        for f in os.listdir(playlist_dir):

            if not f.endswith(f".{ext}") or not os.path.isfile(f"{playlist_dir}/{f}"):
                continue

            try:
                yt_id = yt_video_regex.search(f.split(" - ")[-1]).group()
            except AttributeError:
                yt_id = None

            if not yt_id or not new_tracks.get(yt_id):
                os.makedirs(f"{old_dir}/{playlist_id}", exist_ok=True)
                shutil.move(f"{playlist_dir}/{f}", f"{old_dir}/{playlist_id}/{f}")
                continue

            if not yt_video_regex.match(f):
                try:
                    os.rename(f"{playlist_dir}/{f}", f"{playlist_dir}/{yt_id}.{ext}")
                except FileExistsError:
                    os.remove(f"{playlist_dir}/{f}")

        ytdl_args_list = []

        counter = 0

        for yt_id, track in new_tracks.items():

            if track['name'] == '[Deleted video]':
                print(f"Video deletado: https://www.youtube.com/watch?v={yt_id}")
                continue

            if track['name'] == '[Private video]':
                print(f"Video privado: https://www.youtube.com/watch?v={yt_id}")
                continue

            counter += 1

            if os.path.isfile(f"{playlist_dir}/{yt_id}.{ext}"):
                m3u_data[counter] = (f"#EXTINF:{track['duration']},{track['name']} - Por: {track['uploader']}\n"
                                     f"./.synced_playlist_data_{ext}/{playlist_id}/{yt_id}.{ext}")
                save_m3u(f"{out_dir}/{sanitize_filename(playlist_name)} - {playlist_id}.m3u")
                continue

            new_args = deepcopy(ytdl_download_args_final)

            ytdl_args_list.append([new_tracks[yt_id]["name"], yt_id, new_args, playlist_dir, out_dir, counter, ext, playlist_name, playlist_id])

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(download_video, *args) for args in ytdl_args_list]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        m3u_data.clear()

        time.sleep(10)

    try:
        os.remove("cookies.temp")
    except FileNotFoundError:
        pass

def download_video(name: str, yt_id: str, args, playlist_dir: str, out_dir: str, index: int, ext: str,
                   playlist_name: str, playlist_id: str):
    logging.info(f"Baixando: [{yt_id}] -> {name}")

    filepath = None

    try:
        with yt_dlp.YoutubeDL(args) as ytdl:
            r = ytdl.extract_info(url=f"https://www.youtube.com/watch?v={yt_id}")
            filepath = r['requested_downloads'][0]['filepath']
            m3u_data[index] = (f"#EXTINF:{r['duration']},{r['title']} - Por: {r['uploader']}\n"
                                 f"./.synced_playlist_data_{ext}/{playlist_id}/{yt_id}.{ext}")
    except Exception as e:
        logging.info(f"Erro ao baixar: [{yt_id}] -> {name} | {repr(e)}")

    time.sleep(3)

    if filepath:
        try:
            shutil.move(filepath, f"{playlist_dir}/{os.path.basename(filepath)}")
            save_m3u(f"{out_dir}/{sanitize_filename(playlist_name)} - {playlist_id}.m3u")
        except FileNotFoundError:
            pass

if __name__ == '__main__':
    run()
