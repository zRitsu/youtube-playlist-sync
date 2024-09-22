import json
import logging
import os
import re
import shutil
import time
import traceback
import concurrent.futures
from copy import deepcopy
from tempfile import gettempdir

from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from platformdirs import user_music_dir, user_videos_dir
from send2trash import send2trash
import yt_dlp

from ffmpeg_check import check_ffmpeg_command, check_ffmpeg

logging.basicConfig(level=logging.INFO, format='%(message)s')

yt_playlist_regex = re.compile(r'(?<=list=)[a-zA-Z0-9_-]+')

yt_video_regex = re.compile(r'(?:^|(?<=\W))[-a-zA-Z0-9_]{11}(?:$|(?=\W))')

temp_dir = gettempdir()

ytdl_download_args = {
    'ignoreerrors': False,
    'logtostderr': False,
    'no_warnings': True,
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

error_messages = {
    "[Deleted video]": "Vídeo deletado",
    "[Private video]": "Vídeo privado"
}

playlist_data = {}

track_ids = set()

m3u_data = {}


def save_m3u(out_dir: str):
    with open(out_dir, 'w', encoding="utf-8") as f:
        f.write("\n\n".join(m3u_data.values()))


def make_dirs(dst: str):
    if os.path.isfile(dst):
        os.remove(dst)

    try:
        os.makedirs(os.path.normcase(dst))
    except FileExistsError:
        pass


def move_dir(src: str, dst: str):
    make_dirs(dst)

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
        print("\n\nUsando cookies.txt para obter videos de playlists privadas.")
    except FileNotFoundError:
        cookie_file = None
        print("\n\nUso de cookies.txt ignorado (caso tenha adicionado link de alguma playlist privada da sua conta no "
              "arquivo playlists.txt ela será ignorada com erro de playlist inexistente).")

    if os.path.isfile("./playlists.txt"):
        os.rename("./playlists.txt", "./playlists_links_audio.txt")

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
            make_dirs(playlists_audio_directory)
            if not os.path.isdir(os.path.abspath(playlists_audio_directory)):
                raise Exception(f"O diretório não existe: {playlists_audio_directory}")
    except (IndexError, FileNotFoundError):
        playlists_audio_directory = user_music_dir() or "./playlists_audio"
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
            make_dirs(playist_video_directory)
            if not os.path.isdir(os.path.abspath(playist_video_directory)):
                raise Exception(f"O diretório não existe: {playist_video_directory}")
    except (IndexError, FileNotFoundError):
        playist_video_directory = user_videos_dir() or "./playlists_video"
        with open("./playists_video_directory.txt", "w") as f:
            f.write(playist_video_directory)

    if not playlists_audio and not playlists_video:
        print("\n\nAbra o arquivo playlists_links_audio.txt e cole os links das suas playlists do youtube (pra download de "
              "vídeos cole os links de playlists no playlists_links_video.txt).")
        return

    if os.path.isdir("./playlists"):
        print(f"\n\nMovendo músicas da pasta playlists para a pasta {playlists_audio_directory}")
        move_dir("./playlists", playlists_audio_directory)

    download_playlist(file_list=playlists_audio, out_dir=playlists_audio_directory, only_audio=True,
                      cookie_file=cookie_file)

    download_playlist(file_list=playlists_video, out_dir=playist_video_directory, only_audio=False,
                      cookie_file=cookie_file)


def download_playlist(file_list: list, out_dir: str, only_audio=True, **kwargs):
    make_dirs(out_dir)

    ytdl_download_args_final = deepcopy(ytdl_download_args)

    old_dir = os.path.join(out_dir, f"./.synced_playlist_data/deleted")

    if not os.path.isdir(old_dir):
        os.makedirs(old_dir)

    if only_audio:
        ext = "mp3"
        media_txt = "áudio"
        ytdl_download_args_final.update(
            {
                'format': 'bestaudio',
                'postprocessors': [
                    {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
                    {'key': 'FFmpegMetadata', 'add_metadata': 'True'},
                    {'key': 'EmbedThumbnail', 'already_have_thumbnail': False}
                ],
                'parse_metadata': 'title:%(playlist_index)s - %(title)s',
            }
        )
    else:
        ext = "mp4"
        media_txt = "vídeo"
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

    make_dirs(old_dir)

    make_dirs(f"{out_dir}/.synced_playlist_data/")

    for yt_pl_id in file_list:

        data = playlist_data.get(yt_pl_id)

        if not data:

            print(f"\n\nObtendo informações da playlist: https://www.youtube.com/playlist?list={yt_pl_id}")

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

        make_dirs(f"{out_dir}/.synced_playlist_data/")

        print("\n" + "#" * (pn := len(
            playlist_name) + 50) + f"\n### Sincronizando {media_txt}s da playlist:\n### {playlist_name} [ID: {playlist_id}]\n" + "#" * pn + "\n")

        for dir_ in os.listdir(out_dir):
            if dir_.endswith(".m3u"):
                if playlist_id in dir_ and os.path.isfile(f"{out_dir}/{dir_}"):
                    os.remove(f"{out_dir}/{dir_}")

        new_tracks = {
            t["id"]: {
                "name": t['title'],
                "duration": t["duration"],
                "uploader": t["uploader"],
            } for c, t in enumerate(data["entries"]) if not t["live_status"] and not t["live_status"]
        }

        synced_dir = f"{out_dir}/.synced_playlist_data/{playlist_id}"

        make_dirs(f"{synced_dir}/")

        unkown_files = 0

        for f in os.listdir(synced_dir):

            if not f.endswith(f".{ext}") or not os.path.isfile(f"{synced_dir}/{f}"):
                continue

            try:
                yt_id = yt_video_regex.search(f.split(" - ")[-1]).group()
            except AttributeError:
                yt_id = None

            if not yt_id:
                make_dirs(f"{out_dir}/.arquivos_desconhecidos")
                shutil.move(f"{synced_dir}/{f}", f"{out_dir}/.arquivos_desconhecidos/{f}")
                unkown_files += 1
                continue

        if unkown_files > 1:
            print(f"\n\n{unkown_files} arquivo{(s := 's'[:unkown_files ^ 1])} fo{'ram'[:unkown_files ^ 1] or 'i'} "
                  f"movido{s} pra pasta {out_dir}/.arquivos_desconhecidos")

        ytdl_args_list = []

        index = 0
        counter = 0
        existing = 0

        total_entries = len(new_tracks)

        save_data = deepcopy(data)

        del save_data["entries"]

        with open(f"{synced_dir}/playlist_info.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(save_data, indent=4))

        for yt_id, track in new_tracks.items():

            track_ids.add(yt_id)

            if e_message := error_messages.get(track['name']):
                total_entries -= 1
                try:
                    deleted_file = [p for p in [f"{old_dir}/{yt_id}.{ext}", f"{synced_dir}/{yt_id}.{ext}"] if os.path.isfile(p)][0]
                except IndexError:
                    print(f"{e_message}: https://www.youtube.com/watch?v={yt_id}")
                else:
                    existing += 1
                    audio_tag = MP3(deleted_file, ID3=EasyID3)
                    m3u_data[index] = (f"#EXTINF:{int(audio_tag.info.length)},[{e_message}]: {audio_tag['title'][0]} - "
                                       f"Por: {audio_tag['artist'][0]}\n"
                                       f"{old_dir}/{yt_id}.{ext}")
                    print(f"{e_message} (reaproveitado): https://www.youtube.com/watch?v={yt_id}")
                continue

            index += 1

            print(f"{out_dir}/{yt_id}.{ext}")

            if (move:=os.path.isfile(f"{out_dir}/.synced_playlist_data/{yt_id}.{ext}")) or os.path.isfile(f"{synced_dir}/{yt_id}.{ext}"):
                total_entries -= 1
                existing += 1
                m3u_data[index] = (f"#EXTINF:{track['duration']},{track['name']} - Por: {track['uploader']}\n"
                                   f"./.synced_playlist_data/{playlist_id}/{yt_id}.{ext}")
                if move:
                    shutil.move(f"{out_dir}/.synced_playlist_data/{yt_id}.{ext}", f"{synced_dir}/{yt_id}.{ext}")
                continue

            new_args = deepcopy(ytdl_download_args_final)

            counter += 1

            ytdl_args_list.append(
                [new_tracks[yt_id]["name"], counter, yt_id, new_args, synced_dir, out_dir, index, ext, playlist_name,
                 playlist_id])

        if existing > 0:
            save_m3u(f"{out_dir}/{sanitize_filename(playlist_name)} - {playlist_id}.m3u")
            print(f"{existing} download{'s'[:existing ^ 1]} de {media_txt}{'s'[:existing ^ 1]} "
                  f"existente{'s'[:existing ^ 1]} ignorado{'s'[:existing ^ 1]}.")

        if not ytdl_args_list:
            time.sleep(10)
        else:
            total_entries = len(ytdl_args_list)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(download_video, total_entries=total_entries, *args) for n, args in
                           enumerate(ytdl_args_list)]
                for future in concurrent.futures.as_completed(futures):
                    future.result()

        m3u_data.clear()

        if os.path.isdir(f"{synced_dir}/{playlist_id}"):

            removed_files = 0

            for f in os.listdir(f"{synced_dir}/{playlist_id}/.synced_playlist_data/"):
                if not f.endswith((".mp3", ".mp4")):
                    continue
                if f[:-4] not in track_ids:
                    send2trash(os.path.abspath(f"{synced_dir}/{playlist_id}/.synced_playlist_data/{f}"))
                    removed_files += 1

            if removed_files > 1:
                print(f"\n\n{removed_files} arquivo{(s := 's'[:removed_files ^ 1])} que não estão em suas playlists "
                      f"fo{'ram'[:removed_files ^ 1] or 'i'} movido{s} para a lixeira")

    try:
        os.remove("cookies.temp")
    except FileNotFoundError:
        pass


def download_video(name: str, counter: int, yt_id: str, args, playlist_dir: str, out_dir: str, index: int, ext: str,
                   playlist_name: str, playlist_id: str, total_entries: int):
    logging.info(f"\n[{counter}/{total_entries}] Baixando: [{yt_id}] -> {name}")

    filepath = None

    try:
        with yt_dlp.YoutubeDL(args) as ytdl:
            r = ytdl.extract_info(url=f"https://www.youtube.com/watch?v={yt_id}")
            filepath = r['requested_downloads'][0]['filepath']
            m3u_data[index] = (f"#EXTINF:{r['duration']},{r['title']} - Por: {r['uploader']}\n"
                               f"./.synced_playlist_data/{yt_id}.{ext}")
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
