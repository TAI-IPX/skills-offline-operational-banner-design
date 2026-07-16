#!/usr/bin/env python3
"""
邮件长图生成：1920 宽竖版，KV + EVENT01~04 四区排版。
色调从 KV 图自动提取，装饰纹理走 Vision 风格分析后 API 生图，
标题使用指定字体，正文使用微软雅黑。

编程调用：
    from email_poster import make_email_poster
    make_email_poster(kv="kv.png", font_title="fonts/title.otf", ...)
"""
from __future__ import annotations

import sys
import os
import io
import re
import base64
import json
import time
import colorsys
import urllib.request
import urllib.error
import requests
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Canvas ──
CANVAS_W = 1920

# ── KV title ──
KV_TITLE_SIZE = 200
KV_SUBTITLE_SIZE = 84
KV_TITLE_SUB_GAP = 20

# ── Section layout ──
SECTION_GAP = 60
SECTION_PAD_LR = 72
SECTION_PAD_TOP = 60
SECTION_PAD_BOTTOM = 60
SECTION_TITLE_SIZE = 96
CANVAS_PAD_BOTTOM = 200   # 画布底部留白

# ── Event badge ──
BADGE_PAD_X = 40
BADGE_PAD_Y = 16
BADGE_ENUM_SIZE = 28
BADGE_ENUM_PAD = 12
BADGE_RADIUS = 16
BADGE_CONTENT_GAP = 60

# ── Text box ──
TEXT_BOX_PAD_X = 60
TEXT_BOX_PAD_Y = 60
TEXT_BOX_RADIUS = 16

LINE_HEIGHT_RATIO = 1.6

EVENT_DATE_SIZE = 46
EVENT_DESC_SIZE = 42
EVENT_INTRO_SIZE = 36

# ── Cards ──
CARD_GAP = 40
CARD_RADIUS = 16
CARD_NAME_SIZE = 36
CARD_NAME_H = 56
CARD_IMG_PAD = 24

# ── Shadows removed ──

# ── Frosted frame ──
FRAME_BORDER_WIDTH = 2
FRAME_BLUR_RADIUS = 16
FRAME_TINT_ALPHA = 80

# ── Decor ──
DECOR_MAX_H = 4800

# ── Brand header (KV 左上角品牌行) ──
BRAND_LOGO_SIZE = 56
BRAND_PAD_X = 48
BRAND_PAD_Y = 40
BRAND_SUBLABEL_SIZE = 22
BRAND_NAME_SIZE = 34
BRAND_TEXT_GAP = 4

# ── Device frame (EVENT02 截图模拟窗口) ──
DEVICE_FRAME_RADIUS = 18
DEVICE_TITLEBAR_H = 40
DEVICE_DOT_R = 6
DEVICE_DOT_GAP = 18
DEVICE_BORDER_WIDTH = 1

# ── Wave divider (区块间水波分隔) ──
WAVE_HEIGHT = 36
WAVE_SAMPLE_COUNT = 20

# ── Decor stickers (吉祥物/水滴贴纸) ──
STICKER_SIZE = 816  # 最小满足 API 像素要求（655360px）且为 16 倍数，生成后缩放到目标尺寸

# ── Combined section banner (AI 装饰背景 + 分区标题，替代 transition + section banner) ──
COMBINED_BANNER_H = 640          # API 生成高度（px），16的倍数，满足 ≤3:1 纵横比
COMBINED_BANNER_DISPLAY_H = 320  # 实际显示高度（px），从生成图中裁剪中心
TRANSITION_BANNER_EDGE_FADE = 10 # 上下边缘渐变融合宽度（px）

# ── Section banner (从战报移植：渐变+半调网点+辉光+描边炫彩栏头) ──
SECTION_BANNER_H = 200
SECTION_BANNER_TOP_TAPE_H = 8
SECTION_BANNER_RADIUS = 20

_YAHEI_FONT_PATH: str | None = None


# ══════════════════════════════════════════════════════════════════
#  Utility functions (adapted from changtu/poster.py)
# ══════════════════════════════════════════════════════════════════

def set_yahei_font(path: str | Path) -> None:
    global _YAHEI_FONT_PATH
    _YAHEI_FONT_PATH = str(Path(path).resolve())


def _check_fonts(font_title_path: str | Path, font_yahei_path: str | Path | None) -> None:
    title_path = Path(font_title_path)
    if not title_path.is_file():
        print(f"[邮件长图/字体] 标题字体不存在: {title_path}", file=sys.stderr)
        print("  请使用 --font-title 指定有效的 .otf 或 .ttf 字体文件路径。", file=sys.stderr)
        sys.exit(1)
    if font_yahei_path:
        set_yahei_font(font_yahei_path)
    try:
        _yahei(24)
    except (RuntimeError, OSError) as e:
        print(f"[邮件长图/字体] 微软雅黑加载失败: {e}", file=sys.stderr)
        print("  正文使用微软雅黑，请确保已安装。或使用 --font-yahei 手动指定路径。", file=sys.stderr)
        sys.exit(1)


def _drop_shadow(canvas, _draw,
                 x: int, y: int, w: int, h: int,
                 radius: int,
                 shadow_color: tuple[int, int, int] | None = None) -> None:
    pass


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    return int(round(font.size * LINE_HEIGHT_RATIO))


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")[:6]
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def _c(c: int) -> float:
        x = c / 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * _c(rgb[0]) + 0.7152 * _c(rgb[1]) + 0.0722 * _c(rgb[2])


def _contrast_ratio(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    l1, l2 = _relative_luminance(c1), _relative_luminance(c2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _mix_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _lighten(rgb: tuple[int, int, int], amt: float = 0.2) -> tuple[int, int, int]:
    return _mix_rgb(rgb, (255, 255, 255), amt)


def _darken(rgb: tuple[int, int, int], amt: float = 0.3) -> tuple[int, int, int]:
    return _mix_rgb(rgb, (0, 0, 0), amt)


def _boost_vivid(rgb: tuple[int, int, int], *, sat_mul: float = 1.1, val_mul: float = 1.12) -> tuple[int, int, int]:
    """提升饱和度/明度（移植自战报 compose_battle_report.py）。"""
    r, g, b = (x / 255.0 for x in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(1.0, s * sat_mul)
    v = min(1.0, v * val_mul)
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return tuple(int(round(x * 255)) for x in (r2, g2, b2))


def _draw_halftone_band(ld: ImageDraw.ImageDraw,
                        box: tuple[int, int, int, int],
                        rgb: tuple[int, int, int],
                        *, dot: int = 6, alpha: int = 160) -> None:
    """棋盘状半调网点纹理（移植自战报）。"""
    x0, y0, x1, y1 = box
    for yy in range(y0, y1, dot):
        for xx in range(x0, x1, dot):
            if ((xx - x0) // dot + (yy - y0) // dot) % 2 == 0:
                ld.rectangle([xx, yy, xx + dot - 2, yy + dot - 2], fill=(*rgb, alpha))


def _load_font(path: str | Path | ImageFont.FreeTypeFont, size: int) -> ImageFont.FreeTypeFont:
    """支持传入路径或已加载的字体对象。"""
    if isinstance(path, ImageFont.FreeTypeFont):
        return ImageFont.truetype(path.path, size)
    return ImageFont.truetype(str(Path(path).resolve()), size)


def _resolve_yahei_path() -> Path:
    global _YAHEI_FONT_PATH
    if _YAHEI_FONT_PATH:
        p = Path(_YAHEI_FONT_PATH)
        if p.is_file():
            return p
    name = "msyh.ttc"
    alt_names = ["MSYH.TTC", "msyh.ttf", "msyhbd.ttc", "msyhbd.ttf", "Microsoft YaHei.ttf"]
    search_dirs: list[Path] = []
    cwd = Path.cwd()
    search_dirs.append(cwd / "fonts")
    search_dirs.append(cwd)
    search_dirs.append(Path.home() / "Library" / "Fonts")
    search_dirs.append(Path("/Library/Fonts"))
    windir = Path("C:/Windows/Fonts")
    if windir.is_dir():
        search_dirs.append(windir)
    for d in search_dirs:
        if not d.is_dir():
            continue
        for n in [name] + alt_names:
            p = d / n
            if p.is_file():
                _YAHEI_FONT_PATH = str(p.resolve())
                return p
    raise RuntimeError(
        "Microsoft YaHei font not found. "
        "Use set_yahei_font() or --font-yahei to specify the path."
    )


def _yahei(size: int, font_path: str | Path | None = None) -> ImageFont.FreeTypeFont:
    if font_path:
        return ImageFont.truetype(str(Path(font_path).resolve()), size)
    return ImageFont.truetype(str(_resolve_yahei_path()), size)


def _prize_rows(count: int) -> list[int]:
    if count <= 3:
        return [count]
    if count == 4:
        return [2, 2]
    if count == 5:
        return [2, 3]
    if count == 6:
        return [3, 3]
    if count == 7:
        return [3, 4]
    if count == 8:
        return [4, 4]
    rows = []
    while count > 0:
        rows.append(min(4, count))
        count -= min(4, count)
    return rows


NO_LINE_START = set("\uff0c\u3002\uff01\uff1f\u3001\uff1b\uff1a\u300d\u300f\u3015\u3011\u201d\u2014\u2026")


def _wrap_text(draw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for ch in paragraph:
            test = current + ch
            if draw.textbbox((0, 0), test, font=font)[2] > max_w and current:
                if ch in NO_LINE_START:
                    lines.append(current + ch)
                    current = ""
                else:
                    lines.append(current)
                    current = ch
            else:
                current = test
        if current:
            lines.append(current)
    i = 1
    while i < len(lines):
        if len(lines[i]) <= 1 and lines[i] not in NO_LINE_START:
            merged = lines[i - 1] + lines[i]
            if draw.textbbox((0, 0), merged, font=font)[2] <= max_w:
                lines[i - 1] = merged
                lines.pop(i)
                continue
        i += 1
    return lines


def _load_prizes(prize_dir: str, order: list[str] | None = None) -> list[tuple[str, Image.Image]]:
    pdir = Path(prize_dir)
    if not pdir.is_dir():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    items: dict[str, Path] = {}
    for f in sorted(pdir.iterdir()):
        if f.suffix.lower() in exts and not f.name.startswith("."):
            items[f.stem] = f
    if order:
        ordered: list[tuple[str, Path]] = []
        used = set()
        for kw in order:
            matched = [(k, v) for k, v in items.items() if kw in k and k not in used]
            if matched:
                ordered.extend(matched)
                used.update(k for k, _ in matched)
        for k, v in items.items():
            if k not in used:
                ordered.append((k, v))
                used.add(k)
        items_list = ordered
    else:
        items_list = sorted(items.items())
    result: list[tuple[str, Image.Image]] = []
    for name, path in items_list:
        try:
            img = Image.open(path).convert("RGBA")
            result.append((name, img))
        except Exception as e:
            print(f"  [warn] skip prize {name}: {e}")
    return result


def _trim_transparency(img: Image.Image) -> Image.Image:
    arr = np.array(img.convert("RGBA"))
    alpha = arr[:, :, 3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not rows.any():
        return img
    ys = np.where(rows)[0]
    xs = np.where(cols)[0]
    return img.crop((xs[0], ys[0], xs[-1] + 1, ys[-1] + 1))


def _fit_trimmed(img: Image.Image, tw: int, th: int) -> Image.Image:
    trimmed = _trim_transparency(img)
    w, h = trimmed.size
    scale = min(tw / w, th / h)
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    result = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    resized = trimmed.resize((nw, nh), Image.Resampling.LANCZOS)
    px = (tw - nw) // 2
    py = (th - nh) // 2
    result.paste(resized, (px, py), resized if resized.mode == "RGBA" else None)
    return result


def _draw_neon_border(canvas, x: int, y: int, w: int, h: int,
                      glow_color: tuple[int, int, int],
                      radius: int = 16,
                      glow_layers: int = 6,
                      line_width: int = 2) -> None:
    """Function kept for compatibility but no longer used."""
    pass


def _frosted_frame(canvas, draw,
                   x: int, y: int, w: int, h: int,
                   tint_rgb: tuple[int, int, int],
                   border_color: tuple[int, int, int],
                   radius: int, border_width: int) -> None:
    region = canvas.crop((x, y, x + w, y + h))
    blurred = region.filter(ImageFilter.GaussianBlur(FRAME_BLUR_RADIUS))
    tint = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tp = tint.load()
    for py in range(h):
        t = py / max(h - 1, 1)
        a = int(FRAME_TINT_ALPHA * (0.6 + 0.4 * t))
        for px in range(w):
            tp[px, py] = (*tint_rgb, a)
    blended = Image.alpha_composite(blurred.convert("RGBA"), tint)
    canvas.paste(blended, (x, y), blended)
    # _draw_neon_border(canvas, x, y, w, h, border_color,
    #                   radius=radius, glow_layers=6, line_width=border_width)







# ══════════════════════════════════════════════════════════════════
#  Brand header (KV 左上角小 icon + 竖排双行文字)
# ══════════════════════════════════════════════════════════════════

def _draw_brand_header(canvas, draw,
                       brand_logo: Image.Image | None,
                       brand_name: str,
                       brand_sublabel: str,
                       font_brand: ImageFont.FreeTypeFont,
                       font_sublabel: ImageFont.FreeTypeFont,
                       accent: tuple[int, int, int]) -> None:
    """在 KV 左上角绘制品牌行：小方形/圆形 icon + 竖排双行文字（小字在上，大字在下）。
    若未提供 logo 则只放文字。"""
    x = BRAND_PAD_X
    y = BRAND_PAD_Y
    if brand_logo:
        logo = brand_logo.convert("RGBA")
        logo = _fit_trimmed(logo, BRAND_LOGO_SIZE, BRAND_LOGO_SIZE)
        # 圆形裁切 icon
        mask = Image.new("L", (BRAND_LOGO_SIZE, BRAND_LOGO_SIZE), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, BRAND_LOGO_SIZE, BRAND_LOGO_SIZE],
            radius=BRAND_LOGO_SIZE // 3, fill=255)
        canvas.paste(logo, (x, y), mask)
        x += BRAND_LOGO_SIZE + BRAND_PAD_X // 2

    # 竖排双行：小字(品牌副标)在上, 大字(品牌名)在下
    if brand_sublabel:
        sw = draw.textbbox((0, 0), brand_sublabel, font=font_sublabel)[2]
        draw.text((x, y), brand_sublabel, fill=accent, font=font_sublabel)
        sy = y + font_sublabel.size + BRAND_TEXT_GAP
    else:
        sy = y
    if brand_name:
        draw.text((x, sy), brand_name, fill=(255, 255, 255), font=font_brand)


# ══════════════════════════════════════════════════════════════════
#  Event badge (EVENT01 中文标题，纯文字堆叠)
# ══════════════════════════════════════════════════════════════════

def _draw_event_badge(canvas, draw, y: int,
                      enum_label: str, section_title: str,
                      font_enum, font_sec,
                      accent: tuple[int, int, int],
                      border_color: tuple[int, int, int],
                      text_color: tuple[int, int, int]) -> tuple[int, int]:
    """纯文字堆叠样式：小号 EVENT0X 居中在上，大号加粗中文标题居中在下。
    无背景框/无描边，让底部装饰背景直接透出。返回 (y_after, 水平中心x)。"""
    enum_gap = 10

    ew = draw.textbbox((0, 0), enum_label, font=font_enum)[2]
    ex = (CANVAS_W - ew) // 2
    ey = y
    draw.text((ex, ey), enum_label, fill=accent, font=font_enum)

    tw = draw.textbbox((0, 0), section_title, font=font_sec)[2]
    sx = (CANVAS_W - tw) // 2
    sy = ey + font_enum.size + enum_gap
    draw.text((sx, sy), section_title, fill=border_color, font=font_sec)

    return sy + font_sec.size, CANVAS_W // 2


# ══════════════════════════════════════════════════════════════════
#  Wave divider (区块间水波分隔条)
# ══════════════════════════════════════════════════════════════════

def _draw_wave_divider(canvas, y: int, color: tuple[int, int, int], alpha: int = 40) -> None:
    """在 y 位置画一条水波分隔线（固定采样点 polygon），不增加画布高度。"""
    w = CANVAS_W
    h = WAVE_HEIGHT
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(overlay)
    step = w / (WAVE_SAMPLE_COUNT - 1)
    wave = []
    for i in range(WAVE_SAMPLE_COUNT):
        vx = int(i * step)
        vy = int(2 + 6 * (1 if (i % 2 == 0) else -1))
        wave.append((vx, vy))
    wave.append((w, h))
    wave.append((0, h))
    ld.polygon(wave, fill=(*color, alpha))
    canvas.paste(overlay, (0, y), overlay)


# ══════════════════════════════════════════════════════════════════
#  Transition banner prompts (区块间 AI 生图全宽分割条)
# ══════════════════════════════════════════════════════════════════

_TRANSITION_BANNER_PROMPTS = [
    # 0: KV hero → 活动时间
    (
        "A wide panoramic transition strip bridging the hero artwork to an activity timeline. "
        "Subtle countdown motifs, soft calendar glyphs, golden star sparkles, and prize ribbon "
        "accents flowing from left to right. "
        "Color palette harmonizes with the hero art: deep blues, mystical purples, and warm gold highlights. "
        "Smooth horizontal gradient, no hard edges, cinematic lighting, ultra-wide 1920x450 banner format."
    ),
    # 1: 活动时间 → 参与方法
    (
        "A wide panoramic transition strip from activity schedule to how-to-participate steps. "
        "Flowing guide arrows, subtle device outlines, soft glowing path lines leading forward. "
        "Interwoven with floating particles and gentle geometric shapes. "
        "Color palette harmonizes with the activity timeline section: cool blues, teal accents, and warm gold highlights. "
        "Smooth horizontal gradient, cinematic lighting, ultra-wide 1920x450 banner format."
    ),
    # 2: 参与方法 → 奖品展示
    (
        "A wide panoramic transition strip from participation steps to winner highlights showcase. "
        "Gleaming treasure chests, prize ribbon banners, floating gift boxes, and celebration confetti "
        "emerging from the flow. "
        "Color palette harmonizes with the participation section: warm golds, amber oranges, and cool teal contrasts. "
        "Smooth horizontal gradient, cinematic lighting, ultra-wide 1920x450 banner format."
    ),
    # 3: 奖品展示 → 游戏介绍
    (
        "A wide panoramic transition strip from winner highlights into the game world lore. "
        "Epic landscape silhouettes, floating game icons, magical portals, and atmospheric depth. "
        "Color palette harmonizes with the prize section: rich golds, deep indigos, and ethereal cyan glows. "
        "Smooth horizontal gradient, cinematic lighting, ultra-wide 1920x450 banner format."
    ),
]


def _build_transition_banner_prompt(idx: int, design: dict) -> str:
    """根据过渡位置索引和设计系统，构建单条 transition banner 的生图 prompt。"""
    base_prompt = _TRANSITION_BANNER_PROMPTS[min(idx, len(_TRANSITION_BANNER_PROMPTS) - 1)]

    style_info = design["_style_info"]
    art_style_en = {
        "realistic": "photorealistic cinematic style",
        "anime": "Japanese anime cel style",
        "cyberpunk": "cyberpunk neon aesthetic",
        "guofeng_chinese": "Chinese guofeng ink-painting fusion",
        "painterly": "painterly concept art with visible brush strokes",
        "Q_style": "chibi Q-style cute illustrations",
        "sci_fi": "sci-fi futuristic technology aesthetic",
        "fantasy": "high fantasy epic style",
        "minimalist": "minimalist clean geometric design",
        "dark_gothic": "dark gothic ornate style",
        "pop_art": "pop art bold graphic comic style",
        "cel_shaded": "cel-shaded toon render style",
    }.get(style_info.get("art_style", ""), "fantasy game art style")

    color_mood_en = {
        "warm_gold_orange": "warm gold-orange-amber tones",
        "cool_blue_purple": "cool blue-cyan-purple tones",
        "high_saturation_clash": "vivid high-saturation colors",
        "muted_earth": "muted earthy desaturated tones",
        "monochrome": "monochrome single-hue scheme",
        "pastel_soft": "soft pastel dreamy palette",
        "neon_dark": "dark with neon accent pops",
        "split_complementary": "dual-color split-complementary scheme",
    }.get(style_info.get("color_mood", ""), "cool blue-purple gradient")

    a1 = design["_theme"].get("accent_bright", "#4488FF")
    a2 = design["_theme"].get("accent_bright_alt", "#88CCFF")
    bg_hex = design["_theme"].get("bg_page", "#0A0A1A")

    return (
        f"{base_prompt} "
        f"Art style: {art_style_en}. "
        f"Color mood: {color_mood_en}. "
        f"Accent colors: {a1}, {a2}. "
        f"Base background: {bg_hex}. "
        f"Ultra-wide seamless decorative banner strip, 1920x450px. "
        f"No text, no logos, no characters, no faces. "
        f"High quality, 8k, masterpiece."
    )


def _make_transition_fallback(design: dict) -> Image.Image:
    """生成纯色渐变兜底过渡条（无需 API 调用）。"""
    h = COMBINED_BANNER_H
    w = CANVAS_W
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    accent_bright = design["accent_bright"]
    accent_bright_alt = design["accent_bright_alt"]
    bg_page = design["bg_page"]
    base_top = _mix_rgb(bg_page, _mix_rgb(accent_bright, accent_bright_alt, 0.5), 0.4)
    base_bot = _mix_rgb(bg_page, _mix_rgb(accent_bright_alt, accent_bright, 0.3), 0.35)
    for i in range(h):
        t = i / max(1, h - 1)
        c = _mix_rgb(base_top, base_bot, t)
        draw.line([(0, i), (w, i)], fill=(*c, 255))
    return img


def _generate_transition_banners(design: dict, out_dir: Path, count: int = 4) -> list[Image.Image | None]:
    """生成 count 条 transition banner 图片（顺序调用 API）。已存在则直接复用，不重新生成。"""
    from scripts.changtu.micu_image_gen import run_micu_t2i
    banners: list[Image.Image | None] = []
    for idx in range(count):
        out_path = out_dir / f"_email_transition_{idx}.png"
        raw_path = out_dir / f"_email_transition_{idx}.raw.png"

        # ── 缓存命中：直接读取已有文件 ──
        for cached in (out_path, raw_path):
            if cached.is_file() and cached.stat().st_size > 10000:
                try:
                    img = Image.open(cached).convert("RGBA")
                    banners.append(img)
                    print(f"[邮件长图/过渡Banner] [{idx+1}/{count}] 复用缓存: {cached.name}", flush=True)
                    break
                except Exception:
                    pass
        else:
            # ── 未命中：调用 API 生成 ──
            prompt = _build_transition_banner_prompt(idx, design)
            print(f"[邮件长图/过渡Banner] 生成 [{idx+1}/{count}] ({CANVAS_W}×{COMBINED_BANNER_H}px)...", flush=True)
            try:
                raw_result = run_micu_t2i(
                    prompt=prompt,
                    output_path=raw_path,
                    width=CANVAS_W,
                    height=COMBINED_BANNER_H,
                )
                img = Image.open(raw_result).convert("RGBA")
                img.save(out_path)
                banners.append(img)
                print(f"[邮件长图/过渡Banner] [{idx+1}/{count}] 完成", flush=True)
            except Exception as e:
                print(f"[邮件长图/过渡Banner] [{idx+1}/{count}] 失败({e})，渐变兜底", flush=True)
                banners.append(_make_transition_fallback(design))
    return banners


def _draw_combined_section_banner(canvas, x: int, y: int, w: int,
                                   title: str, enum_label: str,
                                   banner_img: Image.Image | None,
                                   design: dict,
                                   font_sec: ImageFont.FreeTypeFont,
                                   font_enum: ImageFont.FreeTypeFont,
                                   layout: str = "text_left",
                                   subtitle: str = "") -> int:
    """AI 装饰背景 + 分区标题合并为一条 Banner。
    layout: "text_left" (文字左 + 装饰右) | "text_center" (文字居中 + 两侧装饰)
    subtitle: 副标题文字；为空则不渲染副标题行，主标题在 banner 高度内垂直居中。
    背景始终铺满画布全宽 (CANVAS_W)，文字区使用 x/w 定位。
    """
    h = COMBINED_BANNER_DISPLAY_H

    # ── 1. AI 装饰背景（铺满画布全宽，居中裁剪到显示高度） ──
    img = banner_img if banner_img is not None else _make_transition_fallback(design)
    if img.height > h:
        crop_top = (img.height - h) // 2
        img = img.crop((0, crop_top, CANVAS_W, crop_top + h))
    elif img.size != (CANVAS_W, h):
        img = img.resize((CANVAS_W, h), Image.Resampling.LANCZOS)
    rgba_bg = img.convert("RGBA")
    canvas.paste(rgba_bg, (0, y), rgba_bg)

    # ── 2. 色彩衍生 ──
    bg_page = design["bg_page"]
    accent_bright = design["accent_bright"]
    accent_primary = design["_theme"].get("accent_primary", "")
    vp = _boost_vivid(_hex_rgb(accent_primary) if accent_primary else accent_bright,
                      sat_mul=1.28, val_mul=1.18)
    pop = _boost_vivid(accent_bright, sat_mul=1.22, val_mul=1.15)

    # ── 3. 文字区域遮罩已移除 ──
    # 原来的暗色矩形遮罩（alpha=90）视觉上显示为一块明显的黑色底板。
    # 现在改为仅靠文字描边保证可读性，不再叠加面积遮罩。
    draw = ImageDraw.Draw(canvas)

    # ── 4. ENUM 标签（为空则跳过） ──
    shadow_c = (0, 0, 0, 200)
    enum_c = _lighten(pop, 0.5)
    if enum_label:
        ew = draw.textbbox((0, 0), enum_label, font=font_enum)[2]
        if layout == "text_left":
            ex = x + (text_zone_w - ew) // 2
        else:
            ex = x + (w - ew) // 2
        ey = y + (h - 60 - 8 - 100) // 2
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)):
            draw.text((ex + dx, ey + dy), enum_label, fill=shadow_c, font=font_enum)
        draw.text((ex, ey), enum_label, fill=enum_c, font=font_enum)
        title_top = ey + font_enum.size + 6
    else:
        # 无 ENUM 标签时，title 在 banner 高度内垂直居中
        title_top = None  # 在下方计算

    # ── 6. 分区标题 ──
    title_c = (255, 255, 255)
    tw = draw.textbbox((0, 0), title, font=font_sec)[2]
    th = draw.textbbox((0, 0), title, font=font_sec)[3]
    if layout == "text_left":
        tx = x + (text_zone_w - tw) // 2
    else:
        tx = x + (w - tw) // 2
    ty = title_top if title_top is not None else y + (h - th) // 2
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3), (3, 3), (-3, 3), (3, -3)):
        draw.text((tx + dx, ty + dy), title, fill=shadow_c, font=font_sec)
    draw.text((tx, ty), title, fill=title_c, font=font_sec)

    # ── 7. 副标题（有值才渲染） ──
    if subtitle:
        sub_c = (255, 255, 255, 210)
        sw = draw.textbbox((0, 0), subtitle, font=font_enum)[2]
        if layout == "text_left":
            sx = x + (text_zone_w - sw) // 2
        else:
            sx = x + (w - sw) // 2
        sy = ty + th + 12  # 主副标题间距
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            draw.text((sx + dx, sy + dy), subtitle, fill=shadow_c, font=font_enum)
        draw.text((sx, sy), subtitle, fill=sub_c, font=font_enum)

    return h


def _draw_section_container(canvas, x: int, y: int, w: int, h: int,
                            design: dict) -> None:
    """根据 Vision card_style 绘制统一分区容器背景 + 发光边框。"""
    card_style = design["card_style"]
    border = design["border_color"]

    if card_style in ("dark_glass", "light_glass"):
        fill_color = design["bg_card_dark"] if "dark" in card_style else design["bg_card_light"]
        bg = Image.new("RGBA", (w, h), (*fill_color, 40))
        canvas.paste(bg, (x, y), bg)
    elif card_style == "solid_dark":
        bg = Image.new("RGBA", (w, h), (*design["bg_card_dark"], 120))
        canvas.paste(bg, (x, y), bg)
    elif card_style == "solid_light":
        bg = Image.new("RGBA", (w, h), (*design["bg_card_light"], 180))
        canvas.paste(bg, (x, y), bg)
    # card_style == "geometric_panels" 等后续风格在此扩展


def _draw_event_section_banner(canvas, x: int, y: int, w: int,
                               title: str, enum_label: str,
                               design: dict,
                               font_sec: ImageFont.FreeTypeFont,
                               font_enum: ImageFont.FreeTypeFont) -> int:
    """移植自战报的炫彩分区栏头：渐变底 + 半调网点 + 椭圆辉光 + 顶部胶带条 + 上下描边。
    无人物斜切槛（邮件长图没有角色素材），标题/枚举标签居中叠加描边。
    返回 banner 实际占用高度。"""
    theme = design["_theme"]
    h = SECTION_BANNER_H

    bg_page = design["bg_page"]
    accent_bright = design["accent_bright"]
    accent_bright_alt = design["accent_bright_alt"]
    accent_primary = design["_theme"].get("accent_primary", "")
    vp = _boost_vivid(_hex_rgb(accent_primary) if accent_primary else accent_bright,
                      sat_mul=1.28, val_mul=1.18)
    vs = _boost_vivid(accent_bright_alt, sat_mul=1.24, val_mul=1.16)
    pop = _boost_vivid(accent_bright, sat_mul=1.22, val_mul=1.15)

    # 逐行竖向渐变底
    banner_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(banner_layer)
    base_top = _mix_rgb(bg_page, _mix_rgb(vp, pop, 0.55), 0.52)
    base_bot = _mix_rgb(bg_page, _mix_rgb(vs, vp, 0.52), 0.48)
    for i in range(h):
        t = i / max(1, h - 1)
        c = _mix_rgb(base_top, base_bot, t)
        ld.line([(0, i), (w, i)], fill=(*c, 255))

    # 半调网点两层
    _draw_halftone_band(ld, (0, 0, w, h), _mix_rgb(vp, pop, 0.45), dot=5, alpha=90)
    _draw_halftone_band(ld, (0, 0, w, h), _mix_rgb(vs, pop, 0.55), dot=9, alpha=50)

    # 中心辉光（两个椭圆）
    glow_cx, glow_cy = w // 2, int(h * 0.55)
    ld.ellipse([glow_cx - int(w * 0.45), glow_cy - 80, glow_cx + int(w * 0.45), glow_cy + 80],
               fill=(*_lighten(vp, 0.32), 90))
    ld.ellipse([glow_cx - int(w * 0.22), glow_cy - 36, glow_cx + int(w * 0.22), glow_cy + 36],
               fill=(*_lighten(pop, 0.2), 60))

    # 顶部胶带条（警示斜纹）
    tape_h = SECTION_BANNER_TOP_TAPE_H
    for ii in range(0, tape_h):
        c = vp if (ii // 2) % 2 == 0 else pop
        ld.line([(0, ii), (w, ii)], fill=(*c, 255))
    ld.line([(0, tape_h), (w, tape_h)], fill=(0, 0, 0, 220), width=2)

    # 上下描边线
    ld.line([(0, 1), (w, 1)], fill=(*vp, 255), width=3)
    ld.line([(0, h - 2), (w, h - 2)], fill=(*_lighten(pop, 0.1), 255), width=2)

    # 贴到主画布
    canvas.paste(banner_layer, (x, y), banner_layer)

    # 标题文字（带描边保证在炫彩底上可读）
    draw = ImageDraw.Draw(canvas)
    shadow_c = _darken(_mix_rgb(vp, bg_page, 0.6), 0.5)
    title_c = (255, 255, 255)

    # enum_label（小字，居中）
    ew = draw.textbbox((0, 0), enum_label, font=font_enum)[2]
    ex = x + (w - ew) // 2
    ey = y + tape_h + 10
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        draw.text((ex + dx, ey + dy), enum_label, fill=shadow_c, font=font_enum)
    draw.text((ex, ey), enum_label, fill=_lighten(pop, 0.5), font=font_enum)

    # section title（大字，居中，多重描边）
    tw = draw.textbbox((0, 0), title, font=font_sec)[2]
    tx = x + (w - tw) // 2
    ty = ey + font_enum.size + 8
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2)):
        draw.text((tx + dx, ty + dy), title, fill=shadow_c, font=font_sec)
    draw.text((tx, ty), title, fill=title_c, font=font_sec)

    return h


# ══════════════════════════════════════════════════════════════════
#  EVENT01: 活动时间 + 圆形图标网格（去卡片化）
# ══════════════════════════════════════════════════════════════════

def _draw_date_line(canvas, draw, y: int, event_date: str,
                    font_date, accent: tuple[int, int, int],
                    text_primary: tuple[int, int, int]) -> int:
    """Draw a date line like 2026/7/6-2026/10/10, return y_after."""
    if not event_date.strip():
        return y
    content_w = CANVAS_W - SECTION_PAD_LR * 2
    label = "活动时间："
    label_w = draw.textbbox((0, 0), label, font=font_date)[2]
    date_w = draw.textbbox((0, 0), event_date, font=font_date)[2]
    total_w = label_w + date_w
    sx = (CANVAS_W - total_w) // 2
    sy = y + SECTION_PAD_TOP // 2
    if sx < SECTION_PAD_LR:
        sx = SECTION_PAD_LR
    draw.text((sx, sy), label, fill=accent, font=font_date)
    draw.text((sx + label_w, sy), event_date, fill=text_primary, font=font_date)
    return sy + _line_height(font_date)


def _draw_circular_icon_grid(canvas, draw, y: int,
                             prizes: list[tuple[str, Image.Image]],
                             font_name,
                             accent: tuple[int, int, int],
                             bg_card: tuple[int, int, int],
                             border_color: tuple[int, int, int],
                             text_secondary: tuple[int, int, int]) -> int:
    """Draw prizes as circular icons in a grid. 去卡片化：无背景/无描边/无投影，纯圆形 icon + 底部文字。"""
    if not prizes:
        return y
    content_w = CANVAS_W - SECTION_PAD_LR * 2
    rows = _prize_rows(len(prizes))
    max_row = max(rows)
    card_w = (content_w - (max_row - 1) * CARD_GAP) // max_row
    icon_size = min(card_w - CARD_IMG_PAD * 2, 320)
    name_h = CARD_NAME_H
    card_h = icon_size + CARD_IMG_PAD + name_h

    cy = y
    idx = 0
    for row_items in rows:
        total_w = row_items * (card_w + CARD_GAP) - CARD_GAP
        rx = (CANVAS_W - total_w) // 2
        for _ in range(row_items):
            if idx >= len(prizes):
                break
            name, pimg = prizes[idx]
            # circular clip
            icon_img = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
            mask = Image.new("L", (icon_size, icon_size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, icon_size, icon_size], fill=255)
            fitted = _fit_trimmed(pimg, icon_size, icon_size)
            icon_img.paste(fitted, (0, 0), mask)
            # icon centered — no card bg, no shadow, no border
            ix = rx + (card_w - icon_size) // 2
            iy = cy + CARD_IMG_PAD
            canvas.paste(icon_img, (ix, iy), icon_img)
            # name below
            name_w = draw.textbbox((0, 0), name, font=font_name)[2]
            nx = rx + (card_w - name_w) // 2
            ny = iy + icon_size + (name_h - font_name.size) // 2
            if name_w > card_w - 8:
                while name_w > card_w - 8 and len(name) > 1:
                    name = name[:-1]
                    name_w = draw.textbbox((0, 0), name + "...", font=font_name)[2]
                name += "..."
                nx = rx + (card_w - name_w) // 2
            draw.text((nx, ny), name, fill=text_secondary, font=font_name)
            rx += card_w + CARD_GAP
            idx += 1
        cy += card_h + CARD_GAP
    return cy


# ══════════════════════════════════════════════════════════════════
#  Device frame (截图模拟浏览器/应用窗口)
# ══════════════════════════════════════════════════════════════════

def _draw_device_frame(canvas, x: int, y: int, w: int, h: int,
                       border_color: tuple[int, int, int],
                       bg_card: tuple[int, int, int]) -> None:
    """给截图区域绘制模拟窗口框：顶部标题栏 + 三个圆点 + 圆角外框。"""
    draw = ImageDraw.Draw(canvas)
    frame_h = h + DEVICE_TITLEBAR_H
    bx, by = x, y

    # 外框填充
    outer_fill = Image.new("RGBA", (w, frame_h), (*bg_card, 230))
    canvas.paste(outer_fill, (bx, by), outer_fill)
    # _draw_neon_border(canvas, bx, by, w, frame_h, border_color,
    #                   radius=DEVICE_FRAME_RADIUS, glow_layers=4, line_width=DEVICE_BORDER_WIDTH)

    # 标题栏底色
    title_bg = Image.new("RGBA", (w, DEVICE_TITLEBAR_H), (*_darken(bg_card, 0.1), 200))
    # 标题栏顶部圆角
    title_mask = Image.new("L", (w, DEVICE_TITLEBAR_H), 0)
    ImageDraw.Draw(title_mask).rounded_rectangle(
        [0, 0, w, DEVICE_TITLEBAR_H + DEVICE_FRAME_RADIUS],
        radius=DEVICE_FRAME_RADIUS, fill=255)
    title_bg.putalpha(title_mask.point(lambda p: p))
    canvas.paste(title_bg, (bx, by), title_bg)

    # 三个圆点（红/黄/绿）
    dot_y = by + DEVICE_TITLEBAR_H // 2
    colors = [(237, 106, 94), (245, 191, 79), (97, 197, 84)]
    for ci, c in enumerate(colors):
        dx = bx + 20 + ci * DEVICE_DOT_GAP
        draw.ellipse(
            [dx - DEVICE_DOT_R, dot_y - DEVICE_DOT_R,
             dx + DEVICE_DOT_R, dot_y + DEVICE_DOT_R],
            fill=c)

    # 把截图贴到标题栏下方区域
    screenshot_region = (bx, by + DEVICE_TITLEBAR_H, bx + w, by + frame_h)
    # 截图由调用方在外部某次 paste 中处理，这里只画框


# ══════════════════════════════════════════════════════════════════
#  EVENT02: 参与方法 (纵向堆叠：文字居中在上 + 截图在下 + 设备边框)
# ══════════════════════════════════════════════════════════════════

def _draw_method_section(canvas, draw, y: int,
                         method_texts: list[str],
                         screenshots: list[tuple[str, Image.Image]],
                         font_desc,
                         accent: tuple[int, int, int],
                         bg_card: tuple[int, int, int],
                         border_color: tuple[int, int, int],
                         text_secondary: tuple[int, int, int],
                         skip_ocr: bool = False) -> int:
    """EVENT02: 纵向堆叠，每项文字整行居中在上，截图在下（套设备边框），无磨砂框包裹。"""
    if not method_texts and not screenshots:
        return y
    content_w = CANVAS_W - SECTION_PAD_LR * 2
    text_w = int(content_w * 0.85)
    img_w = int(content_w * 0.90)

    cy = y
    count = max(len(method_texts), len(screenshots))
    for i in range(count):
        if i < len(method_texts):
            text = method_texts[i]
            lines = _wrap_text(draw, text, font_desc, text_w)
            lh = _line_height(font_desc)
            text_h = lh * len(lines)

            ty = cy
            for li, line in enumerate(lines):
                line_w = draw.textbbox((0, 0), line, font=font_desc)[2]
                lx = (CANVAS_W - line_w) // 2
                draw.text((lx, ty + li * lh), line, fill=text_secondary, font=font_desc)
            cy = ty + text_h + CARD_GAP

        # 截图 + 设备边框
        shot_img = screenshots[i][1] if i < len(screenshots) else None
        if shot_img:
            shot_h = int(img_w * shot_img.height / max(shot_img.width, 1))
            frame_h = shot_h + DEVICE_TITLEBAR_H
            ix = (CANVAS_W - img_w) // 2

            # 画设备外框
            _draw_device_frame(canvas, ix, cy, img_w, shot_h, border_color, bg_card)

            # 把截图贴到标题栏下方
            sr = shot_img.resize((img_w, shot_h), Image.Resampling.LANCZOS)
            # 截图底部保留圆角裁切
            sm = Image.new("L", (img_w, shot_h), 0)
            # 底部两个角做圆角
            rd = ImageDraw.Draw(sm)
            rd.rectangle([DEVICE_FRAME_RADIUS, 0, img_w - DEVICE_FRAME_RADIUS, shot_h], fill=255)
            rd.rectangle([0, 0, img_w, shot_h - DEVICE_FRAME_RADIUS], fill=255)
            rd.pieslice([0, shot_h - DEVICE_FRAME_RADIUS * 2, DEVICE_FRAME_RADIUS * 2, shot_h],
                        start=180, end=270, fill=255)
            rd.pieslice([img_w - DEVICE_FRAME_RADIUS * 2, shot_h - DEVICE_FRAME_RADIUS * 2, img_w, shot_h],
                        start=270, end=360, fill=255)
            ssr = sr.convert("RGBA") if sr.mode != "RGBA" else sr
            ss = Image.composite(ssr, Image.new("RGBA", (img_w, shot_h), (0, 0, 0, 0)), sm)
            canvas.paste(ss, (ix, cy + DEVICE_TITLEBAR_H), ss)

            # OCR 识别截图文字，并在截图下方渲染（已提供文字描述时跳过）
            ocr_text = "" if skip_ocr else _ocr_screenshot(shot_img)
            if ocr_text:
                # 计算文字区域宽度（留白 10%）
                ocr_w = int(img_w * 0.85)
                ocr_lines = _wrap_text(draw, ocr_text, font_desc, int(img_w * 0.85))
                lh = _line_height(font_desc)
                ocr_h = lh * len(ocr_lines)
                # 文字居中，在截图下方留 12px 间距
                ocr_y = cy + DEVICE_TITLEBAR_H + shot_h + 12
                for li, line in enumerate(ocr_lines):
                    line_w = draw.textbbox((0, 0), line, font=font_desc)[2]
                    lx = (CANVAS_W - line_w) // 2
                    draw.text((lx, ocr_y + li * _line_height(font_desc)), line, fill=text_secondary, font=font_desc)
                cy = ocr_y + ocr_h + CARD_GAP
            else:
                cy += frame_h + CARD_GAP
        else:
            cy += CARD_GAP
    return cy


# ══════════════════════════════════════════════════════════════════
#  EVENT03: 往期中奖 (方形卡片网格，浅色减重版)
# ══════════════════════════════════════════════════════════════════

def _draw_history_cards(canvas, draw, y: int,
                        items: list[tuple[str, Image.Image]],
                        font_name,
                        accent: tuple[int, int, int],
                        bg_card: tuple[int, int, int],
                        border_color: tuple[int, int, int],
                        text_secondary: tuple[int, int, int]) -> int:
    """EVENT03: 浅色卡片 + 柔和投影，无粗描边。"""
    if not items:
        return y
    content_w = CANVAS_W - SECTION_PAD_LR * 2
    rows = _prize_rows(len(items))
    max_row = max(rows)
    card_w = (content_w - (max_row - 1) * CARD_GAP) // max_row
    img_ratio = 0.72
    img_h = int(card_w * img_ratio)
    name_h = CARD_NAME_H
    card_h = img_h + name_h

    cy = y
    idx = 0
    for row_items in rows:
        total_w = row_items * (card_w + CARD_GAP) - CARD_GAP
        rx = (CANVAS_W - total_w) // 2
        for _ in range(row_items):
            if idx >= len(items):
                break
            name, pimg = items[idx]
    # 柔和投影（已删除）
    # _drop_shadow(canvas, draw, rx, cy, card_w, card_h, CARD_RADIUS)
    # 霓虹发光边框（卡片在分区容器内，无独立底色）
    # _draw_neon_border(canvas, rx, cy, card_w, card_h, border_color,
    #                   radius=CARD_RADIUS, glow_layers=4, line_width=1)
            # image
            fitted = _fit_trimmed(pimg, card_w - CARD_IMG_PAD * 2, img_h - CARD_IMG_PAD * 2)
            fw, fh = fitted.size
            fx = rx + (card_w - fw) // 2
            fy = cy + (img_h - fh) // 2
            canvas.paste(fitted, (fx, fy), fitted)
            # name bar
            bar = Image.new("RGBA", (card_w, name_h), (0, 0, 0, 0))
            bp = bar.load()
            for ppx in range(name_h):
                a_val = max(0, 120 - int(ppx * 120 / name_h))
                for ppy in range(card_w):
                    bp[ppy, ppx] = (*border_color, a_val)
            canvas.paste(bar, (rx, cy + img_h), bar)
            # name text
            text = name
            nw = draw.textbbox((0, 0), text, font=font_name)[2]
            if nw > card_w - 8:
                while nw > card_w - 8 and len(text) > 1:
                    text = text[:-1]
                    nw = draw.textbbox((0, 0), text + "...", font=font_name)[2]
                text += "..."
            nx = rx + (card_w - nw) // 2
            ny = cy + img_h + (name_h - font_name.size) // 2
            draw.text((nx, ny), text, fill=text_secondary, font=font_name)
            rx += card_w + CARD_GAP
            idx += 1
        cy += card_h + CARD_GAP
    return cy


# ══════════════════════════════════════════════════════════════════
#  EVENT04: 游戏介绍 (磨砂框文字卡)
# ══════════════════════════════════════════════════════════════════

def _draw_intro_section(canvas, draw, y: int,
                        intro_text: str,
                        font_intro,
                        bg_card: tuple[int, int, int],
                        border_color: tuple[int, int, int],
                        text_secondary: tuple[int, int, int]) -> int:
    """EVENT04: 纯文字渲染（容器由外层 _draw_section_container 统一接管）。"""
    if not intro_text.strip():
        return y
    content_w = CANVAS_W - SECTION_PAD_LR * 2
    text_box_w = content_w - TEXT_BOX_PAD_X * 2
    lines = _wrap_text(draw, intro_text, font_intro, text_box_w)
    lh = _line_height(font_intro)
    text_h = lh * len(lines)
    box_h = text_h + TEXT_BOX_PAD_Y * 2
    bx = SECTION_PAD_LR
    by = y

    ty = by + (box_h - text_h) // 2
    for li, line in enumerate(lines):
        draw.text((bx + TEXT_BOX_PAD_X, ty + li * lh), line,
                  fill=text_secondary, font=font_intro)
    return by + box_h


# ══════════════════════════════════════════════════════════════════
#  KV title
# ══════════════════════════════════════════════════════════════════

def _draw_kv_title(draw, kv_display_h: int,
                   main_title: str, sub_title: str,
                   font_title) -> None:
    """在 KV 上绘制主副标题，使用同字体不同号，带白字黑描边。"""
    sub_bottom = kv_display_h - 80
    text_y = sub_bottom - KV_SUBTITLE_SIZE - KV_TITLE_SUB_GAP - KV_TITLE_SIZE
    
    # 副标题字体：同主标题字体，84pt
    font_sub = _load_font(font_title, KV_SUBTITLE_SIZE)
    
    # 白字黑描边颜色
    title_c = (255, 255, 255)
    shadow_c = (0, 0, 0, 200)
    
    # ── 主标题 ──
    fw = draw.textbbox((0, 0), main_title, font=font_title)[2]
    tx = (CANVAS_W - fw) // 2
    # 8方向描边
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3), (3, 3), (-3, 3), (3, -3)):
        draw.text((tx + dx, text_y + dy), main_title, fill=(0, 0, 0, 200), font=font_title)
    draw.text((tx, text_y), main_title, fill=title_c, font=font_title)

    # ── 副标题 ──
    sy = text_y + KV_TITLE_SIZE + KV_TITLE_SUB_GAP
    fw2 = draw.textbbox((0, 0), sub_title, font=font_sub)[2]
    tx2 = (CANVAS_W - fw2) // 2
    # 8方向描边
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
        draw.text((tx2 + dx, sy + dy), sub_title, fill=(0, 0, 0, 200), font=font_sub)
    draw.text((tx2, sy), sub_title, fill=title_c, font=font_sub)


