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

temp_dir = gettempdir()

ytdl_download_args = {
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'retries': 30,
    'extract_flat': False,
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
        shutil.move("./playlists.old", "./playlists_audio.old")

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
        for f in os.listdir("./playlists"):
            shutil.move(f"./playlists/{f}", f"{playlists_audio_directory}/{f}")
        shutil.rmtree("./playlists")

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

        selected_dir = None

        for dir_ in os.listdir(out_dir):

            if not os.path.isdir(f"{out_dir}/{dir_}"):
                continue

            if not dir_.endswith(playlist_id):
                continue

            if (current_name := " - ".join(a for a in dir_.split(" - ")[:-1]) + f" - {playlist_id}") != f"{playlist_name} - {playlist_id}":
                print(f"Renomeando pasta: {current_name} -> {playlist_name} - {playlist_id}")
                os.rename(f"{out_dir}/{current_name}", f"{out_dir}/{playlist_name} - {playlist_id}")
            selected_dir = True
            break

        tnd = len(str(len(data["entries"])))

        new_tracks = {
            t["id"]: {
                "filename": f"{c+1:0{tnd}d}) {sanitize_filename(t['title'])} - {t['id']}",
                "name": f"{t['title']}",
            } for c, t in enumerate(data["entries"]) if not t["live_status"] and not t["live_status"]
        }

        if not selected_dir:
            os.makedirs(f"{out_dir}/{playlist_name} - {playlist_id}")
        else:

            for f in os.listdir(f"{out_dir}/{playlist_name} - {playlist_id}"):

                if not f.endswith(f".{ext}"):
                    continue

                filename = f[:-4].split(" - ")

                yt_id = filename[-1]

                name = " - ".join(a for a in filename[:-1]) + f" - {yt_id}"

                if t:=new_tracks.get(yt_id):
                    del new_tracks[yt_id]
                    if t != name:
                        os.rename(f"{out_dir}/{playlist_name} - {playlist_id}/{f}",
                                  f"{out_dir}/{playlist_name} - {playlist_id}/{t['filename']}.{ext}")

                else:

                    if f.endswith(f".{ext}"):
                        os.makedirs(f"{old_dir}/{playlist_name} - {playlist_id}", exist_ok=True)
                        shutil.move(f"{out_dir}/{playlist_name} - {playlist_id}/{f}",
                                  f"{old_dir}/{playlist_name} - {playlist_id}/{f}")

        ytdl_args_list = []

        for yt_id, track in new_tracks.items():

            if track['name'] == '[Deleted video]':
                print(f"Video deletado: https://www.youtube.com/watch?v={yt_id}")
                continue

            if track['name'] == '[Private video]':
                print(f"Video privado: https://www.youtube.com/watch?v={yt_id}")
                continue

            new_args = deepcopy(ytdl_download_args_final)

            new_args['outtmpl'] = os.path.join(temp_dir, f"{track['filename']}") + '.%(ext)s'

            ytdl_args_list.append([new_tracks[yt_id]["name"], yt_id, new_args, f"{out_dir}/{playlist_name} - {playlist_id}"])

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(download_video, *args) for args in ytdl_args_list]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        time.sleep(10)

    try:
        os.remove("cookies.temp")
    except FileNotFoundError:
        pass

def download_video(name: str, yt_id: str, args, final_dir: str):
    logging.info(f"Baixando: [{yt_id}] -> {name}")

    filepath = None

    try:
        with yt_dlp.YoutubeDL(args) as ytdl:
            r = ytdl.extract_info(url=f"https://www.youtube.com/watch?v={yt_id}")
            filepath = r['requested_downloads'][0]['filepath']
    except Exception as e:
        logging.info(f"Erro ao baixar: [{yt_id}] -> {name} | {repr(e)}")

    time.sleep(3)

    if filepath:
        try:
            shutil.move(filepath, f"{final_dir}/{os.path.basename(filepath)}")
        except FileNotFoundError:
            pass

if __name__ == '__main__':
    run()
