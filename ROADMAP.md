# Roadmap

Done: draft, thumbnails, teaser, quality check, native pop-ups (v0.2); form dashboard (v0.3);
the timeline editor with live preview (v0.4); **Claude co-editor with an MCP tool server (v0.5)**; exact lyric timing from the singing (v0.6).

The editor, in milestones:

1. **Editor shell** (done, v0.4): live preview, multi-track timeline, drag/trim/snap/razor, inspector, undo, render menu.
2. **More editing**: drag a shot to reorder, ripple edit, markers, transitions per cut, speed ramps, clip filmstrip that matches the used part,
   multi-select, copy/paste, lyric word timing with karaoke highlight.
3. **Claude co-editor** (done, v0.5): MCP tools + chat panel. Next for it: Claude hears the song (beat/section awareness), streams its text as it types, suggests edits as buttons.
4. **AI pipeline**: exact lyric timing (done, v0.6). Next: search footage by meaning (open_clip), beat grid on the timeline, smart 9:16 crop that follows the subject.
5. **Polish**: Ge'ez lyric styles and templates, colour looks, light leaks, export presets, DaVinci Resolve export (OTIO/FCPXML), desktop app (Tauri).
6. **YouTube**: results next to each video (read-only), then publish from the editor.
7. **Speed**: GPU encoding (turns on with NVIDIA driver 610+), faster final pass.
