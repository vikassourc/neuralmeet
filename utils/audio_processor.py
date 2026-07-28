import os
import shutil

import yt_dlp
from pydub import AudioSegment

DOWNLOAD_DIR = 'downloades'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# FFmpeg installed via winget — point tools directly to the binary folder
FFMPEG_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin"
)


def find_ffmpeg():
    candidates = []
    if os.path.isdir(FFMPEG_DIR):
        candidates.append(FFMPEG_DIR)

    system_ffmpeg = shutil.which("ffmpeg")
    system_ffprobe = shutil.which("ffprobe")
    if system_ffmpeg and system_ffprobe:
        candidates.append(os.path.dirname(system_ffmpeg))

    for folder in candidates:
        ffmpeg_bin = os.path.join(folder, "ffmpeg.exe") if os.name == "nt" else os.path.join(folder, "ffmpeg")
        ffprobe_bin = os.path.join(folder, "ffprobe.exe") if os.name == "nt" else os.path.join(folder, "ffprobe")
        if os.path.isfile(ffmpeg_bin) and os.path.isfile(ffprobe_bin):
            return ffmpeg_bin, ffprobe_bin

    return None, None


FFMPEG_BIN, FFPROBE_BIN = find_ffmpeg()
if FFMPEG_BIN and FFPROBE_BIN:
    AudioSegment.converter = FFMPEG_BIN
    AudioSegment.ffprobe = FFPROBE_BIN
    os.environ["PATH"] = os.path.dirname(FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", "")
else:
    print("Warning: FFmpeg is not installed or not found in PATH. Audio conversion may fail.")

def download_youtube_audio(url: str) -> str:
    # Strip playlist params so we only download the single video
    import urllib.parse as _urlparse
    parsed = _urlparse.urlparse(url)
    params = _urlparse.parse_qs(parsed.query)
    clean_params = {k: v for k, v in params.items() if k in ("v",)}
    clean_url = _urlparse.urlunparse(parsed._replace(query=_urlparse.urlencode(clean_params, doseq=True)))
    if not clean_params:
        clean_url = url  # fallback if no ?v= param (e.g. short URLs)

    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "noplaylist": True,       # never download entire playlists
        "retries": 5,             # retry on network errors
        "quiet": True,
        "no_warnings": True,      # suppress JS runtime warnings
    }
    if FFMPEG_BIN:
        ydl_opts["ffmpeg_location"] = os.path.dirname(FFMPEG_BIN)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(clean_url, download=True)
        # handle playlist info dict vs single video
        if "entries" in info:
            info = info["entries"][0]
        filename = ydl.prepare_filename(info).replace(".webm", ".wav").replace(".m4a", ".wav")
    return filename



def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV format using pydub."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000) #16khz
    audio.export(output_path, format="wav")
    return output_path



def chunk_audio(wav_path : str , chunk_minutes : int = 10) -> list:
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000 

    chunks = []

    for i, start in enumerate(range(0,len(audio),chunk_ms)):
        chunk = audio[start : start + chunk_ms]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path , format = "wav")

        chunks.append(chunk_path)
    
    return chunks

def process_input(source: str) -> list:
    if source.startswith("http://") or source.startswith("https://"):
        print("Detected YouTube URL. Downloading audio...")
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks

