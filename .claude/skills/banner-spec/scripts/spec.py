#!/usr/bin/env python3
"""
Banner 规范唯一数据源：预设、安全区、图例区、布局、规范分组、输出文件名。
供 banner-composer、banner-background-from-image、banner-background-from-description、run_all_presets 引用。
"""

# 预设名 -> (宽, 高)
PRESETS: dict[str, tuple[int, int]] = {    "fill_canvas": (4096, 1024),  # 无图流程：即梦 4:1 生成图，与 prepare_background A4 画布一致，供 run_all_presets 输入
    "changtu_poster": "auto",  # 活动长图 1080×auto（高度由内容动态计算）
}

# 安全区 (x_min, x_max, y_min, y_max)，按画布 (W, H)
SAFE_ZONE_BY_CANVAS: dict[tuple[int, int], tuple[int, int, int, int]] = {}

# 按 preset 覆盖安全区（与同尺寸 SAFE_ZONE_BY_CANVAS 并存；裁切/对齐时传入 preset 生效）
SAFE_ZONE_BY_PRESET: dict[str, tuple[int, int, int, int]] = {}

# 图例区 (x_min, x_max, y_min, y_max)，按画布 (W, H)
LEGEND_ZONE_BY_CANVAS: dict[tuple[int, int], tuple[int, int, int, int]] = {}

# 对话框区域 (x_min, x_max, y_min, y_max)，按画布 (W, H)
DIALOG_ZONE_BY_CANVAS: dict[tuple[int, int], tuple[int, int, int, int]] = {}

# 文字艺术字区域 (x_min, x_max, y_min, y_max)，按画布 (W, H)
# 走独立管线：生图API生成艺术字体 → BiRefNet抠图 → 背景风格统一重绘 → 粘贴
TEXT_ART_ZONE_BY_CANVAS: dict[tuple[int, int], tuple[int, int, int, int]] = {}

# 排除区 (x_min, x_max, y_min, y_max) 列表，按画布 (W, H)
# 画面主要内容需避开这些区域（后续叠对话框/文字艺术字等组件）
EXCLUSION_ZONES_BY_CANVAS: dict[tuple[int, int], list[tuple[int, int, int, int]]] = {}

# 规范分组：组名 -> 该组要跑的 preset 列表（-g 用）
GENRE_PRESETS: dict[str, list[str]] = {
    "活动长图": ["changtu_poster"],
    # 战报长图（1080px 竖版，KV 取色 + 多分区排版 + 本地字体叠字）
    "战报": ["battle_report_poster"],
    # 邮件长图（1920px 竖版，KV + EVENT01~04 四区排版 + Vision 风格分析 + API 装饰背景）
    "邮件长图": ["email_poster"],
    # 排行榜（1080px 竖版，CSV→JSON + 图标 + 背景 + 截图）
    "排行榜": ["ranking_poster"],
}

# 分组 -> Step 1 文生图时自动追加的风格描述片段（拼在用户 description 之后，PROMPT_SUFFIX 之前）
# 未配置的分组不追加。run_full_with_custom_prompt 在调用 Step 1 前读取并拼入。
GENRE_STYLE_PROMPT: dict[str, str] = {
    "活动长图": (
        "。竖版构图，上方为核心视觉区（KV），色彩饱和有张力；"
        "下方为信息区，背景干净留白、渐变过渡自然。"
        "禁止出现文字、标题或 CTA 按钮。"
    ),
}

# 预设 -> 约定输出文件名（Windows 下 * 改为 x）