# ══════════════════════════════════════════════════════════════════
#  KV Vision 风格分析 (OpenAI chat/completions protocol)
# ══════════════════════════════════════════════════════════════════

def _vision_analyze_kv_style(kv_path: Path, out_dir: Path) -> dict:
    """使用 OpenAI chat/completions 协议分析 KV 风格，缓存到 JSON。"""
    cache = out_dir / "kv_style.json"
    if cache.is_file():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    api_key = ""
    base_url = ""
    vision_model = "gpt-4o"

    # 按优先级选择 key+base_url 组合
    # 1. MoxinGemini（当前主力 Vision key）
    moxingemini_key = os.environ.get("MOXINGEMINI_API_KEY", "").strip()
    if moxingemini_key and moxingemini_key.startswith("sk-"):
        api_key = moxingemini_key
        base_url = os.environ.get("MOXINGEMINI_BASE_URL", "https://www.moxin.studio").strip()
        vision_model = os.environ.get("MOXINGEMINI_MODEL", "gpt-4o").strip()
    # 2. MoxinGPT（t2i key，也支持 Vision）
    if not api_key:
        moxingpt_key = os.environ.get("MOXINGPT_API_KEY", "").strip()
        if moxingpt_key and moxingpt_key.startswith("sk-"):
            api_key = moxingpt_key
            base_url = os.environ.get("MOXINGPT_BASE_URL", "https://www.moxin.studio").strip()
            vision_model = os.environ.get("MOXINGPT_MODEL", "gpt-4o").strip()
    # 3. PackyGPT
    if not api_key:
        packygpt_key = os.environ.get("PACKYGPT_API_KEY", "").strip()
        if packygpt_key and packygpt_key.startswith("sk-"):
            api_key = packygpt_key
            base_url = "https://www.packyapi.com"
    # 4. MicuGemini / MicuAPI
    if not api_key:
        micu_key = os.environ.get("MICUGEMINI_API_KEY", os.environ.get("MICUAPI_API_KEY", "")).strip()
        if micu_key and micu_key.startswith("sk-"):
            api_key = micu_key
            base_url = "https://www.micuapi.ai"
    # 5. Xingchen 系列
    if not api_key:
        for key_var in ("XINGCHENGGPT_API_KEY", "XINGCHENGEMINI_API_KEY", "PACKY7S_API_KEY", "PACKY_API_KEY", "GEMINI_API_KEY"):
            k = os.environ.get(key_var, "").strip()
            if k and k.startswith("sk-"):
                api_key = k
                break

    if not api_key:
        print("[邮件长图/Vision] 未找到可用的 Vision Key，使用默认风格描述", flush=True)
        return _default_style_info()

    if not base_url:
        base_url = os.environ.get("GOOGLE_GEMINI_BASE_URL", "https://www.packyapi.com").strip()
    base_url = base_url.rstrip("/")

    # Encode KV image to base64
    with Image.open(kv_path) as im:
        im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        kv_b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = """You are a game art style analyst. Analyze this KV key visual image and output ONLY a JSON object (no markdown, no explanation):

{
  "art_style": "realistic | anime | cyberpunk | guofeng_chinese | painterly | Q_style | sci_fi | fantasy | minimalist | dark_gothic | pop_art | cel_shaded",
  "composition": "center_focus | asymmetric_left | asymmetric_right | symmetric | diagonal | scattered | radial | rule_of_thirds",
  "lighting": "bottom_spotlight | side_rim_light | soft_diffuse | hard_key_light | neon_glow | volumetric_god_rays | dramatic_chiaroscuro | flat_even",
  "mood": "epic_heroic | dark_mysterious | joyful_celebration | serene_narrative | intense_battle | futuristic_tech | magical_fantasy | cute_playful",
  "motifs": ["2-5 visual motifs, e.g. crystal, magic_circle, fire, tech_lines, ink_wash, neon_grid, particle_splash, energy_beam, hologram, smoke, water_ripple, mechanical_gear, feather, nebula"],
  "color_mood": "warm_gold_orange | cool_blue_purple | high_saturation_clash | muted_earth | monochrome | pastel_soft | neon_dark | split_complementary",
  "depth_style": "shallow_bokeh | deep_atmospheric | flat_graphic | layered_parallax",

  "background_tone": "very_dark | dark | medium | light | very_light -- judge the overall brightness of the image",
  "text_should_be": "light | dark -- should overlay text use white/light or black/dark color for readability",
  "frame_style": "glowing_neon | delicate_lines | geometric_panels | organic_curves -- what decorative border style matches this art",
  "frame_glow_color_name": "cool_blue | warm_gold | magenta_pink | cyan_teal | pure_white | amber_orange | soft_purple -- the glow/accent color for borders",
  "decor_elements": ["2-4 decorative element ideas derived from motifs, e.g. floating_crystal_shards, stardust_particles"],
  "sticker_ideas": ["1-2 cute mascot/sticker creature ideas that fit this style, e.g. small_glowing_crystal_sprite, nebula_wisp_creature"],
  "card_style": "dark_glass | light_glass | solid_dark | solid_light | minimal_border -- what material for info cards matches this art"
}"""

    body = {
        "model": vision_model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{kv_b64}"}}
        ]}],
        "temperature": 0.2,
        "max_tokens": 768,
    }

    url = f"{base_url}/v1/chat/completions"
    print(f"[邮件长图/Vision] POST {url} model={vision_model} key_prefix={api_key[:10]}...", flush=True)
    style_info = _default_style_info()

    def _resolve_vision_model(current_model: str) -> str:
        """如果 current_model 403，自动从 /v1/models 取第一个非生图文本模型的完整 ID。"""
        try:
            r_models = requests.get(f"{base_url}/v1/models",
                                    headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
            if r_models.status_code == 200:
                available = [m.get("id", "") for m in r_models.json().get("data", [])]
                for mid in available:
                    low = mid.lower()
                    if "image" not in low and "embedding" not in low:
                        print(f"[邮件长图/Vision] 自动选取模型: {mid}", flush=True)
                        return mid
        except Exception as e:
            print(f"[邮件长图/Vision] 查模型列表失败: {e}", flush=True)
        return current_model

    for attempt in range(3):
        try:
            body["model"] = vision_model
            r = requests.post(url, json=body, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }, timeout=180)
            if r.status_code == 403 and attempt == 0:
                print("[邮件长图/Vision] 403，尝试自动匹配可用模型...", flush=True)
                vision_model = _resolve_vision_model(vision_model)
                continue
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices") or []
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                m = re.search(r"\{[\s\S]*\}", content)
                if m:
                    style_info = json.loads(m.group())
                    break
        except Exception as e:
            detail = str(e)[:300]
            if hasattr(e, "response") and e.response is not None:
                try:
                    detail = f"HTTP {e.response.status_code}: {e.response.text[:200]} | {detail}"
                except Exception:
                    pass
            print(f"[邮件长图/Vision] 请求失败 (attempt {attempt+1}): {detail}", flush=True)
            if attempt == 0:
                time.sleep(2)

    # Cascade save: keep last 2 snapshots
    if style_info != _default_style_info():
        if cache.is_file():
            c1 = cache.with_suffix(".json.1")
            c2 = cache.with_suffix(".json.2")
            if c2.is_file():
                c2.unlink(missing_ok=True)
            if c1.is_file():
                c1.rename(c2)
            cache.rename(c1)
        cache.write_text(json.dumps(style_info, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"[邮件长图/Vision] art={style_info.get('art_style')} "
            f"bg={style_info.get('background_tone','?')} "
            f"frame={style_info.get('frame_style','?')} "
            f"card={style_info.get('card_style','?')} "
            f"text={style_info.get('text_should_be','?')} "
            f"stickers={style_info.get('sticker_ideas',[])} "
            f"motifs={style_info.get('motifs',[])}",
            flush=True,
        )
    else:
        print("[邮件长图/Vision] 未返回有效 JSON，使用默认风格描述", flush=True)

    return style_info


def _default_style_info() -> dict:
    return {
        "art_style": "fantasy",
        "composition": "center_focus",
        "lighting": "soft_diffuse",
        "mood": "epic_heroic",
        "motifs": [],
        "color_mood": "warm_gold_orange",
        "depth_style": "shallow_bokeh",
        "background_tone": "dark",
        "text_should_be": "light",
        "frame_style": "glowing_neon",
        "frame_glow_color_name": "cool_blue",
"decor_elements": [],
        "sticker_ideas": [],
        "card_style": "dark_glass",
    }


def _ocr_screenshot(img: Image.Image) -> str:
    """对单张截图进行 OCR 文字识别，复用 Vision API (chat/completions)。
    返回识别出的纯文本（无 Markdown/JSON/解释），失败返回空字符串。"""
    import io
    import base64
    import requests
    import os

    api_key = ""
    base_url = ""
    vision_model = "gpt-4o"

    moxingemini_key = os.environ.get("MOXINGEMINI_API_KEY", "").strip()
    if moxingemini_key and moxingemini_key.startswith("sk-"):
        api_key = moxingemini_key
        base_url = os.environ.get("MOXINGEMINI_BASE_URL", "https://www.moxin.studio").strip()
        vision_model = os.environ.get("MOXINGEMINI_MODEL", "gpt-4o").strip()
    if not api_key:
        moxingpt_key = os.environ.get("MOXINGPT_API_KEY", "").strip()
        if moxingpt_key and moxingpt_key.startswith("sk-"):
            api_key = os.environ.get("MOXINGPT_API_KEY", "").strip()
            base_url = os.environ.get("MOXINGPT_BASE_URL", "https://www.moxin.studio").strip()
            vision_model = os.environ.get("MOXINGPT_MODEL", "gpt-4o").strip()
    if not api_key:
        packygpt_key = os.environ.get("PACKYGPT_API_KEY", "").strip()
        if packygpt_key and packygpt_key.startswith("sk-"):
            api_key = os.environ.get("PACKYGPT_API_KEY", "").strip()
            base_url = "https://www.packyapi.com"
    if not api_key:
        micu_key = os.environ.get("MICUGEMINI_API_KEY", os.environ.get("MICUAPI_API_KEY", "")).strip()
        if micu_key and micu_key.startswith("sk-"):
            api_key = micu_key
            base_url = "https://www.micuapi.ai"

    if not api_key:
        print("[邮件长图/OCR] 未找到可用的 Vision Key，跳过 OCR", flush=True)
        return ""

    if not base_url:
        base_url = os.environ.get("GOOGLE_GEMINI_BASE_URL", "https://www.packyapi.com").strip()
    base_url = base_url.rstrip("/")

    # Encode image to base64
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    prompt = """请提取这张图片中的所有可见文字（中文/英文/数字/标点），按阅读顺序输出纯文本。
要求：
1. 仅输出识别到的文字内容，不要任何解释、标签、JSON、Markdown
2. 保持原文的段落结构和标点
3. 无文字时输出空行
4. 忽略图标、装饰性元素，只提取可读文字"""

    body = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
        ]}],
        "temperature": 0.0,
        "max_tokens": 1024,
    }

    url = f"{base_url}/v1/chat/completions"
    print(f"[邮件长图/OCR] POST {url} model=gpt-4o...", flush=True)

    try:
        r = requests.post(url, json=body, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }, timeout=60)
        r.raise_for_status()
        data = r.json()
        choices = data.get("choices") or []
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            text = content.strip()
            print(f"[邮件长图/OCR] 识别到 {len(text)} 字符", flush=True)
            return text
    except Exception as e:
        print(f"[邮件长图/OCR] 失败: {e}", flush=True)
    return ""


