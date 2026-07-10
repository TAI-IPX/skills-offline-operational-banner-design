---
name: battle-report-composer
description: Compose a vertical battle report long image (战报长图, 1080px wide) from KV hero image, section screenshots, main title, and statistics. Automatically extracts 12-color theme palette from KV, generates optional AI section banners, renders all text with local fonts. Use when user wants to create 战报, 数据战报, or 活动战报.
---

# Battle Report Composer

Compose a battle report long image: extract colors from KV, overlay text with local fonts, layout section screenshots, and output a 1080px-wide vertical poster.

## When to use

- User says "做战报" / "生成战报长图" / "帮我做一张战报" / "battle report"
- User has uploaded images and wants to compose a data/event battle report poster
- User provides a KV hero image + screenshots and needs a vertical summary image

## Inputs

| Input | Required | Source |
|-------|----------|--------|
| KV hero image | Yes | Auto-extracted from `input/uploads/` (largest image); or generated via Step 1 t2i |
| Main title | Yes | `-m` / `--main-title` |
| Subtitle | No | `-s` / `--tagline` |
| Bar text | No | `--bar-text` (launch banner text) |
| Stats | No | `--stat-exposure` / `--stat-download` |
| Section screenshots | No | `--report-dir` or auto-built from `input/uploads/` |
| Fonts | Yes | Auto-scanned from `scripts/assets/battle-report/fonts/` or system |

## Workflow (7 steps)

1. **Scan** — Validate KV.jpg and section subfolder structure in materials directory
2. **Color Extract** — K-means cluster KV top 55% → 12-color theme JSON (`color_extract.py`)
3. **Asset Prep** — Optionally generate AI section banner backgrounds (MICU/baoyu/nano-banana/Gemini)
4. **Hero Header** — Overlay main title, subtitle, platform logos, launch bar, and stats on KV (5 layout styles)
5. **Section Layout** — Compose section headers + screenshot grids for B/C/D zones
6. **Concatenate** — Stack all blocks vertically with zero gap
7. **Output** — JPEG quality 92 → `战报_{title}_{timestamp}.jpg`

## Resources

| Resource | Path |
|----------|------|
| Entry script | `scripts/run_battle_report.py` |
| Core package | `scripts/battle_report/` |
| Color extraction | `scripts/battle_report/color_extract.py` |
| Theme presets | `scripts/assets/battle-report/themes/` |
| Style profiles | `scripts/assets/battle-report/styles/` |
| Fonts directory | `scripts/assets/battle-report/fonts/` |
| Full spec | `docs/战报规范.md` |

## Usage via -g 战报

```bash
py scripts/run_full_with_custom_prompt.py -g 战报 --micugpt2 --packy7s \
  -m "主标题" -s "副标题" \
  --bar-text "首发启幕 联动数据重磅揭晓" \
  --stat-exposure "2亿+" --stat-download "100万+"
```

## Standalone usage

```bash
py scripts/run_battle_report.py ~/Desktop/战报 \
  -m "主标题" -s "副标题" \
  --bar-text "首发启幕" --stat-exposure "2亿+" --stat-download "100万+"
```

## Multi-section image classification

When images are uploaded to `input/uploads/`, the AI should:
1. Extract all images and identify the KV (largest image)
2. Ask the user to classify remaining screenshots into sections:
   - 核心资源矩阵 (Core Resources Matrix)
   - 联动活动火热开启 (Collaboration Event)
   - 玩家真实好评 (Player Praise)
3. Build a temporary materials directory with the proper subfolder structure
4. Pass it as `--report-dir` to the script

## Dependencies

- Python 3.8+
- Pillow, numpy, requests, python-dotenv
- 4 local font files (display-bold.otf, display-medium.otf, body-regular.otf, data-bold.otf)
- Optional: MICU_API_KEY / GEMINI_API_KEY for AI banner generation
