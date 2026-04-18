---
name: yt-deep-research
description: "Full research pipeline: transcript-first analysis with visual frame extraction as bonus context. Uses yt-vision-pro for chapter-aware frame extraction, OCR, and deep Ideaverse synthesis. Replaces watching the video."
user_invocable: true
argument: url (required) - The YouTube video URL to analyze
---

# YouTube Deep Visual Research

Fetch the transcript and metadata (primary source), run yt-vision-pro for visual frame extraction (bonus context), analyze both together, synthesize against the Ideaverse wiki, and write a vault note detailed enough to replace watching the video.

yt-vision-pro is implemented in `coding-projects/yt-vision-pro/` and exposed as the `yt-vision-pro` CLI / `python -m yt_vision_pro` module.

## Prerequisites

- `yt-vision-pro` installed in the workspace venv (`pip install -e coding-projects/yt-vision-pro`)
- `ffmpeg` on PATH
- Workspace venv activated

---

## Step 1: Fetch Transcript + Metadata (Primary Source)

Call both MCP tools for the video URL:
- `fetch_youtube_transcript(url)` - returns video_id, segment_count, and cache_path
- `fetch_video_metadata(url)` - returns title, channel, description

The transcript is the PRIMARY textual source for the entire analysis. Everything else is supplementary.

**Handling the transcript result:**
- If the result includes `formatted_transcript` inline, use it directly.
- If the result includes a `note` about the transcript being too large, read the full transcript from `cache_path` using `read_file`. The cached JSON contains `formatted_transcript` (timestamped text) and `transcript` (raw segments with start/duration).
- If the MCP tool fails entirely, fall back to the VTT captions in the yt-vision-pro cache (`cache/source.en.vtt`).

Read the full transcript now and keep it available for all subsequent analysis steps.

## Step 2: Run the yt-vision-pro Pipeline (Visual Context)

Activate the venv, add ffmpeg to PATH, and run the pipeline:

```powershell
& C:\Users\kevin\Workspace\.venv\Scripts\Activate.ps1; $env:PATH = "C:\Users\kevin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin;" + $env:PATH; cd C:\Users\kevin\Workspace\coding-projects\yt-vision-pro; python -m yt_vision_pro "$ARGUMENTS"
```

The default is **light mode**: transcript-guided cue detection + chapter-fill sampling (~100-200 frames, ~2-3 min). This extracts frames where the speaker references something visual ("as you can see", "look at this", "this diagram") plus even chapter coverage.

For heavy analysis with full scene detection and pHash dedup, add `--thorough`.

Pipeline stages:
- Light mode: fetch -> extract (cue-guided + chapter fill) -> ocr -> align -> manifest
- Thorough mode: fetch -> extract (scene detection) -> ocr -> dedup-with-ocr-context -> align -> manifest

Useful flags:
- `--max-frames 200` (light mode frame budget, default 200)
- `--thorough` (full scene detection + dense extraction + pHash dedup)
- `--detector content|adaptive` (thorough mode only)
- `--sensitivity FLOAT` (thorough mode only)
- `--density high|normal|low`
- `--dense-chapters "0,1,2"`
- `--dense-until "01:00:00"`
- `--from-stage dedup-with-ocr-context`

Capture the output and note:
- `video_id`
- chapter count
- frame count (and cue vs fill breakdown in light mode)
- manifest path or manifest directory
- caption source (`youtube` or `whisper`)

If the command fails, diagnose the actual failure mode before continuing.

After the pipeline completes, copy the extracted frames into the vault for Obsidian embedding. Prefix every filename with the video ID so embeds stay unique across videos.

```powershell
$VIDEO_ID = "{video_id}"
$CACHE_DIR = "C:\Users\kevin\Workspace\coding-projects\yt-vision-pro\cache"
New-Item -ItemType Directory -Path "C:\Users\kevin\Workspace\MyIdeaverse\Vault\visualization\yt-frames\$VIDEO_ID" -Force | Out-Null
Get-ChildItem "$CACHE_DIR\frames\*.jpg" | ForEach-Object {
    Copy-Item $_.FullName "C:\Users\kevin\Workspace\MyIdeaverse\Vault\visualization\yt-frames\$VIDEO_ID\${VIDEO_ID}_$($_.Name)"
}
```

## Step 3: Read the Generated Manifest(s)

Use the cache directory from Step 2.

