# LOCAL_FEASIBILITY.md

Grounded in `LOCAL_ENVIRONMENT_AUDIT.md` — never claims a solution is possible merely
because a related tool exists.

| Need signal | Local capability (verified) |
|---|---|
| STT/subtitles/dubbing | faster-whisper CPU/int8 know-how + FFmpeg 9.0.1 (sibling-verified) |
| video cut/edit/render | FFmpeg 9.0.1 full build, h264_qsv verified |
| reasoning/chat/extraction | Qwen2.5-Coder-7B loaded on :1234 (verified) |
| search/similarity | nomic-embed-text-v1.5 loaded on :1234 (verified) |
| images/faces | OpenCV in project .venv (verified) |
| storage/service | SQLite 3.45.1 / Python 3.11.9 / Node 24 / Docker 29.8 |

Output per opportunity: **High/Medium/Low + why**. Media-heavy needs note the 4C/2GB-VRAM
chunking caveat. NOT available locally: OCR, browser automation, PG/Redis/Elastic, Ollama,
paid APIs — flagged honestly when an opportunity needs them.
