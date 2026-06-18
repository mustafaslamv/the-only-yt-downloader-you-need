# YouTube Downloader

A simple local app for downloading YouTube content with a clean Streamlit interface.

## Features

- Download a single video or an entire playlist
- Choose a video quality cap
- Download music as MP3 with the thumbnail embedded
- Save files into a folder you choose

## Why Python

Python is a strong fit here because `yt-dlp` already solves the hard part of YouTube downloading, while Streamlit gives us a quick, well structured UI.

## Requirements

- Python 3.10+
- `ffmpeg` installed and available on your `PATH`

`ffmpeg` is needed to merge video and audio streams and to embed thumbnails into music files.

## Install

Fastest path:

```bash
bash run.sh
```

That script creates a local virtual environment, bootstraps `pip` if needed, installs dependencies, and starts the app.

Manual setup:

```bash
python3 -m ensurepip --upgrade
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

```bash
python -m streamlit run app.py
```

## How to use

1. Paste a YouTube video or playlist URL.
2. Choose `Video` or `Music`.
3. Pick the quality you want.
4. Decide whether to download the entire playlist.
5. Click `Start download`.

For music downloads, the app saves MP3 audio and embeds the thumbnail automatically.

## Notes

- Use this for content you own or are allowed to download.
- If downloads fail, check that `ffmpeg` is installed correctly.
