# Roadmap

Done: draft, thumbnails, teaser, quality check, native pop-ups (v0.2); form dashboard (v0.3);
the timeline editor with live preview (v0.4); **Claude co-editor with an MCP tool server (v0.5)**; exact lyric timing from the singing (v0.6); lyric looks with karaoke, reorder and transitions, beat grid, smart 9:16 crop, search by meaning, versions and autosave, publish-ready export (v0.7).

The editor, in milestones:

1. **Editor shell** (done, v0.4): live preview, multi-track timeline, drag/trim/snap/razor, inspector, undo, render menu.
2. **More editing** (reorder, transitions and karaoke done, v0.7). Next: ripple delete, markers, speed ramps, clip filmstrip that matches the used part,
   multi-select, copy/paste, real per-word lyric timing (now spread by word length).
3. **Claude co-editor** (done, v0.5): MCP tools + chat panel. v0.7 added: it streams its text as it types, quick-prompt buttons, and it hears the song through the beat grid and loudness per bar. Next: before/after per change.
4. **AI pipeline**: exact lyric timing (done, v0.6). Search by meaning, beat grid and smart 9:16 crop done (v0.7). Next: the smart crop could follow a moving subject, not just one position per shot.
5. **Polish**: light theme, colour looks, light leaks, export presets, DaVinci Resolve export (OTIO/FCPXML), desktop app (Tauri).
6. **YouTube**: results next to each video (read-only), then publish from the editor.
7. **Speed**: GPU encoding (turns on with NVIDIA driver 610+), faster final pass.
