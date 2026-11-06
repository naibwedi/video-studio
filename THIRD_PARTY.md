# Third-party libraries (dashboard)

Stored unmodified in `core/ui/vendor` so the dashboard works offline.

| Library | Version | License | Used for |
|---|---|---|---|
| [wavesurfer.js](https://github.com/katspaugh/wavesurfer.js) + Regions plugin | 7.10.0 | BSD-3-Clause | audio waveform, draggable lyric regions |
| [SortableJS](https://github.com/SortableJS/Sortable) | 1.15.6 | MIT | drag and drop to reorder shots |
| [Lucide](https://github.com/lucide-icons/lucide) | 0.460.0 | ISC | icons |

ffmpeg (not included in the repository) is downloaded by `setup.ps1`; Pillow is installed with pip.

## The editor (`editor/`, built with npm)

| Library | License | Used for |
|---|---|---|
| [React](https://react.dev) | MIT | interface |
| [Zustand](https://github.com/pmndrs/zustand) | MIT | state and undo history |
| [Lucide](https://lucide.dev) (lucide-react) | ISC | icons |
| [Vite](https://vite.dev), [TypeScript](https://www.typescriptlang.org), [Vitest](https://vitest.dev) | MIT / Apache-2.0 | build and tests |
