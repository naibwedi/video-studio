# video-studio

A small workshop for making videos from a song: lyric videos, teasers, vertical (9:16) and wide (16:9) versions,
with free stock footage, subtitles, your logo and subscribe pop-ups.

You (or Claude) describe a video in one small file, `projects/<name>/project.json`. The tool builds it.
Change the file, build again. Only the parts you changed are re-rendered.

---

## 0. Setup (first time, or on a new PC)

```
powershell -ExecutionPolicy Bypass -File setup.ps1
```

It makes the Python environment, downloads ffmpeg, creates `.env`, and runs `studio doctor`, which checks everything and says what to fix.
Run `studio doctor` any time something seems off. Tests: `.venv\Scripts\python.exe -m unittest discover tests`.

**Speed:** a first full build takes about 5 minutes, and a rebuild after changing one shot about 3 (use `--preview`, about 1 minute, while experimenting).
If `studio doctor` says GPU encoding is off, update your NVIDIA driver to version 610 or newer; builds then use the graphics card and get faster.

## 1. Running it

Open a terminal in this folder and use `studio` (a short name for `python studio.py`):

```
studio list                              what projects exist
studio build gundi --preview             fast small draft (about 1 minute)
studio build gundi                       full quality, both 16:9 and 9:16
studio build gundi --size 9x16           only vertical
studio build gundi --variant video_only  no sound, no subtitles (for CapCut)
studio pack gundi                        CapCut set: silent video + MP3 + subtitles
studio check exports\gundi\gundi_16x9.mp4   test a video for damage
```

Finished videos go to `exports\<project>\`.

> The first full build of a video is slow (5-8 minutes) because every shot is rendered once.
> After that, changing one shot takes about a minute: unchanged shots are reused from `.cache\`.
> Always use `--preview` while experimenting.

## 2. The folders

```
projects\gundi\project.json   the whole video: song, lyrics, shots, overlays   <- you edit this
projects\gundi\audio\         the song
library\stock\                downloaded stock clips (named p<id>.mp4)
library\brand\logo.jpg        your channel logo
library\overlays\             subscribe pop-up animations (from Remotion)
exports\                      finished videos, contact sheets
core\                         the program (you do not need to open this)
tools\bin\ffmpeg.exe          the video engine
```

## 3. project.json in plain words

```json
{
  "title": "ጉንዲ ዓይነይ'ዩ",
  "audio": "audio/gundi_full.wav",
  "sizes": ["16x9", "9x16"],
  "subtitles": { "lines": [ { "text": "first line", "start": 17.0, "end": 23.4 } ] },
  "overlays": {
    "logo":       { "image": "library/brand/logo.jpg", "in": 9.5, "out": 104 },
    "title_card": { "text": "Title", "subtitle": "Channel name", "in": 2, "out": 12 },
    "end_card":   { "title": "Title", "handle": "@channel", "tagline": "SUBSCRIBE", "in": 106.5 },
    "popups": [49, 99]
  },
  "shots": [ { "at": 0, "clip": "6960054", "start": 3 },
             { "at": "L3m", "clip": "19120716", "start": 1, "pan": 0.6 } ]
}
```

- **shots**: each one starts at `at` and runs until the next shot. `clip` is a Pexels number (from `library\stock`)
  or the path to your own video or photo. `start` is where in the clip to begin (seconds).
  `pan` (0 to 1) matters only for 9:16: it chooses which part of the wide picture stays in the tall frame.
- **at** can be seconds (`17.0`) or tied to the lyrics: `L3` = start of line 3, `L3m` = middle of line 3.
  Tied times follow the lyrics automatically when you fix the subtitle timing.
- Photos work too: use a `.jpg`/`.png` path as `clip` and it gets a slow zoom.
- Leave out `title_card`, `end_card` or `popups` if you do not want them.

Quick edits without opening the file:

```
studio shots gundi                              list shots with their times
studio swap gundi --at 17 --clip 6988904        change the clip of the shot at 17 s
studio swap gundi --at L3m --clip 19120716 --start 1
```

## 4. Exact subtitle timing (tap-sync)

The subtitle times Claude gets from the computer are a draft. To make them exact:

1. `studio tap gundi` makes a page: `projects\gundi\build\tap_sync.html`. Open it in your browser.
2. Press Play (it runs slowed down) and press **Space** at the moment each line starts being sung. Press **E** if the singing stops before the next line.
3. Press **Download .srt**.
4. `studio import-srt gundi C:\Users\naib\Downloads\gundi_lyrics_tapped.srt`
5. Build again.

## 5. Getting clips

Three ways, easiest first:

**A. Ask Claude (no key, works today).** Tell Claude the theme ("candles, roots, dark water"). Claude searches
Pexels in the browser, downloads the clips into `library\stock`, and shows you a picture sheet to choose from.
(Pexels has paused new API keys, so this is the main route for now.)

**B. By clip number.** If you know a clip number (the digits at the end of a Pexels video address):

```
studio fetch-ids 6988904 855482 --sheet
```

**C. Pixabay search (needs a free key).**

```
studio fetch "tree roots" --count 12 --source pixabay
```

Downloads 12 clips and makes a choosing sheet in `exports\_sheets\`. Pixabay clips are named `pb<number>` (for example `pb12345`)
and are used in project.json the same way as Pexels numbers.

### Pixabay key setup (free, 2 minutes)

1. Go to **https://pixabay.com/api/docs/** and log in (or sign up, free).
2. Once logged in, the documentation page shows your key in the text ("key (required)"). Copy it.
3. In this folder copy `.env.example` and rename the copy to `.env`.
4. Open `.env` in Notepad, replace `PASTE_YOUR_KEY_HERE` with your key, save.
5. Test: `studio fetch "candle flame" --count 6 --source pixabay`.

Keep the key private (only in `.env`, never in chat). Pixabay videos are free to use, no attribution needed.
(If Pexels opens new keys again: put it on the `PEXELS_API_KEY=` line and `studio fetch "..."` will use it.)

## 6. Starting a new video

```
studio new myvideo "C:\path\to\song.wav" --title "My Title"
```

Then edit `projects\myvideo\project.json`, or just tell Claude:
**the song file, the lyrics (Ge'ez is fine), the mood or theme, and which sizes you want.** Claude fills in the project,
picks and shows you footage to choose from, and builds it.

## 7. What each build makes

| Variant | Sound | Subtitles | Command |
|---|---|---|---|
| full | yes | yes | `--variant full` (default) |
| nosubs | yes | no | `--variant nosubs` |
| video_only | no | no | `--variant video_only` |

`studio pack <project>` collects the silent video, an MP3 and the subtitles in `exports\<project>\CapCut\`.

## 8. If something goes wrong

- **"Stock clip ... is not downloaded"**: run `studio fetch-ids <number>` or `studio fetch-ids <number> (or ask Claude to find clips)`.
- **A render stops with an error**: run the same command again; finished shots are kept.
- **A video looks damaged**: `studio check <file>`. Never run two builds at the same time on the same project.
- **Subtitle letters look wrong**: the font must be installed. The default is Ebrima (comes with Windows 10/11).

## 9. Not included yet (could be added)

- Changeable text in the animated subscribe pop-ups and end card (they are fixed videos from Remotion, in `library\overlays`).
  Rebuilding them for a new title means regenerating them with Remotion; ask Claude.
- Automatic subtitle timing is a rough draft only; tap-sync is the accurate way.
