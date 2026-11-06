"""video-studio command line.   python studio.py --help"""
import argparse, json, os, shutil, sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from core import paths, project, render, stock, tools

paths.load_env()


def sizes_for(p, size):
    return p["sizes"] if size in (None, "all") else [size]


def cmd_list(a):
    for d in sorted(os.listdir(paths.PROJECTS)):
        if os.path.exists(project.json_path(d)):
            p = project.load(d)
            print(f"{d:20} {p['duration']:6.1f}s  {len(p['_shots'])} shots  {len(p['subtitles']['lines'])} lyric lines  {p['title']}")


def cmd_build(a):
    p = project.load(a.project)
    for size in sizes_for(p, a.size):
        for variant in (render.VARIANTS if a.variant == "all" else [a.variant]):
            out = render.build(p, size, variant, preview=a.preview)
            tools.check(out)


def cmd_check(a):
    ok = all([tools.check(f) for f in a.files])
    sys.exit(0 if ok else 1)


def cmd_pack(a):
    tools.pack(project.load(a.project))


def cmd_fetch(a):
    files = stock.fetch(a.query, a.count, a.orientation, a.source)
    out = os.path.join(paths.EXPORTS, "_sheets", a.query.replace(" ", "_") + ".png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print("choosing sheet ->", paths.rel(stock.sheet(files, out)))


def cmd_fetch_ids(a):
    files = stock.fetch_ids(a.ids)
    if files and a.sheet:
        out = os.path.join(paths.EXPORTS, "_sheets", "ids.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        print("choosing sheet ->", paths.rel(stock.sheet(files, out)))


def cmd_sheet(a):
    import glob
    files = sorted(glob.glob(os.path.join(paths.STOCK, "p*.mp4")))
    if a.ids:
        files = [paths.stock_path(i) for i in a.ids]
    files = files[a.skip:a.skip + a.count]
    out = os.path.join(paths.EXPORTS, "_sheets", f"library_{a.skip}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print("sheet ->", paths.rel(stock.sheet(files, out)))


def cmd_tap(a):
    tools.tap_html(project.load(a.project))


def cmd_import_srt(a):
    tools.import_srt(a.project, a.srt)


def cmd_swap(a):
    tools.swap(a.project, a.at, a.clip, a.start, a.pan)


def cmd_shots(a):
    p = project.load(a.project)
    cuts = [s["at"] for s in p["_shots"]] + [p["duration"]]
    for i, s in enumerate(p["_shots"]):
        print(f"{cuts[i]:7.1f} - {cuts[i + 1]:6.1f}  {s['clip']:>10}  start={s['start']:<5} pan={s['pan']}")


def cmd_doctor(a):
    tools.doctor()


def cmd_new(a):
    d = project.project_dir(a.name)
    if os.path.exists(d):
        sys.exit(f"projects/{a.name} already exists")
    os.makedirs(os.path.join(d, "audio"))
    audio = os.path.join("audio", os.path.basename(a.audio))
    shutil.copy(a.audio, os.path.join(d, audio))
    raw = {"title": a.title or a.name, "audio": audio, "sizes": ["16x9", "9x16"],
           "subtitles": {"lines": [{"text": "first lyric line", "start": 0.0, "end": 5.0}]},
           "overlays": {"logo": {"image": "library/brand/logo.jpg", "in": 3.0, "out": None},
                        "title_card": {"text": a.title or a.name, "subtitle": "", "in": 1.0, "out": 6.0}},
           "shots": [{"at": 0, "clip": "6988904", "start": 2}]}
    json.dump(raw, open(project.json_path(a.name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"created projects/{a.name}/project.json - edit it, then: python studio.py build {a.name} --preview")


def main():
    ap = argparse.ArgumentParser(description="video-studio: build lyric / teaser videos from a project.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list projects").set_defaults(f=cmd_list)

    s = sub.add_parser("build", help="render a project")
    s.add_argument("project")
    s.add_argument("--size", choices=["16x9", "9x16", "all"], default="all")
    s.add_argument("--variant", choices=["full", "nosubs", "video_only", "all"], default="full",
                   help="full = sound + subtitles; nosubs = sound only; video_only = silent, no subtitles")
    s.add_argument("--preview", action="store_true", help="half size, fast draft")
    s.set_defaults(f=cmd_build)

    s = sub.add_parser("check", help="test videos for decode errors")
    s.add_argument("files", nargs="+")
    s.set_defaults(f=cmd_check)

    s = sub.add_parser("pack", help="CapCut set: silent video + MP3 + SRT")
    s.add_argument("project")
    s.set_defaults(f=cmd_pack)

    s = sub.add_parser("fetch", help="search Pexels, download clips, make a choosing sheet (needs PEXELS_API_KEY)")
    s.add_argument("query")
    s.add_argument("--count", type=int, default=12)
    s.add_argument("--orientation", default="landscape", choices=["landscape", "portrait", "square"])
    s.add_argument("--source", default="auto", choices=["auto", "pexels", "pixabay"])
    s.set_defaults(f=cmd_fetch)

    s = sub.add_parser("fetch-ids", help="download Pexels clips by id, no key needed (id or id:fps)")
    s.add_argument("ids", nargs="+")
    s.add_argument("--sheet", action="store_true")
    s.set_defaults(f=cmd_fetch_ids)

    s = sub.add_parser("sheet", help="contact sheet of clips already in the library")
    s.add_argument("--ids", nargs="*")
    s.add_argument("--skip", type=int, default=0)
    s.add_argument("--count", type=int, default=30)
    s.set_defaults(f=cmd_sheet)

    s = sub.add_parser("shots", help="show the shot list of a project")
    s.add_argument("project")
    s.set_defaults(f=cmd_shots)

    s = sub.add_parser("swap", help="change the clip of the shot at a time:  swap gundi --at 17 --clip 6988904")
    s.add_argument("project")
    s.add_argument("--at", required=True, help="seconds, or L3 / L3m (line 3 start / middle)")
    s.add_argument("--clip", required=True)
    s.add_argument("--start", type=float)
    s.add_argument("--pan", type=float)
    s.set_defaults(f=cmd_swap)

    s = sub.add_parser("tap", help="make the tap-sync page for exact subtitle times")
    s.add_argument("project")
    s.set_defaults(f=cmd_tap)

    s = sub.add_parser("import-srt", help="load tapped subtitle times into the project")
    s.add_argument("project")
    s.add_argument("srt")
    s.set_defaults(f=cmd_import_srt)

    sub.add_parser("doctor", help="check the setup").set_defaults(f=cmd_doctor)

    s = sub.add_parser("new", help="start a new project from a song")
    s.add_argument("name")
    s.add_argument("audio", help="path to the song (wav/mp3)")
    s.add_argument("--title")
    s.set_defaults(f=cmd_new)

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