Paths:
- Multi-chapter videos: `C:\Users\kevin\Workspace\coding-projects\yt-vision-pro\cache\manifests\`
- Single-chapter videos: `C:\Users\kevin\Workspace\coding-projects\yt-vision-pro\cache\manifest.md`

Each manifest now records:
- `density`
- `detector`
- `sensitivity`
- `scene_sample_interval`
- `slide_aware_dedup`
- caption source and OCR status

Read all manifests that belong to the run and total the number of frames and chunks.

## Step 4: Visual Analysis - View Every Frame

Process each chunk in each manifest.

For every frame:
1. View the image with `view_image`
2. Read the aligned caption text
3. Read the OCR text already stored in the manifest
4. Record what is on screen:
   - diagrams, architectures, or process maps
   - code, terminals, editors, demos
   - slide titles, bullets, charts, tables, benchmarks
   - URLs, commands, version numbers, labels
   - whether the frame is a talking head or information-dense content
5. Cross-check visual content against both captions and OCR

Do not skip frames.

If there are many frames, keep rolling notes in session memory so compaction does not lose frame-level observations.

## Step 5: Deep Content Analysis

After all frames are reviewed, synthesize transcript + captions + OCR + visuals into one analysis.

Identify:
- the main thesis
- all major takeaways, preserving taxonomies and sub-concepts
- every tool, framework, service, or method mentioned
- workflows or tutorials shown on screen
- code or commands visible on screen
- diagrams, benchmarks, or tables that matter
- 1-3 open questions
- source bias or agenda
- a confidence rating: High, Medium, or Low

## Step 6: Ideaverse Synthesis

Read:
1. `C:\Users\kevin\Workspace\MyIdeaverse\Vault\wiki\_index.md`
2. relevant section `_index.md` files
3. 3-10 relevant wiki articles

Produce:
- 2-4 convergent themes
- 1-3 tensions or extensions
- 3-5 actionable insights with why/try-it framing
- a 3-5 step curriculum arc ordered by effort

## Step 7: Generate Diagrams When Warranted

If the video shows or implies an architecture, workflow, or taxonomy worth preserving, generate an Excalidraw diagram and save it to:

`C:\Users\kevin\Workspace\MyIdeaverse\Vault\Excalidraw\research-{slug}.excalidraw`

Use the `excalidraw-diagram` skill approach. If no diagram is warranted, say so explicitly in the note.

## Step 8: Write the Research Note

Save to:

`C:\Users\kevin\Workspace\MyIdeaverse\Vault\raw\youtube\deep-research-{slug}.md`

Use this frontmatter:

```markdown
---
title: "[Video Title]"
description: "[What the video covers. Why it matters. What visual material was analyzed.]"
topic: "[primary-topic-slug]"
source: "[Channel Name]"
source_url: "https://youtu.be/VIDEO_ID"
source_type: youtube
analysis_type: deep-visual-research
date: YYYY-MM-DD
tags: [research, youtube, deep-research, topic-tag-1, topic-tag-2]
confidence: Low | Medium | High
frames_analyzed: [number]
chapters_processed: [number]
chunks_processed: [number]
diagrams_generated: [number or 0]
wiki_articles_referenced: [number]
pipeline: yt-vision-pro
related: []
---
```

Required sections:
- `## TL;DR`
- `## Visual Content Summary`
- `## Key Takeaways`
- `## Detailed Analysis`
- `## Ideaverse Synthesis`

In `Visual Content Summary`, embed the 3-5 most important frames using the prefixed filenames copied into `visualization/yt-frames/{video_id}/`.

The final note should be detailed enough that Kevin can rely on it instead of watching the source video.

### Curriculum Arc

| # | Experiment | What You'd Learn | Effort |
|---|-----------|-----------------|--------|
| 1 | [name] | [outcome] | Low |
| 2 | [name] | [outcome] | Medium |

## Open Questions

- [Question raised but not answered]
- [Follow-up worth investigating]

## Bias / Agenda Notes

[1-2 sentences on source credibility]

## Sources and References

- [Tools, libraries, links, papers, books mentioned in the video]
- [URLs visible on screen]
- [If none: "No external sources referenced."]

## Frame Reference

[List the key frames used in this analysis. Embed actual images using Obsidian wikilink syntax so they render inline.]

**[MM:SS] [what it shows]**
![[{video_id}_frame_XXXXX.XX.jpg]]

**[MM:SS] [what it shows]**
![[{video_id}_frame_XXXXX.XX.jpg]]
```

## Quality Rules

- **View every frame.** Do not skip frames or summarize from captions alone. The visual analysis IS the differentiator.
- **Embed images with `![[]]` syntax.** Key Visual Moments and Frame Reference sections must use Obsidian wikilink embeds (`![[{video_id}_frame_XXXXX.XX.jpg]]`), NOT inline code or markdown image links. Frames are copied to `visualization/yt-frames/{video_id}/` with video-ID-prefixed filenames so they are globally unique across the vault. The prefix prevents Obsidian from resolving to a same-named frame from a different video.
- **Frontmatter must be valid YAML.** The `related` field must use a YAML list of quoted strings, NOT raw wikilink syntax. Use `related: []` or a multi-line list with `- "[[article-slug]]"` entries. Obsidian renders `[[wikilinks]]` inside quoted YAML strings correctly in Properties view.
- **Preserve detail.** Key Takeaways must not compress multi-item categories. If the video defines 4 types of X, enumerate all 4.
- **Integrate visuals with speech.** The best insights come from combining what was shown with what was said. A diagram on screen + the speaker's explanation = richer understanding than either alone.
- **Ground the synthesis.** Every convergent theme and tension must cite specific wiki articles. No vague claims.
- **Actionable insights must be actionable.** "This is interesting" is not an insight. "Try running X against Y to test Z" is.
- **ASCII only.** No em dashes, smart quotes, or Unicode. Use hyphens, straight quotes, three dots (...).
- **Do not hallucinate.** Only include information present in the frames and captions.
- **Diagrams add value.** If the video showed an architecture, reproduce it properly. If the video discussed a system without showing it, diagram it yourself. Skip diagrams only for purely conversational content.
- **The report replaces the video.** Someone reading this note should understand the video's content, visuals, and arguments well enough to discuss them without having watched it.
