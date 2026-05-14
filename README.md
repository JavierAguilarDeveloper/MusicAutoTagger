# 🎵 Music Auto Tagger

Automatically tag your music library using just the file names.

Point it at a folder, and it will search for the title, artist, album, year, genre, and album artwork for each file — then write all the tags directly into the audio files.

![demo](https://i.imgur.com/placeholder.png)

## Features

- Parses filenames automatically — handles `Artist - Title`, `01 - Title`, or just `Title`
- Fetches metadata from the iTunes Search API (no API key required)
- Downloads and embeds album artwork (600×600)
- Supports **MP3**, **FLAC**, **M4A**, and **AAC**
- Real-time progress in the browser with live artwork previews
- Full results table at the end with filters (all / tagged / not found)
- Cross-platform: macOS, Windows, Linux

## Requirements

- Python 3.9+
- Internet connection (to query the iTunes API)

## Quick start

### macOS / Linux

```bash
git clone https://github.com/your-username/music-auto-tagger.git
cd music-auto-tagger
./start.sh
```

### Windows

```
Double-click start.bat
```

Then open your browser at **http://localhost:8000**

The start script creates a virtual environment and installs dependencies automatically on first run.

## How it works

1. Enter the path to your music folder (or use the 📂 button to browse)
2. The app scans for audio files recursively
3. For each file it parses the filename to extract artist and title
4. Queries the iTunes Search API for metadata
5. Downloads the album artwork
6. Writes all tags into the file using [mutagen](https://mutagen.readthedocs.io/)
7. Shows a full summary with artwork when done

## Tech stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/)
- **Tagging**: [mutagen](https://mutagen.readthedocs.io/)
- **Metadata source**: [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/)
- **Frontend**: Vanilla HTML/CSS/JS — no build step, no dependencies

## License

MIT
