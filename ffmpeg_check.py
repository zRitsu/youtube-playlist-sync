import os
import subprocess
import urllib.request
import zipfile


def check_ffmpeg_command():
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_ffmpeg():
    appdata_local = os.getenv('LOCALAPPDATA')
    ffmpeg_dir = os.path.join(appdata_local, 'ffmpeg')

    if not os.path.isdir(ffmpeg_dir) or not os.path.isfile(f"{ffmpeg_dir}/ffmpeg"):

        ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        zip_path = os.path.join(ffmpeg_dir, 'ffmpeg.zip')

        os.makedirs(ffmpeg_dir, exist_ok=True)

        print("Baixando o ffmpeg para AppData\\Local...")
        urllib.request.urlretrieve(ffmpeg_url, zip_path)

        print("Extraindo o ffmpeg...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_dir)

        os.remove(zip_path)
        ffmpeg_bin = os.path.join(ffmpeg_dir, 'ffmpeg-release-essentials', 'bin')

        os.environ["PATH"] += os.pathsep + ffmpeg_bin

        print(f"ffmpeg foi baixado e extraído para: {ffmpeg_bin}")

    return f"{ffmpeg_dir}/ffmpeg"
