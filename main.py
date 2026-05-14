import os
import re
import json
import time
import threading
from pathlib import Path
from queue import Queue, Empty
from typing import Optional
from urllib.parse import quote_plus

import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import (
    ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, APIC, ID3NoHeaderError
)

app = FastAPI()

MUSIC_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac"}

event_queue: Queue = Queue()
_processing = False
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Filename parsing + title cleaning
# ---------------------------------------------------------------------------

# Suffixes added by YouTube downloaders that break search queries
_JUNK_PATTERNS = [
    r"[\(\[]\s*official\s*(music\s*)?(video|audio|lyric\s*video|visualizer|clip|mv)\s*[\)\]]",
    r"[\(\[]\s*(video|audio)\s+oficial\s*[\)\]]",
    r"[\(\[]\s*oficial\s*[\)\]]",
    r"[\(\[]\s*lyric[s]?\s*(video)?\s*[\)\]]",
    r"[\(\[]\s*letra[s]?\s*(oficial)?\s*[\)\]]",
    r"[\(\[]\s*live(\s+at\s+[^\)\]]+)?\s*[\)\]]",
    r"\s+[_\|]\s+live\s+from\s+.+",
    r"\s+-\s+live\s+at\s+.+",
    r"[\(\[]\s*(hd|hq|4k|1080p|720p|480p)\s*[\)\]]",
    r"[\(\[]\s*(explicit|clean|censored|radio\s*edit)\s*[\)\]]",
    r"[\(\[]\s*remaster(ed)?\s*(\d{4})?\s*[\)\]]",
    r"[\(\[]\s*\d{4}\s*remaster\s*[\)\]]",
    r"[\(\[]\s*f(ea)?t\.?\s+[^\)\]]+[\)\]]",
    r"\s+f(ea)?t\.?\s+.+$",
    r"[\(\[]\s*\d{4}\s*[\)\]]\s*$",
    r"[\(\[]\s*audio\s*[\)\]]",
]

def _clean_title(title: str) -> str:
    # First pass: remove known YouTube/download patterns
    for p in _JUNK_PATTERNS:
        title = re.sub(p, "", title, flags=re.IGNORECASE)
    # Second pass: remove ANY remaining trailing parenthetical/bracketed block
    # e.g. "Canción (En Vivo)", "Song [2023 Version]", "Track (Versión Acústica)"
    title = re.sub(r"\s*[\(\[][^\(\)\[\]]{1,60}[\)\]]\s*$", "", title).strip()
    # Third pass: repeat in case there were nested/multiple blocks
    title = re.sub(r"\s*[\(\[][^\(\)\[\]]{1,60}[\)\]]\s*$", "", title).strip()
    return title.strip(" -_|")


def parse_filename(stem: str) -> tuple[Optional[str], str]:
    stem = stem.strip()
    # Strip leading track numbers: "01 - ", "01.", "(01) "
    stem = re.sub(r"^[\(\[]?\d{1,3}[\)\]\.\-\s]+", "", stem).strip()
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return artist.strip(), title.strip()
    return None, stem


# ---------------------------------------------------------------------------
# iTunes Search API
# ---------------------------------------------------------------------------

_ITUNES_HEADERS = {"Accept-Language": "es-MX,es;q=0.9,en;q=0.8"}

def _itunes_search(artist: Optional[str], title: str) -> Optional[dict]:
    query = f"{artist} {title}" if artist else title
    url = (
        "https://itunes.apple.com/search"
        f"?term={quote_plus(query)}&media=music&entity=song&limit=5"
    )
    try:
        r = requests.get(url, timeout=12, headers=_ITUNES_HEADERS)
        data = r.json()
        if data.get("resultCount", 0) > 0:
            return _normalize_itunes(data["results"][0], title, artist)
    except Exception:
        pass
    return None


