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

## The editor (`studio ui`, or double-click `dashboard.bat`)

A real timeline editor in your browser, opening your actual video. Only this PC can open it.
The first launch builds it (needs Node.js 20+, one minute); after that it starts at once.

```
+--------+------------------------+-----------+
| Media  |   live preview         | Inspector |
| (clips)|   (plays your clips,   | (selected |
|        |    lyrics, cards)      |  item)    |
|        |  |<  <  PLAY  >  >|    | Claude    |
+--------+------------------------+-----------+
|  ruler   0:00      0:30      1:00      1:30   |
|  VIDEO   [shot][shot][shot][shot]...          |
|  LYRICS  [line][line][line]...                |
|  CARDS   [title]   [subscribe]   [end card]   |
|  LOGO    [corner logo ------------]           |
|  MUSIC   waveform                             |
+-----------------------------------------------+
```

- **Live preview:** plays the real clips with the slow drift, grade, cross-fades, Ge'ez subtitles, logo, title card, end card and the
  subscribe pop-up, in 16:9 or 9:16. It is close to the final render, not pixel-identical.
- **Edit on the timeline:** drag the edge of a shot to move a cut (it snaps to the playhead, lyric lines and other cuts), drag the gold
  lyric blocks to retime them, drag a clip from **Media** onto a shot to replace it, cut with **S** or the razor tool, delete with
  **Delete**, zoom with **Ctrl + wheel**. **Ctrl+Z / Ctrl+Y** undo and redo anything; Save turns off again when you undo back to the saved state.
- **Inspector:** click anything to edit its numbers and words. With nothing selected it shows the project: title, theme, channel, paste lyrics, add cards and pop-ups.
- **Render menu:** quick preview, full build, silent video for CapCut, teaser, thumbnails, quality check, CapCut pack. Progress shows next to it;
  click it to see jobs, cancel one, open the folder, or play the latest files.
- **Claude co-editor:** chat with Claude beside the timeline (see below).
- Shortcuts: press **?** in the editor.

### Exact lyric timing (Auto-time lyrics)

Paste your lyrics, then in the Inspector (nothing selected) press **Auto-time lyrics**, or run `studio align <project>` (add `--dry` to only look).
It separates the voice from the music (demucs), lets a speech model (Meta's MMS aligner, with the Tigrinya text transliterated by uroman) find where each
lyric line is sung, then snaps each line's edges to the nearest real breath. A song of two minutes takes about three minutes on the CPU (it runs as a
background job); the editor updates by itself and **Ctrl+Z undoes it**. The voice is cached, so the next run is faster.
On Gundi it agreed with the earlier draft times to within half a second on every line. Always check a few lines by ear (click a lyric block, press play).
`clarity` in the report says how sure it is; chanting or humming that is not in your lyrics is ignored.

One-time install (large: about 2-3 GB with the models, downloaded on first use):
```
.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
```
`studio doctor` tells you whether it is installed. Claude can start it too (the `auto_time_lyrics` tool).

### Claude, your co-editor

The panel on the right is Claude working **inside** your edit. Ask in plain words, with the playhead where you mean:

> "Look at the frame under the playhead and find a better shot." · "Make the cuts in the first verse faster." · "Write a title card and an end card." · "Review the pacing of the whole video."

Claude can **read** the edit, **look at frames** (a frame or a grid of frames, shown in the chat), **search your footage** by what it shows, and **change**
shots, cuts, clips, lyric lines and times, the title and end cards, pop-ups and the logo, draft a whole new shot list, and start a render.
While Claude works the timeline is locked ("Claude is editing…") and updates live. **One Ctrl+Z undoes everything Claude did in that turn**;
Ctrl+Y brings it back. It can only use these editing tools: not your files, not the shell, nothing else on this PC.

**One-time sign-in.** The chat runs Claude Code (installed with the Claude desktop app) as a program on your PC.
The desktop app signs itself in, but this copy needs its own login once: the panel shows the command; paste it in PowerShell and finish in the browser.
Prefer an API key? Put `ANTHROPIC_API_KEY=...` in the studio's `.env` (billed per use). Anthropic's rules for using a subscription outside its own apps
have changed several times, so for anything shared with other people use an API key. `studio doctor` shows the status.

**Where Claude Code lives:** the Claude desktop app is a Microsoft Store app, so its files show at `%APPDATA%\Claude` only to the app's own programs.
Your terminal and this studio find it in the real package folder (`%LOCALAPPDATA%\Packages\Claude_...\LocalCache\Roaming\Claude\claude-code`). The sign-in command in the panel already uses that path.

