import os
import shutil
import subprocess
import urllib.request
import zipfile


def check_ffmpeg_command(ffmpeg_cmd="ffmpeg", raise_exception=False):
    try:
        subprocess.run([ffmpeg_cmd, '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        if raise_exception:
            raise e
        return False


def check_ffmpeg():
    appdata_local = os.getenv('LOCALAPPDATA')
    ffmpeg_dir = os.path.normpath(os.path.join(appdata_local, 'ffmpeg'))

    if not os.path.isdir(ffmpeg_dir) or not os.path.isfile(f"{ffmpeg_dir}/ffmpeg.exe"):

        ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        zip_path = os.path.join(ffmpeg_dir, 'ffmpeg.zip')

        os.makedirs(ffmpeg_dir, exist_ok=True)

        print(f"Baixando o ffmpeg no diretório: {os.path.normpath(ffmpeg_dir)}")
        urllib.request.urlretrieve(ffmpeg_url, zip_path)

        print("Extraindo o ffmpeg...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_dir)

        os.remove(zip_path)

        for d in os.listdir(ffmpeg_dir):
            if os.path.isdir(f"{ffmpeg_dir}/{d}"):
                if os.path.isdir(f"{ffmpeg_dir}/{d}/bin"):
                    for f in os.listdir(f"{ffmpeg_dir}/{d}/bin"):
                        try:
                            shutil.move(f"{ffmpeg_dir}/{d}/bin/{f}", ffmpeg_dir)
                        except:
                            continue
                shutil.rmtree(f"{ffmpeg_dir}/{d}")

        os.environ["PATH"] += os.pathsep + ffmpeg_dir

        print(f"ffmpeg foi baixado e extraído para: {ffmpeg_dir}")

    return f"{ffmpeg_dir}/ffmpeg.exe"
