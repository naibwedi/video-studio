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

## Optional AI tools (`requirements-ai.txt`, installed with pip; not stored in the repository)

| Library / model | License | Used for |
|---|---|---|
| [demucs](https://github.com/adefossez/demucs) (htdemucs model) | MIT | separating the voice from the music |
| [PyTorch / torchaudio](https://pytorch.org) (MMS_FA aligner model from Meta) | BSD-3-Clause / CC-BY-NC for the MMS model weights | finding where lyric lines are sung |
| [uroman](https://github.com/isi-nlp/uroman) | Apache-2.0 | transliterating Ge'ez text for the aligner |
| [open_clip](https://github.com/mlfoundations/open_clip) (ViT-B-32, LAION-2B weights) | MIT / MIT | search footage by meaning |
| [torchvision, timm, ftfy](https://pytorch.org/vision) | BSD-3 / Apache-2.0 / MIT | helpers for open_clip |

The MMS weights are licensed for non-commercial use: fine for your own church channel, but check before using it in a paid product.
