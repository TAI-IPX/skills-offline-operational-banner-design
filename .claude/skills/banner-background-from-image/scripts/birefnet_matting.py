#!/usr/bin/env python3
"""
BiRefNet 抠图：用于商店专题长图顶部条带主体抠图。
依赖: torch, torchvision, transformers（可选，未安装时调用方需回退）。
"""

from __future__ import annotations

import os
from pathlib import Path

# BiRefNet-matting 为固定分辨率，使用 1024×1024 推理后再缩放回原图尺寸
BIREFNET_INFER_SIZE = 1024
# 顶部条带 matting 使用的源区高度（像素），比条带高一些以利抠图、主体更干净
STRIP_SOURCE_HEIGHT = 120

_model_cache = None


def _get_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def load_birefnet_matting(device: str | None = None):
    """加载 BiRefNet-matting，返回 model。首次会从 HuggingFace 下载。"""
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    # 分别导入，避免把 transformers 内部依赖（如 regex）错误误报成「未装 torch」
    try:
        import torch
    except ImportError as e:
        raise RuntimeError(
            "BiRefNet 需要 PyTorch。任选其一：\n"
            "  1) 项目根: pip install -e \".[birefnet]\"\n"
            "  2) Windows CPU: scripts/install_birefnet_deps.bat\n"
            "  3) pip install torch torchvision"
        ) from e
    try:
        from transformers import AutoModelForImageSegmentation
    except ImportError as e:
        raise RuntimeError(
            "BiRefNet 需要 transformers。请执行: pip install \"transformers>=4.38\" huggingface_hub\n"
            "若仍报错，可尝试: pip install --force-reinstall regex"
        ) from e
    dev = device or _get_device()
    try:
        model = AutoModelForImageSegmentation.from_pretrained(
            "ZhengPeng7/BiRefNet-matting",
            trust_remote_code=True,
        )
    except Exception as e:
        raise RuntimeError(
            "BiRefNet 从 HuggingFace 加载失败（需联网首次下载 ZhengPeng7/BiRefNet-matting）。"
            f" 详情: {e}"
        ) from e
    model.to(dev)
    model.eval()
    if dev == "cuda":
        model.half()
    _model_cache = model
    return model


def extract_alpha_pil(
    image_pil,
    model=None,
    device: str | None = None,
    infer_size: int = BIREFNET_INFER_SIZE,
):
    """
    对整图做 BiRefNet 推理，得到与 image_pil 同尺寸的 alpha（PIL 单通道 L）。
    使用固定 1024×1024 推理后缩放回原图，以兼容 BiRefNet-matting 固定分辨率。
    """
    try:
        import torch
        from torchvision import transforms
    except ImportError as e:
        raise RuntimeError("需要 torch、torchvision") from e
    from PIL import Image

    if model is None:
        model = load_birefnet_matting(device)
    dev = device or _get_device()
    w, h = image_pil.size
    rw = rh = infer_size
    infer_img = image_pil.resize((rw, rh), Image.Resampling.LANCZOS)

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    x = transform(infer_img.convert("RGB")).unsqueeze(0)
    x = x.to(dev)
    if dev == "cuda":
        x = x.half()

    with torch.no_grad():
        out = model(x)
        if isinstance(out, (list, tuple)):
            pred = out[-1].sigmoid().cpu().float().numpy()
        else:
            pred = out.sigmoid().cpu().float().numpy()
    pred = pred[0, 0]
    if pred.ndim == 3:
        pred = pred[0]
    pred = (pred * 255).clip(0, 255).astype("uint8")
    alpha_pil = Image.fromarray(pred, mode="L")
    if (rw, rh) != (w, h):
        alpha_pil = alpha_pil.resize((w, h), Image.Resampling.LANCZOS)
    return alpha_pil


def composite_strip_with_matting(
    canvas_rgb,
    strip_x_min: int,
    strip_x_max: int,
    strip_y_min: int,
    strip_y_max: int,
    model=None,
    device: str | None = None,
    alpha_threshold: float = 0.5,
):
    """
    在 canvas 上取条带区域，用 BiRefNet 抠图得到 RGBA 块，返回 (strip_rgba_pil, alpha_pil_full)。
    使用比条带更高的源区（STRIP_SOURCE_HEIGHT）做 matting 再取最上 strip_h 像素，抠图更干净；
    alpha 低于 alpha_threshold 置 0 以彻底去掉背景。
    """
    from PIL import Image
    import numpy as np
    w, h = canvas_rgb.size
    strip_w = strip_x_max - strip_x_min
    strip_h = strip_y_max - strip_y_min
    if strip_w <= 0 or strip_h <= 0:
        return None, None
    source_h = max(strip_h, min(STRIP_SOURCE_HEIGHT, h - strip_y_min))
    source_y_max = strip_y_min + source_h
    crop = canvas_rgb.crop((strip_x_min, strip_y_min, strip_x_max, source_y_max))
    alpha_full = extract_alpha_pil(canvas_rgb, model=model, device=device)
    alpha_crop = alpha_full.crop((strip_x_min, strip_y_min, strip_x_max, source_y_max))
    a = np.array(alpha_crop, dtype=np.float32) / 255.0
    a = (a >= alpha_threshold).astype(np.float32) * 255
    alpha_crop = Image.fromarray(a.astype(np.uint8), mode="L")
    strip_rgba = Image.new("RGBA", (strip_w, strip_h), (255, 255, 255, 0))
    src_rgb = crop.crop((0, 0, strip_w, strip_h))
    src_alpha = alpha_crop.crop((0, 0, strip_w, strip_h))
    strip_rgba.paste(src_rgb, (0, 0))
    strip_rgba.putalpha(src_alpha)
    return strip_rgba, alpha_full
