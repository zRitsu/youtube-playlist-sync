import os
import re
import shutil
import traceback

import yt_dlp

from ffmpeg_check import check_ffmpeg_command, check_ffmpeg

yt_playlist_regex = re.compile(r'(https?://)?(www\.)?(youtube\.com|music\.youtube\.com)/.*list=([a-zA-Z0-9_-]+)')

ytdl_download_args = {
    'format': 'bestaudio',
    'ignoreerrors': True,
    'quiet': True,
    'retries': 30,
    'writethumbnail': True,
    'extractor_args': {
        'youtube': {
            'skip': [
                'hls',
                'dash'
            ],
        },
        'youtubetab': ['webpage']
    },
    'extract_flat': False,
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
            playlists = set([p for p in f.read().replace(" ", "\n").split("\n") if p])
    except FileNotFoundError:
        with open("playlists.txt", "w") as f:
            f.write("")
        print("Abra o arquivo playlists.txt e cole os links das suas playlists do youtube (apenas playlists públicas ou com visibilidade desativada, não há suporte para playlists privadas no momento).")
        return

    if not check_ffmpeg_command():
        ytdl_download_args["ffmpeg_location"] = check_ffmpeg()

    if not os.path.isdir("./playlists"):
        os.makedirs("./playlists")

    if not os.path.isdir("./playlists.old"):
        os.makedirs("./playlists.old")

    with yt_dlp.YoutubeDL(
                {
                    'extract_flat': True,
                    'quiet': True,
                    'no_warnings': True,
                    'lazy_playlist': True,
                    'simulate': True,
                    'allowed_extractors': [
                        r'.*youtube.*',
                    ],
                }
            ) as ydl:

        for url in playlists:

            if not yt_playlist_regex.match(url):
                print(f"Link de playlist inválido: {url}")
                continue

            try:
                data = ydl.extract_info(url, download=False)
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

            new_tracks = {t["id"]: f"{c+1:0{tnd}d}) {sanitize_filename(t['title'])} - {t['id']}" for c, t in enumerate(data["entries"])}

            if not selected_dir:
                os.makedirs(f"./playlists/{playlist_name} - {playlist_id}")
            else:
                for f in os.listdir(f"./playlists/{playlist_name} - {playlist_id}"):

                    if not f.endswith(".mp3"):

                        if f.endswith((".part", ".webm")):
                            try:
                                os.remove(f"./playlists/{playlist_name} - {playlist_id}/{f}")
                                os.remove(f"./playlists/{playlist_name} - {playlist_id}/{f[:-5]}.mp3")
                            except FileNotFoundError:
                                pass
                        else:
                            continue

                    filename = f[:-4].split(" - ")

                    yt_id = filename[-1]

                    name = " - ".join(a for a in filename[:-1]) + f" - {yt_id}"

                    if t:=new_tracks.get(yt_id):
                        del new_tracks[yt_id]
                        if t != name:
                            os.rename(f"./playlists/{playlist_name} - {playlist_id}/{f}",
                                      f"./playlists/{playlist_name} - {playlist_id}/{t}.mp3")

                    else:
                        if not os.path.isdir(f"./.playlists.old/{playlist_name} - {playlist_id}"):
                            os.makedirs(f"./.playlists.old/{playlist_name} - {playlist_id}")

                        shutil.move(f"./playlists/{playlist_name} - {playlist_id}/{f}",
                                      f"./playlists.old/{playlist_name} - {playlist_id}/{f}")

            for yt_id, track in new_tracks.items():
                ytdl_download_args['outtmpl'] = f'./playlists/{playlist_name} - {playlist_id}/{track}.%(ext)s'
                print(f"{playlist_name} -> Baixando: {new_tracks[yt_id]}")
                with yt_dlp.YoutubeDL(ytdl_download_args) as ytdl:
                    ytdl.extract_info(url=f"https://www.youtube.com/watch?v={yt_id}")

if __name__ == '__main__':
    run()
