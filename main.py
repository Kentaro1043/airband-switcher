import atexit
import os
import signal
import subprocess
import sys
import tempfile
import threading

from flask import Flask, jsonify, render_template, request, send_from_directory

from gr.airband_demodulator import airband_demodulator

# 一時ディレクトリ作成
temp_dir = tempfile.TemporaryDirectory()
atexit.register(temp_dir.cleanup)
print(f"Using temporary directory: {temp_dir.name}")

os.mkfifo(os.path.join(temp_dir.name, "audio.pcm"))
os.makedirs(os.path.join(temp_dir.name, "streaming"), exist_ok=True)

# Flaskセットアップ
app = Flask(__name__)

# グローバルでデモデュレータ参照とロックを保持（main()内で初期化）
demodulator = None
demodulator_lock = threading.Lock()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/streaming/<path:filename>")
def streaming_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".m3u8":
        mime_type = "application/vnd.apple.mpegurl"
    elif ext == ".ts":
        mime_type = "video/mp2t"
    else:
        mime_type = None

    response = send_from_directory(
        os.path.join(temp_dir.name, "streaming"),
        filename,
        mimetype=mime_type,
        as_attachment=False,
        conditional=True,
    )
    response.headers.setdefault("Content-Disposition", f'inline; filename="{filename}"')
    response.headers.setdefault("Accept-Ranges", "bytes")
    if ext == ".m3u8":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@app.route("/api/freq", methods=["POST"])
def api_set_freq():
    """
    JSON body expected: {"freq_hz": 128800000}
    """
    data = request.get_json(silent=True)
    if not data or "freq_hz" not in data:
        return jsonify({"error": "missing freq_hz"}), 400
    try:
        freq_hz = float(data["freq_hz"])
    except (ValueError, TypeError):
        return jsonify({"error": "invalid freq_hz"}), 400

    with demodulator_lock:
        if demodulator is None:
            return jsonify({"error": "demodulator not ready"}), 503
        try:
            demodulator.set_freq(freq_hz)
        except Exception as e:
            return jsonify({"error": "failed to set frequency", "details": str(e)}), 500

    return jsonify({"status": "ok", "freq_hz": freq_hz}), 200


def main():
    # Start ffmpeg in background to convert ./tmp/audio.pcm to HLS segments
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
        "1",
        "-hls_list_size",
        "3",
        "-hls_flags",
        "delete_segments+append_list",
        "-hls_segment_filename",
        os.path.join(temp_dir.name, "streaming", "segment_%03d.ts"),
        os.path.join(temp_dir.name, "streaming", "playlist.m3u8"),
    ]

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

    global demodulator
    demodulator = airband_demodulator()

    demodulator.set_output_path(os.path.join(temp_dir.name, "audio.pcm"))

    def sig_handler(sig, frame):
        # stop demodulator
        try:
            demodulator.stop()
            demodulator.wait()
        except Exception:
            pass

        # terminate ffmpeg if running
        if ffmpeg_proc and ffmpeg_proc.poll() is None:
            try:
                ffmpeg_proc.terminate()
                ffmpeg_proc.wait(timeout=5)
            except Exception:
                try:
                    ffmpeg_proc.kill()
                except Exception:
                    pass

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    demodulator.start()
    demodulator.flowgraph_started.set()

    # Run Flask in a background thread so demodulator.wait() doesn't block server startup.
    flask_thread = threading.Thread(
        target=app.run,
        kwargs={"debug": True, "use_reloader": False, "host": "0.0.0.0", "port": 8080},
        daemon=True,
    )
    flask_thread.start()

    # Wait for demodulator to finish (main thread remains responsive to signals)
    demodulator.wait()

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
