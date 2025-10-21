import atexit
import os
import signal
import subprocess
import sys
import tempfile

from gr.airband_demodulator import airband_demodulator

# 一時ディレクトリを作成
temp_dir = tempfile.TemporaryDirectory()
atexit.register(temp_dir.cleanup)
print(f"Using temporary directory: {temp_dir.name}")

os.mkfifo(os.path.join(temp_dir.name, "audio.pcm"))
os.makedirs(os.path.join(temp_dir.name, "streaming"), exist_ok=True)

# 復調モジュール
demodulator = airband_demodulator()
demodulator.set_output_path(os.path.join(temp_dir.name, "audio.pcm"))


# シグナルハンドラ
def sig_handler(sig, frame):
    # stop demodulator
    try:
        demodulator.stop()
        demodulator.wait()
    except Exception:
        pass
    sys.exit(0)


# シグナルハンドラを登録
signal.signal(signal.SIGINT, sig_handler)
signal.signal(signal.SIGTERM, sig_handler)


def main():
    # ffmpegコマンドを構築
    ffmpeg_cmd = [
        "ffmpeg",
        "-f",
        "s16le",
        "-ar",
        "48000",
        "-ac",
        "1",
        "-re",
        "-i",
        os.path.join(temp_dir.name, "audio.pcm"),
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-ac",
        "1",
        "-ar",
        "48000",
        "-f",
        "hls",
        "-hls_time",
        "6",
        "-hls_list_size",
        "6",
        "-hls_flags",
        "delete_segments+append_list",
        "-hls_segment_filename",
        os.path.join(temp_dir.name, "streaming", "segment_%03d.ts"),
        os.path.join(temp_dir.name, "streaming", "playlist.m3u8"),
    ]

    # ffmpegプロセスを開始
    try:
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print(
            "エラー: ffmpegが見つかりません。",
            file=sys.stderr,
        )
        ffmpeg_proc = None

    # 復調モジュールを開始
    demodulator.start()
    demodulator.flowgraph_started.set()
    demodulator.wait()

    # ffmpegプロセスを終了
    if ffmpeg_proc and ffmpeg_proc.poll() is None:
        try:
            ffmpeg_proc.terminate()
            ffmpeg_proc.wait(timeout=1)
        except Exception:
            try:
                ffmpeg_proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    main()
