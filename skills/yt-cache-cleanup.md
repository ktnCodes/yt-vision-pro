---
name: yt-cache-cleanup
description: "Smart cleanup after a yt-deep-research run. Diffs embedded frames against all vault frames, keeps only what's in the report, and wipes the pipeline cache. Recovers disk space from downloaded video and extracted frames."
user_invocable: true
argument: video_id (required) - The YouTube video ID to clean up
---

# YouTube Cache Cleanup

After a yt-deep-research report is finalized, clean up the pipeline cache and prune unused vault frames. Keeps only the frames actually embedded in the report.

## Inputs

You need these three values. Ask the user if not provided:

| Input | Example | How to find it |
|---|---|---|
| `video_id` | `24t04HzoIXY` | From the report frontmatter `source_url` field |
| `report_path` | `MyIdeaverse/Vault/raw/youtube/deep-research-ai-thinking-partner.md` | The deep-research note to scan |
| `cache_dir` | `coding-projects/yt-vision-pro/cache` | Default unless user specifies otherwise |

All paths are relative to `C:\Users\kevin\Workspace\`.

---

## Phase 1: Vault Frame Pruning

Diff the report against the vault frames directory. Keep only frames that are actually embedded.

### Step 1: Extract embedded frame references

Read the report file and extract all Obsidian image embeds that match the video ID:

```
Pattern: ![[{video_id}_frame_*.jpg]]
```

Build the **embedded set** — the filenames that must survive.

### Step 2: List all vault frames

List all files in:

```
C:\Users\kevin\Workspace\MyIdeaverse\Vault\visualization\yt-frames\{video_id}\
```

This is the **vault set**.

### Step 3: Compute diff and confirm

```
unused = vault_set - embedded_set
```

Show the user:
- Total vault frames: {vault_set count}
- Embedded in report: {embedded_set count}
- To be deleted: {unused count}
- Estimated space recovered: {size of unused frames}

**Wait for user confirmation before deleting.** This is destructive.

### Step 4: Delete unused vault frames

After confirmation, delete every file in the unused set. Do NOT delete the directory itself — keep it for the remaining frames.

Report: `Kept {N} embedded frames, removed {M} unused ({X} MB recovered)`

---

## Phase 2: Pipeline Cache Cleanup

Clean the yt-vision-pro cache directory. Keep small reference files, delete large regenerable files.

### Step 5: Show what will be deleted

Scan the cache directory and categorize:

| Action | Target | Why |
|---|---|---|
| **DELETE** | `source.mp4` (and `.webm`, `.mkv` variants) | Largest file. Re-downloadable via yt-dlp. |
| **DELETE** | `frames/` directory (all extracted frames) | Already copied to vault. Regenerable from video. |
| **DELETE** | `pipeline.db` | SQLite DB with OCR/dedup data. Regenerable. |
| **DELETE** | `.stages/` directory (all sentinel files) | Forces clean re-run next time. |
| **KEEP** | `manifests/` directory | Small. Contains chapter analysis structure. Useful reference. |
| **KEEP** | `*.vtt` caption files | Small. Avoids re-downloading captions. |
| **KEEP** | `source.info.json` | Small. Video metadata (title, chapters, duration). |

Show the user estimated disk recovery from the DELETE targets.

**Wait for user confirmation before deleting.**

### Step 6: Execute cache cleanup

Delete the targets listed above. Use these PowerShell commands:

```powershell
$CACHE = "C:\Users\kevin\Workspace\coding-projects\yt-vision-pro\cache"

# Delete video file (largest)
Remove-Item "$CACHE\source.mp4" -ErrorAction SilentlyContinue
Remove-Item "$CACHE\source.webm" -ErrorAction SilentlyContinue
Remove-Item "$CACHE\source.mkv" -ErrorAction SilentlyContinue

# Delete extracted frames
Remove-Item "$CACHE\frames" -Recurse -Force -ErrorAction SilentlyContinue

# Delete pipeline DB
Remove-Item "$CACHE\pipeline.db" -ErrorAction SilentlyContinue

# Delete stage sentinels
Remove-Item "$CACHE\.stages" -Recurse -Force -ErrorAction SilentlyContinue
```

### Step 7: Verify and report

After cleanup, list what remains in the cache directory and report:

```
Cache cleanup complete for {video_id}:
  Vault frames: {kept} kept, {removed} removed ({vault_MB} MB recovered)
  Cache: video + frames + DB + sentinels deleted ({cache_MB} MB recovered)
  Kept: manifests/ ({N} files), captions ({M} .vtt files), source.info.json
  Total recovered: {total_MB} MB
```

---

## Recovery Note

If you ever need to re-run the pipeline on this video:
- Manifests are preserved for reference
- Captions are preserved (skip re-download)
- Video and frames will re-download/re-extract on next `python -m yt_vision_pro {url}`
- Stage sentinels are cleared, so all stages will re-run

The report itself is unaffected — embedded frames remain in `visualization/yt-frames/{video_id}/`.