# 布局：按画布 (W, H) -> 布局 dict（主/副标题坐标、渐变、legend_zone 等）
LAYOUT_BY_CANVAS: dict[tuple[int, int], dict] = {
    (1976, 464): {  # 首页 1976×464：命名「首页 1976×464」；画布 1976×464，安全区 x=752-1457 y=0-464；主标题 (567,183) 微软雅黑 Bold 52 左对齐 ≥10字按语义断行；副标题距主标题 24px，(567,267) Regular 28 80% 按语义断行单行≤14字；渐变遮罩 1270×464 从左到右黑→透明 40% 边缘柔和
        "main_x": 567, "main_y": 183, "main_size": 52,
        "sub_x": 567, "sub_y": 267, "sub_size": 28, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "sub_y_follow_main_if_wrap": True,
        "main_break_chars": 10, "sub_break_chars": 14,
        "gradient_rect": (1270, 464), "gradient_rect_x": 0, "gradient_rect_y": 0,
        "gradient_diagonal": False, "gradient_vertical": False,
        "gradient_opacity": 0.4, "gradient_blur_radius": 8,
        "white_top_strip": None, "no_text": False,
        "legend_zone": (1257, 1457, 364, 464),
    },
    (3320, 500): {  # 商店专题长图 3320*460（文件 专题长图 3320x460.png）：画布 3320×500；安全区 x=1470-2464 y=40-500；顶 y=0-40 纯白（prepare A5b+BiRefNet，compose white_top_strip=None）；x=1470-2464、y=40-500 内容区白底上铺画面；主标题 Bold68 左(940,134)语义断行；副标题 Reg28 80% 左(940,261)语义断行单行≤14字，主标题多行时副标题下移距主标题24px；按钮「了解更多」居中对齐主标题；渐变 x=0-1457 y=40-500 左黑→右透明 40% 边缘柔和（与首页 1976×464 同向）
        "main_x": 940, "main_y": 134, "main_size": 68,
        "sub_x": 940, "sub_y": 261, "sub_size": 28, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "sub_y_follow_main_if_wrap": True,
        "main_break_chars": 10, "sub_break_chars": 14,
        "gradient_rect": (1457, 460),
        "gradient_rect_x": 0,
        "gradient_rect_y": 40,
        "gradient_diagonal": False,
        "gradient_vertical": False,
        "gradient_opacity": 0.5,
        "gradient_blur_radius": 12,
        "white_top_strip": None, "no_text": False,
        "button_x": 941, "button_y": 370, "button_w": 178, "button_h": 79, "button_text": "了解更多",
        "button_text_x": 973, "button_text_y": 386, "button_font_size": 28,
        "button_radius": 39.5,
        "button_fill_rgba": (255, 255, 255, 51), "button_stroke_rgba": (255, 255, 255, 102), "button_stroke_width": 0.75,
        "button_shadow_dy": None, "button_shadow_rgba": None, "button_shadow_blur_radius": 0,
        "legend_zone": (3100, 3320, 420, 500),
    },
    (500, 280): {  # 专题封面 500×280：命名「专题封面 500×280」；画布 500×280px，安全区 x=200-500 y=50-280；主标题 (36,53) 微软雅黑 Bold 30 最多8字不换行；副标题 (36,102) Regular 24 80% 最多10字不换行；渐变遮罩 x=0-500 y=0-157 从上到下黑→透明 30% 边缘柔和
        "main_x": 36, "main_y": 53, "main_size": 30,
        "sub_x": 36, "sub_y": 102, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "main_break_chars": 99, "sub_break_chars": 99,
        "main_max_chars": 8, "sub_max_chars": 10,
        "gradient_rect": (500, 157), "gradient_rect_x": 0, "gradient_rect_y": 0,
        "gradient_diagonal": False, "gradient_vertical": True, "gradient_vertical_top_heavy": True,
        "gradient_opacity": 0.3, "gradient_blur_radius": 8,
        "white_top_strip": None, "no_text": False,
        "legend_zone": (400, 500, 230, 280),
    },
    (304, 216): {  # 商店田字格 304×216：命名「商店田字格 304×216」（文件名 304x216）；画布 304×216px；安全区 x=0-303 y=0-140；主标题 (24,123) Bold 30 最多8字；副标题 (24,165) Reg 24 80% 最多10字；渐变 x=0-304 y=90-216 下到上黑→透明 30% 边缘柔和
        "main_x": 24, "main_y": 123, "main_size": 30,
        "sub_x": 24, "sub_y": 165, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "main_break_chars": 8, "sub_break_chars": 14,
        "main_max_chars": 8, "sub_max_chars": 10,
        "gradient_rect": (304, 216), "gradient_diagonal": False,
        "gradient_vertical": True, "gradient_vertical_top_heavy": False,
        "gradient_opacity": 0.4, "gradient_blur_radius": 8,
        "white_top_strip": None, "no_text": False,
        "legend_zone": (204, 304, 166, 216),
    },
    (1740, 220): {  # 专题头图 1740×220：命名「专题头图 1740x220」；画布 1740×220px，安全区 x=510-1312 y=76-172；只做画面裁切对齐，无文字填充
        "main_x": 0, "main_y": 0, "main_size": 28,
        "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True,
        "legend_zone": (1540, 1740, 170, 220),
    },
    # 开放平台 2560×496：主/副标题微软雅黑 Bold/Regular 左对齐；按钮「了解更多」无填充、白描边 80%、1px、圆角0、文字 Regular 20 居中
    (2560, 496): {  # 开放平台banner2560*496：画布 2560×496px，安全区 x=1152-1880 y=80-416；主(784,183) Bold 46 最多16字/行；副(784,267) Reg 26 80% 最多20字/行；按钮(784,337) 137×37
        "main_x": 784, "main_y": 183, "main_size": 46,
        "sub_x": 784, "sub_y": 267, "sub_size": 26, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "sub_y_follow_main_if_wrap": True,
        "main_break_chars": 16, "sub_break_chars": 20,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": False,
        "legend_zone": None,
        "button_x": 784, "button_y": 337, "button_w": 137, "button_h": 37, "button_text": "了解更多",
        "button_font_size": 20,
        "button_radius": 0,
        "button_fill_rgba": None,
        "button_stroke_rgba": (255, 255, 255, 204),
        "button_stroke_width": 1,
        "button_shadow_dy": None, "button_shadow_rgba": None, "button_shadow_blur_radius": 0,
    },
    (900, 383): {  # 开放平台微信banner900*383：画布 900×383px，安全区 x=336-860 y=40-303；主(40,115) Bold 48 最多14字/行；副(40,200) Reg 30 80% 最多16字/行；主标题换行时副标题距主标题 32px；无按钮
        "main_x": 40, "main_y": 115, "main_size": 48,
        "sub_x": 40, "sub_y": 200, "sub_size": 30, "sub_opacity": 0.8,
        "subtitle_gap": 32,
        "sub_y_follow_main_if_wrap": True,
        "main_break_chars": 14, "sub_break_chars": 16,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": False,
        "legend_zone": None,
    },
    # 商店移动端系列：主标题微软雅黑 Bold 左对齐，副标题 Regular 左对齐，超出最大字数截断；文字下方左→右渐变遮罩（黑→透明，30%），边缘柔和
    (984, 442): {  # 商店移动端banner 984*442：主标题 (50,150) 55 最多10字，副标题 (50,228) 26 80% 最多14字；遮罩 500×440 左→右黑到透明 30%
        "main_x": 50, "main_y": 150, "main_size": 55,
        "sub_x": 50, "sub_y": 228, "sub_size": 26, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "main_break_chars": 99, "sub_break_chars": 99,
        "main_max_chars": 10, "sub_max_chars": 14,
        "gradient_rect": (500, 440), "gradient_rect_x": 0, "gradient_rect_y": 0,
        "gradient_diagonal": False, "gradient_vertical": False,
        "gradient_opacity": 0.3, "gradient_blur_radius": 10,
        "white_top_strip": None, "no_text": False, "legend_zone": None,
    },
    (650, 275): {  # 商店移动端专题封面 650*275：主标题 (40,110) 36 最多10字，副标题 (40,160) 18 80% 最多14字；遮罩 266×275 左→右黑到透明 30%
        "main_x": 40, "main_y": 110, "main_size": 36,
        "sub_x": 40, "sub_y": 160, "sub_size": 18, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "main_break_chars": 99, "sub_break_chars": 99,
        "main_max_chars": 10, "sub_max_chars": 14,
        "gradient_rect": (266, 275), "gradient_rect_x": 0, "gradient_rect_y": 0,
        "gradient_diagonal": False, "gradient_vertical": False,
        "gradient_opacity": 0.3, "gradient_blur_radius": 10,
        "white_top_strip": None, "no_text": False, "legend_zone": None,
    },
    (720, 220): {  # 商店移动端专题头图 720*220：主标题 (40,72) 36 最多10字，副标题 (40,127) 18 80% 最多14字；遮罩 266×220 左→右黑到透明 30%
        "main_x": 40, "main_y": 72, "main_size": 36,
        "sub_x": 40, "sub_y": 127, "sub_size": 18, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "main_break_chars": 99, "sub_break_chars": 99,
        "main_max_chars": 10, "sub_max_chars": 14,
        "gradient_rect": (266, 220), "gradient_rect_x": 0, "gradient_rect_y": 0,
        "gradient_diagonal": False, "gradient_vertical": False,
        "gradient_opacity": 0.3, "gradient_blur_radius": 10,
        "white_top_strip": None, "no_text": False, "legend_zone": None,
    },
    (355, 350): {  # 商店移动端田字格355*350：固定渐变背景（4种方案），圆角30°，单行文字居中，40号白色微软雅黑Bold
        "main_x": 0, "main_y": 40, "main_size": 40,  # main_align=center 时 x 被忽略
        "main_align": "center",  # 文字在画布水平居中
        "sub_x": 177, "sub_y": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24,
        "main_break_chars": 99, "sub_break_chars": 99,
        "main_max_chars": 8,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": False, "legend_zone": None,
        "main_bold": False,  # Regular 字重
        # 固定渐变背景配置（4种方案，variant=1~4）
        "fixed_gradient": True,
        "fixed_gradient_colors": [
            ("#6AF4EA", "#0471FE"),  # 方案1
            ("#00E0E8", "#2FFD9C"),  # 方案2
            ("#FEA243", "#FEE226"),  # 方案3
            ("#FFA06E", "#833185"),  # 方案4
        ],
        "fixed_gradient_direction": "diagonal",  # 左上→右下
        "corner_radius": 30,
        # 主体物配置：安全区中心 (199, 220)
        "subject_rect": (48, 85, 302, 270),  # (x, y, w, h) 安全区
        "subject_align": "center",           # 居中对齐
        "subject_scale": "fit",              # 等比缩放fit进区域
    },
    # Legend zone 3840×1200 基底：legend_home_3840；无 logo；顶部 banner 的 logo/title_art 见 LAYOUT_BY_PRESET
    (3840, 1200): {
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
    },
    (324, 570): {  # Lengion zone 新游发布 324*570：画布 324×570px；安全区 x=0-324 y=0-570；无文字、无遮罩；logo 区 120×40 @ (30,30)，透明 PNG 等比/非透明抠图后等比（compose 侧）
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (30, 30, 120, 40), "logo_align": "top_left", "logo_scale": "max_width",
    },
    (1800, 1030): {  # Lengion zone 测试先锋背景 1800*1030：画布 1800×1030；安全区全画布；无文字、无遮罩、无 logo
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
    },
    (1120, 660): {
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (30, 30, 130, 40),
    },
    (780, 880): {
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (60, 60, 200, 70), "logo_align": "top_left", "logo_scale": "max_width",
    },
    (708, 570): {
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (80, 50, 150, 50), "logo_align": "top_left", "logo_scale": "max_width",
    },
    (504, 796): {
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (50, 50, 150, 50), "logo_align": "top_left", "logo_scale": "max_width",
    },
    (572, 380): {
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (80, 50, 160, 40), "logo_align": "top_left", "logo_scale": "max_width",
    },
    (2590, 392): {  # Lengion zone 游戏推荐 2590×392：无文字填充，无遮罩
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
    },
    (1196, 672): {
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (40, 50, 500, 55), "logo_align": "top_left", "logo_scale": "max_width",
    },
    (2332, 1306): {
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (60, 90, 264, 170), "logo_align": "top_left", "logo_scale": "max_width",
    },
    (328, 328): {
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": (328, 176), "gradient_rect_x": 0, "gradient_rect_y": 152,
        "gradient_diagonal": False, "gradient_vertical": True, "gradient_vertical_top_heavy": False,
        "gradient_opacity": 0.8,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
    },
    (656, 360): {  # Lengion zone 弹窗 656×360：画布 656×360px；安全区 x=266-656 y=0-360（背景图位置）；无遮罩；主标题 (35,85) Bold 48 最多8字；副标题 Regular 24 80% 跟随主标题；logo (35,35) 高度30px 等比缩放 左上角对齐
        "main_x": 35, "main_y": 85, "main_size": 48,
        "main_break_chars": 99, "main_max_chars": 8,
        "sub_x": 35, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 16, "sub_break_chars": 14,
        "sub_y": 156,
        "sub_y_follow_main_if_wrap": True,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": False,
        "legend_zone": None,
        "logo_rect": (35, 35, 230, 30),   # (x, y, max_w, h)
        "logo_align": "top_left",
        "logo_scale": "max_height",
    },
    (880, 428): {  # Lengion zone 手机端卡片880*428：画布 880×428px；安全区 x=10-870 y=10-418；无文字、无遮罩；logo x=55 y=55 高度90px 等比缩放 左上角对齐
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (55, 55, 760, 90),   # (x, y, max_w, h)；高度90px，最大宽度760px
        "logo_align": "top_left",
        "logo_scale": "max_height",
    },
    (736, 980): {  # Lengion zone 手机端卡片736*980：画布 736×980px；安全区 x=10-736 y=10-980；无文字、无遮罩；logo x=80 y=80 高度90px 等比缩放 左上角对齐
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "logo_rect": (80, 80, 576, 90),   # (x, y, max_w, h)；高度90px，最大宽度576px
        "logo_align": "top_left",
        "logo_scale": "max_height",
    },
    (1920, 550): {  # 商店畅玩卡1920*550：画布 1920×550px；安全区 x=360-1560 y=10-540；无文字填充，对话框叠加区域 x=516-1021 y=363-410，文字艺术字区域 x=516-1026 y=90-360
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "text_art_rect": (516, 90, 510, 270),  # (x, y, w, h) 文字艺术字粘贴区
        "dialog_rect": (516, 363, 505, 47),  # (x, y, w, h) 对话框粘贴区
    },
    (750, 673): {  # 手机端畅玩卡750*673：画布 750×673px；安全区全画布 x=0-750 y=0-673；无文字填充；文字艺术字 x=33-489 y=62-274；对话框 x=33-489 y=282-322
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "text_art_rect": (33, 62, 456, 212),  # (x, y, w, h) 文字艺术字粘贴区
        "dialog_rect": (33, 282, 456, 40),  # (x, y, w, h) 对话框粘贴区
    },
    (112, 112): {  # 商店push112*112：画布 112×112px；安全区 x=0-112 y=0-112；无文字填充，无遮罩
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
    },
    (324, 160): {  # PC浏览器push324*160：无文字填充，无遮罩，8px圆角，透明通道
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
        "corner_radius": 8, "transparent": True,
        "multi_scale": [
            (1.0, "PC浏览器push.png", 8),
            (1.5, "PC浏览器push@150.png", 12),
            (2.0, "PC浏览器push@200.png", 16),
            (3.0, "PC浏览器push@300.png", 24),
        ],
    },
    (700, 300): {  # 商店移动端noti700*300：无文字填充，无遮罩
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
    },
    (1536, 1024): {  # 商店移动端生成式UI封面1536x1024：无文字填充，无遮罩
        "main_x": 0, "main_y": 0, "main_size": 28, "sub_x": 0, "sub_size": 24, "sub_opacity": 0.8,
        "subtitle_gap": 24, "main_break_chars": 8, "sub_break_chars": 14,
        "gradient_rect": None, "gradient_diagonal": False, "gradient_vertical": False,
        "white_top_strip": None, "no_text": True, "legend_zone": None,
    },
}