def _normalize_itunes(result: dict, fallback_title: str, fallback_artist: Optional[str]) -> dict:
    artwork = result.get("artworkUrl100", "")
    if artwork:
        artwork = re.sub(r"\d+x\d+bb", "600x600bb", artwork)
    date = result.get("releaseDate", "")
    return {
        "title":        result.get("trackName", fallback_title),
        "artist":       result.get("artistName", fallback_artist or ""),
        "album":        result.get("collectionName", ""),
        "year":         date[:4] if date else "",
        "genre":        result.get("primaryGenreName", ""),
        "track_number": str(result.get("trackNumber", "")),
        "artwork_url":  artwork,
    }


# ---------------------------------------------------------------------------
# Deezer Search API  (no key required, great Latin/Spanish coverage)
# ---------------------------------------------------------------------------

def _deezer_search(artist: Optional[str], title: str) -> Optional[dict]:
    if artist:
        q = f'artist:"{artist}" track:"{title}"'
    else:
        q = f'track:"{title}"'
    try:
        r = requests.get(
            f"https://api.deezer.com/search?q={quote_plus(q)}&limit=5",
            timeout=12,
        )
        data = r.json()
        tracks = data.get("data", [])
        if not tracks:
            return None
        track = tracks[0]
        album_info = track.get("album", {})
        year, genre = "", ""
        album_id = album_info.get("id")
        if album_id:
            try:
                ar = requests.get(f"https://api.deezer.com/album/{album_id}", timeout=8)
                ad = ar.json()
                year = (ad.get("release_date") or "")[:4]
                genres = ad.get("genres", {}).get("data", [])
                if genres:
                    genre = genres[0].get("name", "")
            except Exception:
                pass
        artwork = (
            album_info.get("cover_xl")
            or album_info.get("cover_big")
            or album_info.get("cover_medium")
            or ""
        )
        return {
            "title":        track.get("title", title),
            "artist":       track.get("artist", {}).get("name", artist or ""),
            "album":        album_info.get("title", ""),
            "year":         year,
            "genre":        genre,
            "track_number": str(track.get("track_position", "")),
            "artwork_url":  artwork,
        }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# MusicBrainz (last resort — no key, rate-limited to ~1 req/s)
# ---------------------------------------------------------------------------

_MB_HEADERS = {"User-Agent": "MusicAutoTagger/1.0 (github.com/javieraguilar)"}

def _musicbrainz_search(artist: Optional[str], title: str) -> Optional[dict]:
    q = f'recording:"{title}"'
    if artist:
        q += f' AND artist:"{artist}"'
    try:
        r = requests.get(
            f"https://musicbrainz.org/ws/2/recording?query={quote_plus(q)}&limit=5&fmt=json",
            timeout=15,
            headers=_MB_HEADERS,
        )
        data = r.json()
        recordings = data.get("recordings", [])
        if not recordings:
            return None
        rec = recordings[0]
        releases = rec.get("releases", [])
        release = releases[0] if releases else {}
        credits = rec.get("artist-credit", [])
        artist_name = credits[0].get("artist", {}).get("name", artist or "") if credits else (artist or "")
        mbid = release.get("id", "")
        artwork = f"https://coverartarchive.org/release/{mbid}/front-250" if mbid else ""
        return {
            "title":        rec.get("title", title),
            "artist":       artist_name,
            "album":        release.get("title", ""),
            "year":         (release.get("date") or "")[:4],
            "genre":        "",
            "track_number": "",
            "artwork_url":  artwork,
        }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Search cascade
# ---------------------------------------------------------------------------

def lookup_metadata(artist: Optional[str], title: str) -> Optional[dict]:
    clean = _clean_title(title)

    # 1. iTunes: artist + cleaned title
    result = _itunes_search(artist, clean)
    if result:
        return result

    # 2. Deezer: artist + cleaned title
    result = _deezer_search(artist, clean)
    if result:
        return result

    # 3. iTunes: title only (drop artist — sometimes the artist name differs)
    if artist:
        result = _itunes_search(None, clean)
        if result:
            return result

    # 4. Deezer: title only
    if artist:
        result = _deezer_search(None, clean)
        if result:
            return result

    # 5. iTunes: original title (uncleaned) in case cleaning removed something useful
    if clean != title:
        result = _itunes_search(artist, title)
        if result:
            return result

    # 6. MusicBrainz: last resort
    result = _musicbrainz_search(artist, clean)
    if result:
        return result

    return None


