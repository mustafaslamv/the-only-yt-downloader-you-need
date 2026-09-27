# YouTube Downloader

Download YouTube videos, playlists and music straight to your computer. You paste a link, pick a few options, and the file shows up in a folder you choose.

## Before you start (one time)

Install these two free things:

1. **Python 3.10+** — from [python.org](https://www.python.org/downloads/)
2. **ffmpeg** — the program that handles audio/video files
   - Linux: `sudo apt install ffmpeg`
   - Mac: `brew install ffmpeg`
   - Windows: download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Start the app

```bash
bash run.sh
```

This sets everything up and starts the app. Click the link it prints (it usually opens your browser by itself).

To close the app later, click **Stop server** in the left sidebar.

## Download your first video

1. **1. What do you want?** → choose `Video` (pick `Music` if you only want the sound).
2. **2. What to download?** → choose `Single video`.
3. Paste the YouTube link in the box and click **Fetch details**.
4. Check that the picture and title look right.
5. Choose a folder to save in (there is already a `downloads` folder picked for you).
6. Click **Start download**.

When the green **Download complete** message appears, your file is in the folder. The defaults are good enough for everyday use — you can ignore the rest of the options.

## Things you can do, and how

**Download a whole playlist**
Choose `Playlist` in step 2, paste the playlist link, click **Fetch details**, leave all the boxes ticked, then **Start download**.
Only want a few songs? Click **Select none**, then tick just the ones you want.

**Get only the music (MP3 with the cover picture)**
Choose `Music`, keep `MP3`, click **Start download**. The cover art and the title are saved inside the file automatically.

**Make files smaller**
- Video: set `Video quality` to `Up to HD (720p)` or lower.
- Music: pick `Good (192 kbps)` or `Economy (128 kbps)`.

**Add subtitles**
Tick `Download subtitles`, pick the languages, and start. Tick `Embed subtitles into the video` if you want them inside the video file.

**Cut out sponsor ads**
Use `Skip sections with SponsorBlock` and tick what you want removed (sponsors, intros, end credits...). The parts are cut out of the saved file.

**Download a private or age-restricted video**
Open `Advanced options` → set `Browser cookies` to the browser where you are already logged in to YouTube.

**Re-download a playlist without redoing finished files**
Open `Advanced options` → tick `Skip files that already exist in the folder`, save into the same folder again.

**Save your internet connection**
Open `Advanced options` → set `Max download speed` (for example `2` for 2 MB/s).

**Stop a download halfway**
Click **Stop download** at the top, then **Dismiss** when it says it stopped.

**Check what you downloaded before**
Open `Download history` at the bottom of the page.

## If something goes wrong

| Problem | What to do |
| --- | --- |
| Yellow warning: ffmpeg was not found | Install ffmpeg (see "Before you start") and restart the app |
| `Start download` button is greyed out | Click **Fetch details** first — the app needs to see the link |
| `HTTP Error 403: Forbidden` | YouTube changed something; run `pip install -U yt-dlp` and try again |
| Page shows `Connection error` | You clicked **Stop server** — that is normal. Start it again with `bash run.sh` |
| Wrong link / nothing found | Paste a normal YouTube link (`youtube.com/watch?v=...` or `youtu.be/...`) |

## For developers

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m streamlit run app.py   # run the app
python -m unittest discover -s tests   # run the tests
```

Python was chosen because `yt-dlp` already solves the hard part of YouTube downloading, and Streamlit gives a quick, well-structured UI.