# ══════════════════════════════════════════════════════════════════
#  Design system (K-means 精确色 + Vision 语义 → 统一设计字典)
# ══════════════════════════════════════════════════════════════════
#  Design system (K-means 精确色 + Vision 语义 → 统一设计字典)
# ══════════════════════════════════════════════════════════════════

def _build_design_system(theme: dict, style_info: dict) -> dict:
    """融合 K-means 取色（精确 hex）和 Vision 分析（语义决策），返回设计系统字典。
    所有 _draw_* / _generate_* 函数统一从此字典取值，不再各自硬编码。"""
    bg_tone = style_info.get("background_tone", "dark")
    is_dark = bg_tone.startswith("very_dark") or bg_tone.startswith("dark")
    text_light = style_info.get("text_should_be", "light") == "light"

    # 精确颜色（K-means）
    bg_page_rgb = _hex_rgb(theme.get("bg_page", "#070514"))
    accent_bright_rgb = _hex_rgb(theme.get("accent_bright", "#344BCA"))
    accent_bright_alt_rgb = _hex_rgb(theme.get("accent_bright_alt", "#7298FD"))
    accent_primary_rgb = _hex_rgb(theme.get("accent_primary", "#3C4EB1"))
    bg_card_rgb = _hex_rgb(theme.get("bg_card", "#F2F2F2"))
    bg_card_dark_rgb = _hex_rgb(theme.get("bg_card_dark", "#1F1D2C"))

    # 文字颜色（Vision 语义决定亮/暗）
    if text_light:
        text_main = (255, 255, 255)
        text_secondary = (220, 220, 230)
    else:
        text_main = (40, 40, 50)
        text_secondary = (100, 100, 120)

    # 边框发光色（Vision frame_glow_color_name → 精确 hex）
    frame_glow_map = {
        "cool_blue": accent_bright_alt_rgb,
        "warm_gold": (255, 180, 60),
        "magenta_pink": (230, 80, 180),
        "cyan_teal": (60, 210, 210),
        "pure_white": (240, 240, 255),
        "amber_orange": (255, 160, 40),
        "soft_purple": (160, 120, 220),
    }
    border_color = frame_glow_map.get(
        style_info.get("frame_glow_color_name", "cool_blue"),
        accent_bright_alt_rgb,
    )

    # 卡片背景色（Vision card_style）
    card_style = style_info.get("card_style", "dark_glass")
    if "dark" in card_style:
        card_bg = bg_card_dark_rgb
        card_bg_alpha = 180
    else:
        card_bg = bg_card_rgb
        card_bg_alpha = 230

    return {
        # ── 精确颜色 ──
        "bg_page": bg_page_rgb,
        "accent_bright": accent_bright_rgb,
        "accent_bright_alt": accent_bright_alt_rgb,
        "accent_primary": accent_primary_rgb,
        "bg_card": card_bg,
        "bg_card_alpha": card_bg_alpha,
        "bg_card_light": bg_card_rgb,
        "bg_card_dark": bg_card_dark_rgb,
        "border_color": border_color,
        "text_primary": text_main,
        "text_secondary": text_secondary,
        # ── 语义 ──
        "is_dark_background": is_dark,
        "text_is_light": text_light,
        "section_title_color": text_main,
        "badge_enum_color": border_color if is_dark else accent_bright_rgb,
        "frame_style": style_info.get("frame_style", "glowing_neon"),
        "card_style": card_style,
        "background_tone": bg_tone,
        "art_style": style_info.get("art_style", "fantasy"),
        "mood": style_info.get("mood", "epic_heroic"),
        "motifs": style_info.get("motifs", []),
        "decor_elements": style_info.get("decor_elements", []),
        "sticker_ideas": style_info.get("sticker_ideas", []),
        # ── 原始数据引用 ──
        "_theme": theme,
        "_style_info": style_info,
    }


