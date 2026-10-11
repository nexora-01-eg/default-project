# TROUBLESHOOTING.md

## `python` opens the Microsoft Store
The Store shim shadows real Python. Install via `.\setup.ps1 -Install`, then verify `where.exe python` points to `Python311\python.exe` before `.venv\`.

## `ffprobe not found`
Run `.\setup.ps1 -Install` (winget `Gyan.FFmpeg`), open a NEW terminal so PATH refreshes, then `video-engine doctor`.

## Whisper OOM / slow (16 GB RAM, 2 GB VRAM)
Use model `base` instead of `small`; keep CPU inference (default). Never force CUDA on the 940MX without a successful smoke run.

## NVENC errors on 940MX
Expected for HEVC — engine falls back to `h264_qsv` → `libx264` automatically. Check `ffmpeg -encoders | findstr nvenc`.

## Long 4K jobs stall
Use 1080p proxies first; 4K render only at the end. See Phase 12 docs when they land.
