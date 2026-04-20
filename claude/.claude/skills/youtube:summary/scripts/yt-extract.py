#!/usr/bin/env python3
"""
YouTube 자막 + 메타데이터 추출 스크립트.
yt-dlp(Primary) + youtube_transcript_api(Fallback) 이중 전략으로 자막을 추출한다.
"""

import json
import re
import sys


def check_dependencies():
    """자막 추출 라이브러리 설치 여부 확인.

    Returns: (any_available: bool, has_ytdlp: bool, has_transcript_api: bool)
    """
    has_ytdlp = False
    has_transcript_api = False
    try:
        import yt_dlp  # noqa: F401
        has_ytdlp = True
    except ImportError:
        pass
    try:
        import youtube_transcript_api  # noqa: F401
        has_transcript_api = True
    except ImportError:
        pass
    return (has_ytdlp or has_transcript_api), has_ytdlp, has_transcript_api


def extract_video_id(url: str) -> str | None:
    """YouTube URL에서 video ID를 추출한다."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def format_duration(seconds: int) -> str:
    """초를 MM:SS 또는 H:MM:SS 형식으로 변환."""
    if seconds is None:
        return "unknown"
    h, remainder = divmod(int(seconds), 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def extract_transcript(entries: list) -> str:
    """자막 엔트리 리스트에서 텍스트만 추출하여 연결."""
    lines = []
    for entry in entries:
        text = entry.get("text", "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def extract_metadata_ytdlp(url: str) -> dict | None:
    """yt-dlp로 영상 메타데이터만 추출 (자막 없이)."""
    try:
        import yt_dlp
    except ImportError:
        return None

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if info is None:
            return None
        upload_date_raw = info.get("upload_date", "")
        if upload_date_raw and len(upload_date_raw) == 8:
            upload_date = f"{upload_date_raw[:4]}-{upload_date_raw[4:6]}-{upload_date_raw[6:]}"
        else:
            upload_date = upload_date_raw or "알 수 없음"
        return {
            "title": info.get("title", "제목 없음"),
            "channel": info.get("channel", info.get("uploader", "알 수 없음")),
            "duration": format_duration(info.get("duration")),
            "upload_date": upload_date,
        }
    except Exception as e:
        sys.stderr.write(f"warn: extract_metadata_ytdlp failed: {e}\n")
        return None


def extract_transcript_ytdlp(url: str) -> dict | None:
    """yt-dlp로 자막 추출 (Primary 방식)."""
    try:
        import yt_dlp
    except ImportError:
        return None

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["ko", "en"],
        "subtitlesformat": "json3",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        sys.stderr.write(f"warn: extract_transcript_ytdlp (extract_info) failed: {e}\n")
        return None

    if info is None:
        return None

    # 자막 추출 (우선순위: 수동 ko → 수동 en → 자동 ko → 자동 en)
    subtitles = info.get("subtitles", {}) or {}
    auto_subs = info.get("automatic_captions", {}) or {}

    subtitle_data = None
    language = None

    for lang, subs_dict, sub_type in [
        ("ko", subtitles, "manual"),
        ("en", subtitles, "manual"),
        ("ko", auto_subs, "auto"),
        ("en", auto_subs, "auto"),
    ]:
        if lang in subs_dict:
            formats = subs_dict[lang]
            json3_fmt = next((f for f in formats if f.get("ext") == "json3"), None)
            if json3_fmt:
                subtitle_data = json3_fmt
                language = f"{lang}" if sub_type == "manual" else f"{lang}(auto)"
                break
            elif formats:
                subtitle_data = formats[0]
                language = f"{lang}" if sub_type == "manual" else f"{lang}(auto)"
                break

    if subtitle_data is None:
        return None

    sub_url = subtitle_data.get("url")
    if not sub_url:
        return None

    try:
        import urllib.request
        with urllib.request.urlopen(sub_url, timeout=30) as response:
            sub_content = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"warn: subtitle download failed: {e}\n")
        return None

    events = sub_content.get("events", [])
    transcript_lines = []
    for event in events:
        segs = event.get("segs", [])
        text = "".join(seg.get("utf8", "") for seg in segs).strip()
        if text and text != "\n":
            transcript_lines.append(text)

    transcript = "\n".join(transcript_lines)
    if not transcript.strip():
        return None

    return {"transcript": transcript, "language": language}


def extract_transcript_api(video_id: str) -> dict | None:
    """youtube_transcript_api로 자막 추출 (Fallback 방식)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None

    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        # 우선순위: ko 수동 → en 수동 → ko 자동 → en 자동
        target = None
        for lang_code in ["ko", "en"]:
            for t in transcript_list:
                if t.language_code == lang_code and not t.is_generated:
                    target = t
                    break
            if target:
                break

        if target is None:
            for lang_code in ["ko", "en"]:
                for t in transcript_list:
                    if t.language_code == lang_code and t.is_generated:
                        target = t
                        break
                if target:
                    break

        if target is None:
            # 아무거나 첫 번째
            for t in transcript_list:
                target = t
                break

        if target is None:
            return None

        fetched = target.fetch()
        transcript = "\n".join([snippet.text for snippet in fetched])
        lang_suffix = "" if not target.is_generated else "(auto)"
        language = f"{target.language_code}{lang_suffix}"

        return {"transcript": transcript, "language": language}
    except Exception as e:
        sys.stderr.write(f"warn: extract_transcript_api failed: {e}\n")
        return None


