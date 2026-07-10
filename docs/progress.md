# 任务进度追踪

> 此文件由 AI 自动维护。新建会话时读取此文件可恢复上次进度。

## 状态：已完成

## 任务目标

邮件长图 —「王者荣耀世界」全景改造
- 主标题: "王者荣耀世界" | 副标题: 空（KV 图自带标题）
- 字体: msyhbd.ttc
- 素材: C:\Users\80507\Desktop\邮件长图\（KV + 活动时间/参与方法/往期中奖）
- 后端: MoxinGemini（Vision）+ MoxinGPT（生图，gpt-image-2-base64）
- KV 图自带标题，不叠加文字

---

## 步骤状态

- [x] Vision prompt 扩展 7→14 字段，覆盖所有设计维度
- [x] 新增 `_build_design_system()` 融合 K-means 精确色 + Vision 语义
- [x] `_build_decor_prompt` 改读 design dict，不硬算 luminance
- [x] `_generate_decor_sticker` 从硬编码枚举改为 Vision sticker_ideas 驱动
- [x] 新增 `_draw_section_container` 四区统一 dark_glass 容器
- [x] `_draw_neon_border` 光晕参数重写（20px 扩散）
- [x] `_draw_intro_section` 删 `_frosted_frame`
- [x] `_draw_history_cards` 删 card_fill
- [x] 删除所有 `_draw_wave_divider` 调用
- [x] 删除装饰贴纸生成 + 贴图
- [x] `_draw_section_container` 去边框（只留半透明填充）

## 运行摘要

| 项目 | 内容 |
|------|------|
| 输出目录 | `output\邮件长图_王者荣耀世界_20260708_200058\` |
| Vision 结果 | art=fantasy / bg=very_dark / frame=glowing_neon / card=dark_glass / text=light |
| K-means 色 | bg_page=#070514 / accent_bright=#344BCA / accent_bright_alt=#7298FD |
| 画布 | 1920×7231（KV 等比缩放 + 4 区排版） |

## 代码改动清单（`scripts/email_poster/poster.py`）

| 改动 | 说明 |
|------|------|
| Vision prompt | 7→14 字段，maxtokens 512→768 |
| `_default_style_info` | 补 7 个新字段默认值 |
| `_build_design_system()` | **新增** — K-means + Vision → 统一 dict |
| `_build_decor_prompt(design)` | 读 `design["background_tone"]` 不再硬算 |
| `_generate_decor_bg(design)` | 接受 design dict |
| `_generate_decor_sticker` | 改签名去硬编码（当前未调用） |
| `_draw_section_container` | **新增** — dark_glass/light_glass/solid 四种风格 |
| `_draw_neon_border` | 光晕重写，GLOW_EXPAND=20，产品级发光 |
| `_draw_intro_section` | 删 `_frosted_frame`，纯文字 |
| `_draw_history_cards` | 删 `card_fill` |
| `make_email_poster` | 全链路接 `D = _build_design_system()`，删贴纸/wave/card_fill/frosted_frame |
| `run_email_poster.py` | 新增 `--brand-logo/--brand-name/--brand-sublabel` |
| `run_full_with_custom_prompt.py` | 新增同名参数 + 透传 |
| `changtu/micu_image_gen.py` | moxingpt 端点从 chat→images，403 自动匹配模型 |
| `.env` | MOXINGEMINI_MODEL→gemini-2.5-pro，MOXINGPT_MODEL→gpt-image-2-base64 |

## 最后执行

- 2026-07-08

## 恢复指令

读取 docs/progress.md，从上次中断的地方继续

---

# 经验教训

## 文件操作

- **Windows 下绝对不要用 PowerShell `Get-Content | -replace | Set-Content` 操作 UTF-8 文件。** 会导致 GBK 重编码，破坏所有非 ASCII 字符。只用 Edit 工具或 Python `open(encoding='utf-8')`。
- **非 git 项目先 `git init && git add -A && git commit` 再动手改。** 没有回退能力，一个误操作永久丢失。

## 架构设计

- **Vision 一旦分析出完整设计系统，代码里就不该再有硬编码。** 贴纸类型、边框风格、文字亮暗、背景深浅——Vision 已经给了答案，代码再自己算一遍就是重复工作。应该一步到位：Vision 出完整 JSON → `_build_design_system` 融合精确色 → 所有函数只读这个 dict。
- **K-means 取色和 Vision 分析各司其职。** K-means 给精确 hex，Vision 给语义决策（"文字应该用白色""背景是深色""边框用蓝光"），不互相替代。

## 视觉策略

- **深色背景下减法优先。** 波浪分隔→白线、容器 neon 边框→硬线、磨砂框 blur→黑方块。深色底色上大多数"装饰"效果适得其反。间距、排版层次、色彩本身足以区分区域。
- **不要主动生成角色型贴纸/吉祥物。** 用户对此零容忍。贴纸功能保留代码但不调用，除非用户明确要求。

## 交互

- **当前模型不支持图片输入，反馈循环全靠文字盲猜。** 遇到"看这里有问题"时，让用户用语言描述位置和现象，不要反复贴图试探。