def download_artwork(url: str) -> Optional[bytes]:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Tag writers
# ---------------------------------------------------------------------------

def _write_mp3(path: str, meta: dict, art: Optional[bytes]) -> None:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    if meta.get("title"):
        tags["TIT2"] = TIT2(encoding=3, text=meta["title"])
    if meta.get("artist"):
        tags["TPE1"] = TPE1(encoding=3, text=meta["artist"])
    if meta.get("album"):
        tags["TALB"] = TALB(encoding=3, text=meta["album"])
    if meta.get("year"):
        tags["TDRC"] = TDRC(encoding=3, text=meta["year"])
    if meta.get("genre"):
        tags["TCON"] = TCON(encoding=3, text=meta["genre"])
    if meta.get("track_number"):
        tags["TRCK"] = TRCK(encoding=3, text=meta["track_number"])
    if art:
        tags["APIC"] = APIC(
            encoding=3, mime="image/jpeg", type=3, desc="Cover", data=art
        )
    tags.save(path)


def _write_flac(path: str, meta: dict, art: Optional[bytes]) -> None:
    audio = FLAC(path)
    mapping = {
        "title": "title",
        "artist": "artist",
        "album": "album",
        "year": "date",
        "genre": "genre",
        "track_number": "tracknumber",
    }
    for key, tag in mapping.items():
        if meta.get(key):
            audio[tag] = meta[key]
    if art:
        pic = Picture()
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.desc = "Cover"
        pic.data = art
        audio.clear_pictures()
        audio.add_picture(pic)
    audio.save()


def _write_m4a(path: str, meta: dict, art: Optional[bytes]) -> None:
    audio = MP4(path)
    if meta.get("title"):
        audio["\xa9nam"] = meta["title"]
    if meta.get("artist"):
        audio["\xa9ART"] = meta["artist"]
    if meta.get("album"):
        audio["\xa9alb"] = meta["album"]
    if meta.get("year"):
        audio["\xa9day"] = meta["year"]
    if meta.get("genre"):
        audio["\xa9gen"] = meta["genre"]
    tn = meta.get("track_number", "")
    if tn.isdigit():
        audio["trkn"] = [(int(tn), 0)]
    if art:
        audio["covr"] = [MP4Cover(art, imageformat=MP4Cover.FORMAT_JPEG)]
    audio.save()


def write_tags(filepath: Path, meta: dict, art: Optional[bytes]) -> None:
    ext = filepath.suffix.lower()
    if ext == ".mp3":
        _write_mp3(str(filepath), meta, art)
    elif ext == ".flac":
        _write_flac(str(filepath), meta, art)
    elif ext in (".m4a", ".aac"):
        _write_m4a(str(filepath), meta, art)


# ---------------------------------------------------------------------------
# Tag detection — skip already-tagged files
# ---------------------------------------------------------------------------

def is_tagged(filepath: Path) -> bool:
    """Return True if the file already has at least title + artist tags."""
    ext = filepath.suffix.lower()
    try:
        if ext == ".mp3":
            from mutagen.mp3 import MP3
            audio = MP3(str(filepath))
            tags = audio.tags
            if tags is None:
                return False
            return bool(tags.get("TIT2")) and bool(tags.get("TPE1"))
        elif ext == ".flac":
            audio = FLAC(str(filepath))
            return bool(audio.get("title")) and bool(audio.get("artist"))
        elif ext in (".m4a", ".aac"):
            audio = MP4(str(filepath))
            return bool(audio.get("\xa9nam")) and bool(audio.get("\xa9ART"))
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Background processing thread
# ---------------------------------------------------------------------------