# ══════════════════════════════════════════════════════════════════
#  Decoration background (Vision analysis -> API t2i)
# ══════════════════════════════════════════════════════════════════

def _build_decor_prompt(design: dict) -> str:
    """用设计系统构建装饰背景 prompt，不再硬算 luminance。"""
    style_info = design["_style_info"]
    theme = design["_theme"]
    art_style_en = {
        "realistic": "photorealistic cinematic style",
        "anime": "Japanese anime cel style",
        "cyberpunk": "cyberpunk neon aesthetic",
        "guofeng_chinese": "Chinese guofeng ink-painting fusion",
        "painterly": "painterly concept art with visible brush strokes",
        "Q_style": "chibi Q-style cute illustrations",
        "sci_fi": "sci-fi futuristic technology aesthetic",
        "fantasy": "high fantasy epic style",
        "minimalist": "minimalist clean geometric design",
        "dark_gothic": "dark gothic ornate style",
        "pop_art": "pop art bold graphic comic style",
        "cel_shaded": "cel-shaded toon render style",
    }.get(style_info.get("art_style", ""), "fantasy game art style")

    mood_en = {
        "epic_heroic": "epic and heroic atmosphere",
        "dark_mysterious": "dark mysterious tension",
        "joyful_celebration": "joyful festive celebration energy",
        "serene_narrative": "serene calm tranquility",
        "intense_battle": "intense battle action",
        "futuristic_tech": "futuristic high-tech vibe",
        "magical_fantasy": "magical enchanting wonder",
        "cute_playful": "cute playful charm",
    }.get(style_info.get("mood", ""), "magical fantasy atmosphere")

    color_mood_en = {
        "warm_gold_orange": "warm gold-orange-amber tones",
        "cool_blue_purple": "cool blue-cyan-purple tones",
        "high_saturation_clash": "vivid high-saturation colors",
        "muted_earth": "muted earthy desaturated tones",
        "monochrome": "monochrome single-hue scheme",
        "pastel_soft": "soft pastel dreamy palette",
        "neon_dark": "dark with neon accent pops",
        "split_complementary": "dual-color split-complementary scheme",
    }.get(style_info.get("color_mood", ""), "cool blue-purple gradient")

    motifs = style_info.get("motifs", [])
    motif_str = ", ".join(motifs) if motifs else "flowing cloud swirls, gentle water ripples"

    a1 = theme.get("accent_bright", "#4488FF")
    a2 = theme.get("accent_bright_alt", "#88CCFF")
    bg_hex = theme.get("bg_page", "#0A0A1A")
    bg_tone = design["background_tone"]

    if bg_tone.startswith("very_dark"):
        bg_tone_str = (
            f"Overall canvas must be VERY DARK, near-black to deep {bg_hex} base. "
            f"Background fills at least 70% with very dark tones. "
            f"Only decorative motifs and {a1}/{a2} glow accents should be brighter."
        )
    elif bg_tone.startswith("dark"):
        bg_tone_str = (
            f"Overall canvas should be DARK, dominant dark tones based on {bg_hex}. "
            f"Subtle glow accents in {a1} and {a2}."
        )
    else:
        bg_tone_str = (
            f"Overall canvas is light and airy, soft pale tones, "
            f"gentle {a1} and {a2} highlights."
        )

    return (
        f"Design a seamless decorative background texture for a game event poster, "
        f"in {art_style_en}, with {mood_en}. "
        f"{bg_tone_str} "
        f"Color accent palette: {color_mood_en}. "
        f"Dominant decorative elements: {motif_str} -- woven elegantly throughout the canvas "
        f"as flowing abstract patterns, soft gradients, and gentle atmospheric lighting. "
        f"Clean premium UI-background quality, suitable for text overlay. "
        f"NO characters, NO faces, NO text, NO logos, NO hard edges. "
        f"Purely abstract decorative atmosphere. Film grain texture."
    )