**Use these tools from any Claude** (for example Claude Code in a terminal): `studio mcp-config` prints the settings, or run
`claude mcp add studio -- "<python>" "<studio.py>" mcp`. The tools: `get_project`, `look`, `contact_sheet`, `search_clips`, `check_project`,
`split_shot`, `delete_shot`, `move_cut`, `swap_clip`, `set_shot`, `set_line`, `add_line`, `delete_line`, `shift_lines`, `set_title`, `set_theme`,
`set_card`, `add_popup`, `remove_popup`, `set_logo`, `draft_shots`, `render`. Indices are 1-based, as the editor shows them.

The earlier form-based dashboard is still available at `http://127.0.0.1:8765/classic` (and the link "Classic" in the top bar).
The editor's source is in `editor/` (React + TypeScript + Vite). After changing it: `cd editor`, then `npm run build`
(or `npm run dev` for live reloading while `studio ui` is running).

## The classic dashboard (`/classic`)

A control room in your browser. Double-click **`dashboard.bat`** (or run `studio ui`); it opens `http://127.0.0.1:8765`.
Only this PC can open it, and it stops when you close the window.

| Tab | What you do there |
|---|---|
| **Videos** | See every video; start a new one by choosing a song. |
| **Shots** | A waveform of the song with your lyric lines (gold) and shots (colours). Draft a shot list, drag a picture to move a clip to another slot, swap clips from the library, cut a shot at the playhead. |
| **Lyrics** | Paste the lyrics, then **tap-sync**: play the song and press **T** when each line starts. Or drag the gold blocks on the waveform, or type the seconds. Import an .srt, shift all lines. |
| **Style & cards** | Title, channel name and handle, corner logo timing, the title card, the end card, and the subscribe pop-ups (words and timing). |
| **Clip library** | Search all clips by tag, watch one, edit its tags (this is what makes the draft pick better). |
| **Render** | Build previews or full videos, teaser, thumbnails, quality check, CapCut pack. Jobs run one at a time with a progress bar and a Cancel button. |
| **Files** | Play or download everything that was built; open the folder. |
| **System** | The setup check and the shortcuts. |

Shortcuts: **Space** play/pause, **Left/Right** jump, **T** tap, **E** end of the last tapped line, **[ ]** set the selected line's start/end,
**Ctrl+Z / Ctrl+Y** undo/redo, **Ctrl+S** save. Every save keeps the previous version as `project.json.bak`.

Built with [wavesurfer.js](https://wavesurfer.xyz) (waveform and draggable regions), [SortableJS](https://sortablejs.github.io/Sortable/) (drag to reorder)
and [Lucide](https://lucide.dev) (icons). They are stored in `core/ui/vendor`, so the dashboard works offline. See `THIRD_PARTY.md`.

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

## 5b. Make a video fast: draft, thumbnail, teaser, quality check

Every clip in `library\stock` is tagged (what it shows, and whether a person is in it) in `library	ags.json`.

```
studio new myvideo "C:\path	o\song.wav" --title "My Title"   start a project
(put the lyric lines with their times into projects\myvideo\project.json)
studio draft myvideo --theme "repentance candle"               write a first shot list
studio draft myvideo --dry                                     show the plan without writing
studio build myvideo --preview                                 watch a fast draft
studio qc myvideo                                              quality check (see below)
studio thumb myvideo                                           3 YouTube thumbnails (1280x720)
studio teaser myvideo                                          ~50 s teaser from the finished video
```

- **Theme words:** `repentance, sorrow, mourning, prayer, praise, hope, journey, nature, bondage, emptiness, church`, or any tag
  such as `candle`, `chains`, `roots`, `fog`. Give a lyric line its own words with `"keywords": ["chains", "dark"]`.
  Faces are avoided by default (silhouettes and hands are fine); `--people` allows faces. `--seed 2` gives a different pick.
- **Tag new clips:** `studio tag add 123456 "candle dark warm" --people 0` (0 none, 1 silhouette/hands, 2 face). Search: `studio tag find candle church`.
- **`qc`** checks the lyric lines (overlaps, too long), shots that are too short, pop-ups past the end, and in the rendered video:
  black frames, long silences, loudness (YouTube likes about -14 LUFS) and clipping.
- **Teaser:** the default cut is the start of the first verse, two spots further in, and the end card. Choose your own with
  `--segments "17-31,70-84,110-122"` or `"teaser": {"segments": [[17, 31], [70, 84]]}` in project.json.
- **Thumbnails** are made from the silent video (`--variant video_only`) so no subtitles show; `--at 20,60` picks the moments,
  `--text` and `--sub` change the words.

### Subscribe pop-ups
`"popups": [49, 99]` slides in a card at those seconds, "clicks" SUBSCRIBE, then slides out. For your own words:
`"popups": [{"at": 49, "tagline": "Subscribe for the full mezmur", "dur": 5, "click": 2.6}]`.
The channel name and handle come from `"channel"` in project.json (defaults are set for ሰብአ ሰገል).
`"popup_style": "mov"` brings back the old Remotion video pop-up.

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

- Automatic subtitle timing is a rough draft only; tap-sync is the accurate way.
