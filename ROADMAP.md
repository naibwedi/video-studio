# Roadmap

Done: draft, thumbnails, teaser, quality check, native pop-ups (v0.2); form dashboard (v0.3);
**the timeline editor with live preview (v0.4)**.

The editor, in milestones:

1. **Editor shell** (done, v0.4): live preview, multi-track timeline, drag/trim/snap/razor, inspector, undo, render menu.
2. **More editing**: drag a shot to reorder, ripple edit, markers, transitions per cut, speed ramps, clip filmstrip that matches the used part,
   multi-select, copy/paste, lyric word timing with karaoke highlight.
3. **Claude co-editor**: an MCP server (see the frame under the playhead, search footage, retime lines, cut, swap, render) and the chat panel.
4. **AI pipeline**: search footage by meaning (open_clip), vocal separation + forced alignment for exact subtitle timing, beat grid on the timeline,
   smart 9:16 crop that follows the subject.
5. **Polish**: Ge'ez lyric styles and templates, colour looks, light leaks, export presets, DaVinci Resolve export (OTIO/FCPXML), desktop app (Tauri).
6. **YouTube**: results next to each video (read-only), then publish from the editor.
7. **Speed**: GPU encoding (turns on with NVIDIA driver 610+), faster final pass.