def _generate_decor_bg(height: int, design: dict,
                       output_path: Path) -> Image.Image:
    # ── 缓存命中：直接读取已有文件 ──
    if output_path.is_file() and output_path.stat().st_size > 10000:
        try:
            bg = Image.open(output_path).convert("RGB")
            if bg.size != (CANVAS_W, height):
                bg = bg.resize((CANVAS_W, height), Image.Resampling.LANCZOS)
            print(f"[邮件长图/装饰] 复用缓存: {output_path.name}", flush=True)
            return bg
        except Exception:
            pass

    from scripts.changtu.micu_image_gen import run_micu_t2i

    prompt = _build_decor_prompt(design)
    MAX_SIDE = 3840
    gen_h = min((height + 15) // 16 * 16, MAX_SIDE)
    print(f"[邮件长图/装饰] 生成装饰背景 1920x{gen_h}（画布高{height}）...", flush=True)
    result = run_micu_t2i(prompt, output_path, width=1920, height=gen_h)
    if result is None:
        raise RuntimeError("[邮件长图/装饰] API 装饰背景生成失败")
    bg = Image.open(result).convert("RGB")
    if bg.size != (CANVAS_W, height):
        bg = bg.resize((CANVAS_W, height), Image.Resampling.LANCZOS)
    return bg


# ══════════════════════════════════════════════════════════════════
#  Decor sticker generation (AI t2i + BiRefNet 抠图 -> 透明 PNG)
# ══════════════════════════════════════════════════════════════════

def _generate_decor_sticker(sticker_idea: str, design: dict,
                            out_dir: Path) -> Image.Image | None:
    """生成单个贴纸（由 Vision sticker_ideas 驱动，不再硬编码种类）。
    sticker_idea: 如 'small_glowing_crystal_sprite', 'nebula_wisp_creature'
    失败时返回 None，不影响主流程。"""
    accent = design["_theme"].get("accent_bright", "#4488FF")
    art_style = design["art_style"]
    # 生成贴纸 prompt：简洁描述 + 风格 + 颜色
    prompt = (
        f"A cute {sticker_idea.replace('_', ' ')} sticker, "
        f"in {art_style} art style, "
        f"soft gradient coloring accented with {accent}, "
        f"isolated on clean white background, "
        f"digital illustration, chibi sticker art, game-themed."
    )

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", sticker_idea)[:40]
    sticker_path = out_dir / f"_email_sticker_{safe_name}.png"
    from scripts.changtu.micu_image_gen import run_micu_t2i

    print(f"[邮件长图/贴纸] 生成: {sticker_idea}...", flush=True)
    result = run_micu_t2i(prompt, sticker_path.with_suffix(".raw.png"),
                          width=STICKER_SIZE, height=STICKER_SIZE,
                          background="transparent", preserve_alpha=True)
    if result is None:
        print(f"[邮件长图/贴纸] {sticker_idea} API 生成失败", flush=True)
        return None

    img = Image.open(result).convert("RGB")

    # BiRefNet 抠图
    try:
        birefnet_scripts = Path(__file__).resolve().parent.parent.parent / ".claude" / "skills" / "banner-background-from-image" / "scripts"
        sys.path.insert(0, str(birefnet_scripts))
        from birefnet_matting import load_birefnet_matting, extract_alpha_pil

        model = load_birefnet_matting()
        alpha = extract_alpha_pil(img, model=model)
        out_img = img.convert("RGBA")
        out_img.putalpha(alpha)
        out_img.save(sticker_path)
        print(f"[邮件长图/贴纸] {sticker_idea} BiRefNet 抠图完成", flush=True)
        return out_img.resize((200, 200), Image.Resampling.LANCZOS)
    except Exception as e:
        print(f"[邮件长图/贴纸] {sticker_idea} BiRefNet 失败({e})，使用草图", flush=True)
        arr = np.array(img.convert("RGBA"))
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        white_thr = 230
        mask = ~((r > white_thr) & (g > white_thr) & (b > white_thr))
        arr[:, :, 3] = mask.astype(np.uint8) * 255
        out_img = Image.fromarray(arr, "RGBA")
        out_img.save(sticker_path)
        return out_img.resize((200, 200), Image.Resampling.LANCZOS)


# ══════════════════════════════════════════════════════════════════
#  Height calculation (pre-flight)
# ══════════════════════════════════════════════════════════════════

def _calc_event01_height(draw, event_date: str, date_images: list,
                         font_date, font_name) -> int:
    h = COMBINED_BANNER_DISPLAY_H + BADGE_CONTENT_GAP
    if event_date.strip():
        h += SECTION_PAD_TOP // 2 + _line_height(font_date)
    if date_images:
        rows = _prize_rows(len(date_images))
        content_w = CANVAS_W - SECTION_PAD_LR * 2
        card_w = (content_w - (max(rows) - 1) * CARD_GAP) // max(rows)
        icon_size = min(card_w - CARD_IMG_PAD * 2, 320)
        card_h = icon_size + CARD_IMG_PAD + CARD_NAME_H
        h += CARD_GAP + (card_h + CARD_GAP) * len(rows) - CARD_GAP + SECTION_PAD_BOTTOM
    else:
        h += SECTION_PAD_BOTTOM
    return h


def _calc_event02_height(draw, method_texts: list[str], screenshots: list,
                         font_desc) -> int:
    h = COMBINED_BANNER_DISPLAY_H + BADGE_CONTENT_GAP
    count = max(len(method_texts), len(screenshots))
    if count == 0:
        return h + SECTION_PAD_BOTTOM
    content_w = CANVAS_W - SECTION_PAD_LR * 2
    text_w = int(content_w * 0.85)
    img_w = int(content_w * 0.90)
    for i in range(count):
        if i < len(method_texts):
            lines = _wrap_text(draw, method_texts[i], font_desc, text_w)
            text_h = _line_height(font_desc) * len(lines)
            h += text_h + CARD_GAP
        shot_img = screenshots[i][1] if i < len(screenshots) else None
        if shot_img:
            shot_h = int(img_w * shot_img.height / max(shot_img.width, 1))
            h += shot_h + DEVICE_TITLEBAR_H + CARD_GAP
    h -= CARD_GAP
    h += SECTION_PAD_BOTTOM
    return h


def _calc_event03_height(items: list) -> int:
    h = COMBINED_BANNER_DISPLAY_H + BADGE_CONTENT_GAP
    if not items:
        return h + SECTION_PAD_BOTTOM
    content_w = CANVAS_W - SECTION_PAD_LR * 2
    rows = _prize_rows(len(items))
    card_w = (content_w - (max(rows) - 1) * CARD_GAP) // max(rows)
    icon_size = min(card_w - CARD_IMG_PAD * 2, 320)
    card_h = icon_size + CARD_IMG_PAD + CARD_NAME_H
    h += (card_h + CARD_GAP) * len(rows) - CARD_GAP + SECTION_PAD_BOTTOM
    return h


def _calc_event04_height(draw, intro_text: str, font_intro) -> int:
    h = COMBINED_BANNER_DISPLAY_H + BADGE_CONTENT_GAP
    if not intro_text.strip():
        return h + SECTION_PAD_BOTTOM
    content_w = CANVAS_W - SECTION_PAD_LR * 2
    text_box_w = content_w - TEXT_BOX_PAD_X * 2
    lines = _wrap_text(draw, intro_text, font_intro, text_box_w)
    # 使用 textbbox 精确测量每行高度，避免估算误差
    text_h = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_intro)
        text_h += (bbox[3] - bbox[1])
    h += text_h + TEXT_BOX_PAD_Y * 2 + SECTION_PAD_BOTTOM
    return h


