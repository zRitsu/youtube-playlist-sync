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
    'format': 'bestaudio',
    'ignoreerrors': True,
    'quiet': True,
    'retries': 30,
    'writethumbnail': True,
    'extract_flat': False,
    'extractor_args': {
        'youtube': {
            'skip': [
                'hls',
                'dash'
            ],
            'player_skip': [
                'js',
                'configs',
                'webpage'
            ]
        },
        'youtubetab': ['webpage']
    },
    'postprocessors': [
        {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
        {'key': 'FFmpegMetadata', 'add_metadata': 'True'},
        {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
    ],
}

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '-', filename).rstrip('. ')

def run():

    try:
        with open("playlists.txt") as f:
            playlists = sorted(list(set([p for p in yt_playlist_regex.findall(f.read())])))
    except FileNotFoundError:
        with open("playlists.txt", "w") as f:
            f.write("")
        print("Abra o arquivo playlists.txt e cole os links das suas playlists do youtube (apenas playlists públicas "
              "ou com visibilidade desativada, não há suporte para playlists privadas no momento).")
        return

    if not check_ffmpeg_command():
        ytdl_download_args["ffmpeg_location"] = check_ffmpeg()
        check_ffmpeg_command(ytdl_download_args["ffmpeg_location"], raise_exception=True)

    os.makedirs("./playlists", exist_ok=True)
    os.makedirs("./playlists.old", exist_ok=True)

    try:
        shutil.copy("cookies.txt", "cookies.temp")
        cookie_file = "./cookies.temp"
        print("Usando cookies.txt para obter videos de playlists privadas.")
    except FileNotFoundError:
        cookie_file = None
        print("Uso de cookies.txt ignorado (caso tenha adicionado link de alguma playlist privada da sua conta no "
              "arquivo playlists.txt ela será ignorada com erro de playlist inexistente).")

    with yt_dlp.YoutubeDL(
                {
                    'extract_flat': True,
                    'quiet': True,
                    'no_warnings': True,
                    'lazy_playlist': True,
                    'simulate': True,
                    'skip_download': True,
                    'cookiefile': cookie_file,
                    'allowed_extractors': [
                        r'.*youtube.*',
                    ],
                }
            ) as ydl:

        for yt_pl_id in playlists:

            try:
                data = ydl.extract_info(f"https://www.youtube.com/playlist?list={yt_pl_id}", download=False)
            except Exception:
                traceback.print_exc()
                continue

            playlist_name = sanitize_filename(data["title"])
            playlist_id = data["id"]

            print("\n" + "#"*(pn:=len(playlist_name) + 50) + f"\n### Sincronizando playlist:\n### {playlist_name} [ID: {playlist_id}]\n" + "#"*pn + "\n")

            selected_dir = None

            for dir_ in os.listdir("./playlists"):

                if not os.path.isdir(f"./playlists/{dir_}"):
                    continue

                if not dir_.endswith(playlist_id):
                    continue

                if (current_name := " - ".join(a for a in dir_.split(" - ")[:-1]) + f" - {playlist_id}") != f"{playlist_name} - {playlist_id}":
                    print(f"Renomeando pasta: {current_name} -> {playlist_name} - {playlist_id}")
                    os.rename(f"./playlists/{current_name}", f"./playlists/{playlist_name} - {playlist_id}")
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
                os.makedirs(f"./playlists/{playlist_name} - {playlist_id}")
            else:

                for f in os.listdir(f"./playlists/{playlist_name} - {playlist_id}"):

                    if not f.endswith(".mp3"):
                        continue

                    filename = f[:-4].split(" - ")

                    yt_id = filename[-1]

                    name = " - ".join(a for a in filename[:-1]) + f" - {yt_id}"

                    if t:=new_tracks.get(yt_id):
                        del new_tracks[yt_id]
                        if t != name:
                            os.rename(f"./playlists/{playlist_name} - {playlist_id}/{f}",
                                      f"./playlists/{playlist_name} - {playlist_id}/{t['filename']}.mp3")

                    else:

                        if f.endswith(".mp3"):
                            os.makedirs(f"./playlists.old/{playlist_name} - {playlist_id}", exist_ok=True)
                            shutil.move(f"./playlists/{playlist_name} - {playlist_id}/{f}",
                                      f"./playlists.old/{playlist_name} - {playlist_id}/{f}")

            ytdl_args_list = []
            
            for yt_id, track in new_tracks.items():

                if track['name'] == '[Deleted video]':
                    print(f"Video deletado: https://www.youtube.com/watch?v={yt_id}")
                    continue

                if track['name'] == '[Private video]':
                    print(f"Video privado: https://www.youtube.com/watch?v={yt_id}")
                    continue

                new_args = deepcopy(ytdl_download_args)

                new_args['outtmpl'] = os.path.join(temp_dir, f"{track['filename']}") + '.%(ext)s'

                ytdl_args_list.append([new_tracks[yt_id]["name"], yt_id, new_args, f"./playlists/{playlist_name} - {playlist_id}"])

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