# 按 preset 覆盖/追加布局（与 get_layout 合并）；用于同画布多规格（如 3840×1200 首页 vs 顶部 banner）
LAYOUT_BY_PRESET: dict[str, dict] = {}

# 默认布局回退值（未在 LAYOUT_BY_CANVAS 中配置时使用）


def get_safe_zone(width: int, height: int, preset: str | None = None):
    if preset and preset in SAFE_ZONE_BY_PRESET:
        return SAFE_ZONE_BY_PRESET[preset]
    return SAFE_ZONE_BY_CANVAS.get((width, height))


def get_safe_zone_center(width: int, height: int, preset: str | None = None):
    zone = get_safe_zone(width, height, preset)
    if zone is None:
        return None
    x_min, x_max, y_min, y_max = zone
    return ((x_min + x_max) // 2, (y_min + y_max) // 2)


def get_legend_zone(width: int, height: int):
    return LEGEND_ZONE_BY_CANVAS.get((width, height))


def get_dialog_zone(width: int, height: int):
    return DIALOG_ZONE_BY_CANVAS.get((width, height))


def get_text_art_zone(width: int, height: int):
    return TEXT_ART_ZONE_BY_CANVAS.get((width, height))


def get_exclusion_zones(width: int, height: int):
    return EXCLUSION_ZONES_BY_CANVAS.get((width, height), [])


def get_layout(width: int, height: int, preset: str | None = None):
    layout = dict(LAYOUT_BY_CANVAS.get((width, height), {}))
    if preset and preset in LAYOUT_BY_PRESET:
        layout.update(LAYOUT_BY_PRESET[preset])
    return layout