def _process_folder(folder_path: str) -> None:
    global _processing
    folder = Path(folder_path)

    all_files = sorted(
        [f for f in folder.rglob("*") if f.suffix.lower() in MUSIC_EXTENSIONS]
    )
    files = [f for f in all_files if not is_tagged(f)]
    skipped = len(all_files) - len(files)

    event_queue.put(json.dumps({
        "type": "start",
        "total": len(files),
        "skipped": skipped,
    }))

    success = 0
    errors = 0

    for idx, filepath in enumerate(files, start=1):
        artist, title = parse_filename(filepath.stem)
        event_queue.put(
            json.dumps({
                "type": "processing",
                "index": idx,
                "total": len(files),
                "file": filepath.name,
            })
        )

        meta = lookup_metadata(artist, title)
        if meta is None:
            errors += 1
            event_queue.put(
                json.dumps({
                    "type": "result",
                    "index": idx,
                    "total": len(files),
                    "file": filepath.name,
                    "status": "error",
                    "message": "No se encontraron resultados",
                })
            )
            time.sleep(0.4)
            continue

        art = download_artwork(meta.get("artwork_url", ""))

        try:
            write_tags(filepath, meta, art)
            success += 1
            event_queue.put(
                json.dumps({
                    "type": "result",
                    "index": idx,
                    "total": len(files),
                    "file": filepath.name,
                    "status": "success",
                    "title": meta["title"],
                    "artist": meta["artist"],
                    "album": meta["album"],
                    "year": meta["year"],
                    "genre": meta["genre"],
                    "has_artwork": art is not None,
                    "artwork_url": meta.get("artwork_url", ""),
                })
            )
        except Exception as e:
            errors += 1
            event_queue.put(
                json.dumps({
                    "type": "result",
                    "index": idx,
                    "total": len(files),
                    "file": filepath.name,
                    "status": "error",
                    "message": str(e),
                })
            )

        # Be polite to the iTunes API
        time.sleep(0.4)

    event_queue.put(
        json.dumps({"type": "done", "success": success, "errors": errors})
    )
    with _lock:
        _processing = False


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/pick-folder")
def pick_folder():
    import platform
    import subprocess
    system = platform.system()
    path = None
    try:
        if system == "Darwin":
            result = subprocess.run(
                [
                    "osascript", "-e",
                    'POSIX path of (choose folder with prompt "Selecciona la carpeta de música:")',
                ],
                capture_output=True, text=True, timeout=120,
            )
            path = result.stdout.strip()

        elif system == "Windows":
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$d.Description = 'Selecciona la carpeta de música';"
                "$d.ShowNewFolderButton = $false;"
                "if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=120,
            )
            path = result.stdout.strip()

        else:  # Linux
            result = subprocess.run(
                ["zenity", "--file-selection", "--directory",
                 "--title=Selecciona la carpeta de música"],
                capture_output=True, text=True, timeout=120,
            )
            path = result.stdout.strip()

    except FileNotFoundError as e:
        return {"error": f"Comando no disponible: {e}"}
    except Exception as e:
        return {"error": str(e)}

    return {"path": path or None}


@app.post("/scan")
async def scan(request: Request):
    global _processing
    body = await request.json()
    folder = body.get("path", "").strip()

    if not folder or not os.path.isdir(folder):
        return {"error": "Ruta de carpeta inválida"}

    with _lock:
        if _processing:
            return {"error": "Ya hay un proceso en curso"}
        _processing = True

    # Drain old events
    while not event_queue.empty():
        try:
            event_queue.get_nowait()
        except Empty:
            break

    t = threading.Thread(target=_process_folder, args=(folder,), daemon=True)
    t.start()
    return {"status": "started"}


@app.get("/events")
def events():
    def generate():
        yield "retry: 3000\n\n"
        while True:
            try:
                data = event_queue.get(timeout=30)
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("type") == "done":
                    break
            except Empty:
                yield "data: {\"type\":\"ping\"}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/status")
def status():
    return {"processing": _processing}


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
