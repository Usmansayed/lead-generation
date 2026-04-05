"""
Media download for social media posts: video, audio, thumbnail, images.
Uses yt-dlp for multi-platform support. Writes to a structured job directory.
"""
from __future__ import annotations

import os
from pathlib import Path

from .models import DownloadError
from .utils import get_logger

logger = get_logger()

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore[assignment]

# Standard filenames in job output directory
VIDEO_FILENAME = "video"
AUDIO_FILENAME = "audio"
THUMBNAIL_FILENAME = "thumbnail"
# Extensions chosen by yt-dlp or post-processor
VIDEO_EXT = ".mp4"
AUDIO_EXT = ".wav"
THUMB_EXT = ".jpg"


def download_media(
    url: str,
    output_dir: str,
    *,
    download_video: bool = True,
    download_audio: bool = True,
    download_thumbnail: bool = True,
    video_filename: str = VIDEO_FILENAME,
    audio_filename: str = AUDIO_FILENAME,
    thumbnail_filename: str = THUMBNAIL_FILENAME,
    cookies_file: str | None = None,
) -> dict[str, str | None]:
    """
    Download all available media for a post into output_dir.

    Args:
        url: Post URL.
        output_dir: Directory to write files (e.g. media/{job_id}).
        download_video: Whether to download video.
        download_audio: Whether to extract audio (from video) to WAV.
        download_thumbnail: Whether to download thumbnail.
        video_filename: Base name for video file (no extension).
        audio_filename: Base name for audio file (no extension).
        thumbnail_filename: Base name for thumbnail (no extension).
        cookies_file: Optional path to Netscape-format cookies for auth-required platforms.

    Returns:
        Dict with keys: "video_path", "audio_path", "thumbnail_path", "image_paths".
        Paths are absolute; missing files are None. "image_paths" is a comma-separated
        string of paths for multiple images (e.g. carousel), or None.

    Raises:
        DownloadError: If yt-dlp is not installed or download fails.
    """
    if yt_dlp is None:
        raise DownloadError(
            "yt-dlp is not installed. Install with: pip install yt-dlp",
            url=url,
        )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    out_dir_str = str(out.resolve())

    result = {
        "video_path": None,
        "audio_path": None,
        "thumbnail_path": None,
        "image_paths": None,
    }

    # Single template: we'll use one format and then rename to fixed names
    video_path = out / f"{video_filename}{VIDEO_EXT}"
    audio_path = out / f"{audio_filename}{AUDIO_EXT}"
    thumbnail_path = out / f"{thumbnail_filename}{THUMB_EXT}"

    opts = {
        "outtmpl": os.path.join(out_dir_str, f"{video_filename}.%(ext)s"),
        "quiet": False,
        "no_warnings": True,
    }
    if cookies_file and Path(cookies_file).exists():
        opts["cookiefile"] = cookies_file

    if download_video:
        # Prefer best single-file format (video+audio) or best video
        opts["format"] = "best[ext=mp4]/best/bestvideo+bestaudio/best"
        opts["merge_output_format"] = "mp4"
    else:
        opts["skip_download"] = True

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=download_video)
    except Exception as e:
        logger.exception("Download failed for url=%s", url)
        raise DownloadError(f"Media download failed: {e}", url=url)

    if not info:
        raise DownloadError("No media info returned for URL", url=url)

    # Video path: yt-dlp writes to outtmpl (e.g. video.mp4 or video.mkv)
    if download_video:
        for ext in (VIDEO_EXT, ".mkv", ".webm", ".mov"):
            candidate = out / f"{video_filename}{ext}"
            if candidate.exists():
                if ext != VIDEO_EXT:
                    try:
                        if video_path.exists():
                            video_path.unlink()
                        candidate.rename(video_path)
                    except Exception as ex:
                        logger.warning("Could not rename to .mp4: %s", ex)
                        result["video_path"] = str(candidate.resolve())
                else:
                    result["video_path"] = str(video_path.resolve())
                if not result["video_path"]:
                    result["video_path"] = str(candidate.resolve())
                logger.info("Video saved to %s", result["video_path"])
                break
        if not result["video_path"] and info.get("requested_downloads"):
            for d in info["requested_downloads"]:
                p = d.get("filepath") or d.get("filename")
                if p and os.path.isfile(p):
                    result["video_path"] = os.path.abspath(p)
                    logger.info("Video saved to %s", result["video_path"])
                    break

    # Thumbnail: yt-dlp often downloads to a temp name; we prefer writing thumbnail ourselves
    thumb_url = info.get("thumbnail")
    if download_thumbnail and thumb_url:
        try:
            import urllib.request
            req = urllib.request.Request(thumb_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                thumbnail_path.write_bytes(resp.read())
            result["thumbnail_path"] = str(thumbnail_path.resolve())
            logger.info("Thumbnail saved to %s", result["thumbnail_path"])
        except Exception as ex:
            logger.warning("Thumbnail download failed: %s", ex)
    # If yt-dlp wrote a thumbnail to temp path, use it
    if not result["thumbnail_path"] and info.get("requested_thumbnail"):
        tp = info.get("requested_thumbnail")
        if tp and os.path.isfile(tp):
            try:
                Path(tp).rename(thumbnail_path)
                result["thumbnail_path"] = str(thumbnail_path.resolve())
            except Exception:
                result["thumbnail_path"] = tp

    # Extract audio from video if we have video and requested audio
    if download_audio and result.get("video_path") and Path(result["video_path"]).exists():
        try:
            import subprocess
            cmd = [
                "ffmpeg", "-y", "-i", result["video_path"],
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(audio_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
            result["audio_path"] = str(audio_path.resolve())
            logger.info("Audio extracted to %s", result["audio_path"])
        except FileNotFoundError:
            logger.warning("ffmpeg not found; skipping audio extraction")
        except subprocess.CalledProcessError as e:
            logger.warning("ffmpeg audio extraction failed: %s", e)
        except Exception as e:
            logger.warning("Audio extraction failed: %s", e)

    # Multiple images (e.g. Instagram carousel): yt-dlp may download as separate files
    image_paths = []
    if info.get("requested_downloads"):
        for d in info["requested_downloads"]:
            p = d.get("filepath") or d.get("filename")
            if p and p != result.get("video_path"):
                ext = (Path(p).suffix or "").lower()
                if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                    image_paths.append(p)
    if image_paths:
        result["image_paths"] = ",".join(image_paths)

    return result