def extract(url: str) -> dict:
    """YouTube URL에서 자막과 메타데이터를 추출한다.

    전략: yt-dlp(Primary) → youtube_transcript_api(Fallback)
    메타데이터는 yt-dlp로, 자막은 둘 중 성공하는 것을 사용한다.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return {"success": False, "error": "유효하지 않은 YouTube URL입니다"}

    # 1. 메타데이터 추출 (yt-dlp)
    metadata = extract_metadata_ytdlp(url)
    if metadata is None:
        metadata = {
            "title": "제목 없음",
            "channel": "알 수 없음",
            "duration": "unknown",
            "upload_date": "알 수 없음",
        }

    # 2. 자막 추출: yt-dlp 시도 → 실패 시 youtube_transcript_api fallback
    transcript_result = extract_transcript_ytdlp(url)
    method = "yt-dlp"

    if transcript_result is None:
        transcript_result = extract_transcript_api(video_id)
        method = "youtube_transcript_api"

    if transcript_result is None:
        return {"success": False, "error": "자막을 추출할 수 없습니다 (yt-dlp, youtube_transcript_api 모두 실패)"}

    return {
        "success": True,
        "title": metadata["title"],
        "channel": metadata["channel"],
        "duration": metadata["duration"],
        "upload_date": metadata["upload_date"],
        "url": url,
        "language": transcript_result["language"],
        "transcript": transcript_result["transcript"],
        "method": method,
    }


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"success": False, "error": "사용법: yt-extract.py extract <URL>"}, ensure_ascii=False))
        sys.exit(1)

    command = sys.argv[1]
    if command != "extract":
        print(json.dumps({"success": False, "error": f"알 수 없는 명령: {command}"}, ensure_ascii=False))
        sys.exit(1)

    any_available, has_ytdlp, _ = check_dependencies()
    if not any_available:
        print(json.dumps({
            "success": False,
            "error": "yt-dlp 또는 youtube_transcript_api가 설치되어 있지 않습니다. 'pip install yt-dlp'로 설치해주세요."
        }, ensure_ascii=False))
        sys.exit(1)

    url = sys.argv[2]
    result = extract(url)

    if not has_ytdlp and result.get("success"):
        result["metadata_warning"] = "yt-dlp 미설치로 메타데이터(제목/채널/길이/날짜)가 제한될 수 있습니다."

    # 결과를 /tmp/yt-extract-result.json에 저장
    output_path = "/tmp/yt-extract-result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
