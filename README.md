# video-studio

A small workshop for making videos from a song: lyric videos, teasers, vertical (9:16) and wide (16:9) versions,
with free stock footage, subtitles, your logo and subscribe pop-ups.

You (or Claude) describe a video in one small file, `projects/<name>/project.json`. The tool builds it.
Change the file, build again. Only the parts you changed are re-rendered.

---

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

**With a free Pexels key (recommended):**

```
studio fetch "tree roots" --count 12
```

This downloads 12 clips into `library\stock` and makes a picture sheet in `exports\_sheets\` so you can choose by number.

**Without a key:** if you already know a clip number (from the Pexels website address), `studio fetch-ids 6988904 855482 --sheet`.

### Pexels key: setup (2 minutes, free)

1. Go to **https://www.pexels.com/api/** and click **Get Started** (log in or sign up; it is free).
2. Fill the short form if it asks: a name, what you will use it for ("editing videos for my church channel"), and your channel link. Confirm.
3. The page now shows **Your API Key**: a long line of letters and numbers. Copy it.
4. In this folder, copy the file `.env.example` and rename the copy to `.env`.
5. Open `.env` with Notepad and replace `PASTE_YOUR_KEY_HERE` with your key. Save.
6. Test it: `studio fetch "candle flame" --count 6`.

Keep the key private: it lives only in `.env`, which is never uploaded or committed. Do not paste it in chat.
Free limits: 200 requests per hour, 20,000 per month. More than enough.
Pexels videos are free for YouTube, no attribution needed. (The exact button names on their site may differ a little.)

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

- **"Stock clip ... is not downloaded"**: run `studio fetch-ids <number>` or `studio fetch "<search>"`.
- **A render stops with an error**: run the same command again; finished shots are kept.
- **A video looks damaged**: `studio check <file>`. Never run two builds at the same time on the same project.
- **Subtitle letters look wrong**: the font must be installed. The default is Ebrima (comes with Windows 10/11).

## 9. Not included yet (could be added)

- Changeable text in the animated subscribe pop-ups and end card (they are fixed videos from Remotion, in `library\overlays`).
  Rebuilding them for a new title means regenerating them with Remotion; ask Claude.
- Automatic subtitle timing is a rough draft only; tap-sync is the accurate way.