# ── Section background box (bottom of each section) ──
def _draw_section_bg_box(canvas, x: int, y: int, w: int, h: int, alpha: int = 80) -> None:
    """在 section 底部绘制半透明背景框。"""
    if h <= 0:
        return
    bg = Image.new("RGBA", (w, h), (0, 0, 0, alpha))
    canvas.paste(bg, (x, y), bg)


# ══════════════════════════════════════════════════════════════════
#  make_email_poster  -- 主入口
# ══════════════════════════════════════════════════════════════════

def make_email_poster(
    kv: str | Path,
    font_title: str | Path,
    *,
    font_yahei: str | Path | None = None,
    main_title: str = "",
    sub_title: str = "",
    event_date: str = "",
    date_dir: str = "",
    prize_dir: str = "",
    prize_order: list[str] | None = None,
    method_desc: str = "",
    method_dir: str = "",
    history_dir: str = "",
    history_order: list[str] | None = None,
    intro_text: str = "",
    output: str | Path = "output/邮件长图.jpg",
    brand_logo: str | Path | None = None,
    brand_name: str = "",
    brand_sublabel: str = "",
    section_titles: dict | None = None,
) -> Path:
    """Generate the email poster (1920px wide, 4-section layout)."""
    # ── Fonts ──
    _check_fonts(font_title, font_yahei)
    font_title_big = _load_font(font_title, KV_TITLE_SIZE)
    font_sec = _load_font(font_title, SECTION_TITLE_SIZE)
    font_enum_local = _yahei(BADGE_ENUM_SIZE)
    font_date = _yahei(EVENT_DATE_SIZE)
    font_desc = _yahei(EVENT_DESC_SIZE)
    font_intro = _yahei(EVENT_INTRO_SIZE)
    font_name = _yahei(CARD_NAME_SIZE)
    font_brand = _load_font(font_title, BRAND_NAME_SIZE)
    font_brand_sub = _yahei(BRAND_SUBLABEL_SIZE)

    # ── KV ──
    kv_path = Path(kv).resolve()
    kv_img = Image.open(kv_path).convert("RGB")
    kv_scale = CANVAS_W / kv_img.width
    kv_resized = kv_img.resize((CANVAS_W, int(kv_img.height * kv_scale)), Image.Resampling.LANCZOS)
    kv_display_h = kv_resized.height

    # ── Theme + Vision → Design System ──
    out_dir = Path(output).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    from scripts.changtu.color_extract import extract_theme_from_kv

    theme = extract_theme_from_kv(kv_path)
    style_info = _vision_analyze_kv_style(kv_path, out_dir)

    # 融合 K-means 精确色 + Vision 语义 → 统一设计系统
    D = _build_design_system(theme, style_info)
    bg_page = D["bg_page"]
    accent = D["accent_bright"]
    border_color = D["border_color"]
    text_primary = D["text_primary"]
    text_secondary = D["text_secondary"]
    bg_card = D["bg_card"]
    bg_card_dark = D["bg_card_dark"]
    section_title_color = D["section_title_color"]
    badge_enum_color = D["badge_enum_color"]
    badge_text_color = (255, 255, 255)

    # ── Load materials ──
    date_images = _load_prizes(date_dir)
    prizes = _load_prizes(prize_dir, prize_order)
    method_screenshots = _load_prizes(method_dir)
    history_items = _load_prizes(history_dir, history_order)
    method_texts = [t.strip() for t in method_desc.split("|") if t.strip()] if method_desc else []

    # ── Brand logo ──
    brand_logo_img: Image.Image | None = None
    if brand_logo:
        lp = Path(brand_logo)
        if lp.is_file():
            brand_logo_img = Image.open(lp).convert("RGBA")

    # ── Parse section titles (support "主标题|副标题" format) ──
    _default_titles = {"event01": "活动时间", "event02": "参与方法",
                       "event03": "奖品展示", "event04": "活动规则"}
    titles = {**_default_titles, **(section_titles or {})}
    _banner_titles: dict[str, str] = {}      # 主标题
    _banner_subtitles: dict[str, str] = {}   # 副标题（无则为空串）
    for k, v in titles.items():
        if v and "|" in str(v):
            parts = str(v).split("|", 1)
            _banner_titles[k] = parts[0].strip()
            _banner_subtitles[k] = parts[1].strip()
        else:
            _banner_titles[k] = str(v) if v else ""
            _banner_subtitles[k] = ""
    show_section = {k: bool(titles.get(k)) for k in _default_titles}
    _section_order = ["event01", "event02", "event03", "event04"]
    _enum_labels = {"event01": "EVENT01", "event02": "EVENT02",
                    "event03": "EVENT03", "event04": "EVENT04"}

    # ── Pre-calc heights ──
    draw_dummy = ImageDraw.Draw(Image.new("RGB", (CANVAS_W, 100)))
    s1_h = _calc_event01_height(draw_dummy, event_date, date_images, font_date, font_name)
    s2_h = _calc_event02_height(draw_dummy, method_texts, method_screenshots, font_desc)
    s3_h = _calc_event03_height(prizes)
    s4_h = _calc_event04_height(draw_dummy, intro_text, font_intro)

    section_heights = {"event01": s1_h, "event02": s2_h, "event03": s3_h, "event04": s4_h}
    section_total_h = s1_h + SECTION_GAP + s2_h + SECTION_GAP + s3_h + SECTION_GAP + s4_h
    canvas_h = kv_display_h + section_total_h + CANVAS_PAD_BOTTOM

    # ── Generate decor background ──
    decor_path = out_dir / "_email_decor_bg.png"
    try:
        decor_bg = _generate_decor_bg(canvas_h, D, decor_path)
    except Exception as e:
        print(f"[邮件长图/装饰] 生成失败: {e}，使用纯色渐变兜底", flush=True)
        decor_bg = Image.new("RGB", (CANVAS_W, canvas_h), bg_page)

    # ── Generate transition banners (AI) ──
    n_shown = sum(1 for k in _section_order if show_section[k])
    print(f"[邮件长图] 生成 {n_shown} 个显示区块，需 {n_shown} 条过渡 Banner", flush=True)
    transition_banners = _generate_transition_banners(D, out_dir, count=n_shown)

    # ── Canvas ──
    canvas = decor_bg.convert("RGBA")

    # ── 全局遮罩：40% 黑色，覆盖全画布（背景之上，KV/内容之下） ──
    overlay = Image.new("RGBA", (CANVAS_W, canvas_h), (0, 0, 0, 102))
    canvas.paste(overlay, (0, 0), overlay)

    kv_rgba = kv_resized.convert("RGBA")
    canvas.paste(kv_rgba, (0, 0), kv_rgba)

    draw = ImageDraw.Draw(canvas)

    # ── Brand header (KV 左上角) ──
    if brand_logo_img or brand_name:
        _draw_brand_header(canvas, draw, brand_logo_img, brand_name,
                           brand_sublabel, font_brand, font_brand_sub, accent)

    # ── Draw section background box (alpha=80) ──
    def _draw_section_bg_box(canvas, x: int, y: int, w: int, h: int, alpha: int = 80):
        """Draw a rounded rect background box at section bottom."""
        if h <= 0:
            return
        box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(box)
        r = CARD_RADIUS
        d.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=r, fill=(0, 0, 0, alpha))
        canvas.paste(box, (x, y), box)


    # ── KV title ──
    if main_title or sub_title:
        _draw_kv_title(draw, kv_display_h, main_title, sub_title,
                       font_title_big)

    content_w = CANVAS_W - SECTION_PAD_LR * 2
    banner_idx = 0
    sy = kv_display_h  # Section banners start after KV image

    for section_key in _section_order:
        if not show_section[section_key]:
            continue

        sec_title = _banner_titles[section_key]
        sec_subtitle = _banner_subtitles[section_key]
        section_h = section_heights[section_key]
        banner_img = transition_banners[banner_idx]
        banner_idx += 1

        _draw_combined_section_banner(canvas, SECTION_PAD_LR, sy, content_w,
                                      sec_title, "", banner_img,
                                      D, font_sec, font_enum_local, layout="text_center",
                                      subtitle=sec_subtitle)
        cy = sy + COMBINED_BANNER_DISPLAY_H + BADGE_CONTENT_GAP

        # ── 先画背景框（在内容之下） ──
        content_h = section_h - COMBINED_BANNER_DISPLAY_H - BADGE_CONTENT_GAP
        if content_h > 0:
            _draw_section_bg_box(canvas, SECTION_PAD_LR, cy, content_w, content_h, alpha=80)

        # ── Content drawing per section ──
        if section_key == "event01":
            if event_date.strip():
                cy = _draw_date_line(canvas, draw, cy, event_date, font_date,
                                     accent, text_primary)
            if date_images:
                cy = _draw_circular_icon_grid(canvas, draw, cy, date_images, font_name,
                                              accent, bg_card_dark, border_color, text_primary)

        elif section_key == "event02":
            if method_texts:
                cy = _draw_method_section(canvas, draw, cy, method_texts,
                                          method_screenshots, font_desc,
                                          accent, bg_card_dark, border_color, text_primary,
                                          skip_ocr=bool(method_texts))

        elif section_key == "event03":
            if prizes:
                cy = _draw_circular_icon_grid(canvas, draw, cy, prizes, font_name,
                                              accent, bg_card_dark, border_color, text_primary)

        elif section_key == "event04":
            if intro_text.strip():
                cy = _draw_intro_section(canvas, draw, cy, intro_text, font_intro,
                                         bg_card_dark, border_color, text_primary)

        sy = sy + section_heights[section_key] + SECTION_GAP

    # ── Save ──
    out_path = Path(output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[邮件长图] 准备保存到: {out_path}", flush=True)
    canvas.convert("RGB").save(out_path, quality=95)
    print(f"[邮件长图] 已保存: {out_path}", flush=True)
    return out_path
