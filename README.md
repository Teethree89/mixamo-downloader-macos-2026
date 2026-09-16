# Mixamo Downloader — macOS 2026

A macOS/Python 3.13 compatible fork of the Mixamo bulk animation downloader.

## What changed

- Ported from **PySide2** to **PySide6** so it runs on current Apple Silicon Macs and Python 3.13.
- Uses the current PySide6 WebEngine API.
- Adds **Prefer native Mixamo In Place when available**.
- Logs whether a clip exposed a native Mixamo In Place parameter or had to retain authored root motion.
- Resolves `mixamo_anims.json` relative to the script directory, so launching from another working directory works correctly.
- Adds request timeouts and basic export failure reporting.

## Install

From Terminal:

```bash
python3 -m pip install PySide6 requests
```

## Run

Clone/download this repository, then:

```bash
cd mixamo-downloader-macos-2026/src
python3 main.pyw
```

Log into Mixamo inside the embedded browser and select/upload the character you want to animate.

Choose one of:

- **All animations**
- **Animations containing the word**
- **T-Pose (with skin)**

Choose an output folder, then leave **Prefer native Mixamo In Place when available** enabled if you want locomotion clips to use Mixamo's own in-place variant wherever the animation metadata exposes that control.

> Native In Place is intentionally conservative. The downloader only changes an animation when Mixamo's returned parameter metadata clearly identifies an In Place control. Animations without that parameter are downloaded unchanged rather than attempting to zero root motion locally.

## Important

Mixamo's animation API is not formally documented. The downloader reads the animation-specific `gms_hash` metadata returned by Mixamo and only opts into In Place when that metadata explicitly exposes it. The status log shows the decision for each clip.
