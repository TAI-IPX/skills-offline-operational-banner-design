# skills-offline-operational-banner-design

线下活动运营竖版长图自动生成工具（活动长图 + 战报 + 邮件长图 + 排行榜）。

## 环境

- Python >= 3.8
- 安装：`py -m pip install -e .`
- 可选：`py -m pip install -e ".[birefnet]"`（AI 抠图）、`py -m pip install -e ".[ranking]"`（排行榜渲染）
- **必须用 `py` 而非 `python`**（Windows 下 `python` 可能指向 Microsoft Store 存根程序，静默失败）

## 密钥

所有 Key 在 `.env` 中配置（复制 `.env.example`，勿提交 `.env`）：

| 分类 | Key 变量 | 命令行标志 | 用途 |
|------|----------|-----------|------|
| Gemini 编辑 | `GEMINI_API_KEY` | `--packy7s` / `--packy3s` | Vision 检测 + 扩图 + mask 编辑 |
| gpt-image-2 生图 | `PACKYGPT_API_KEY` | `--packygpt` | t2i 文生图 |
| gpt-image-2 生图 | `MICUAPI_API_KEY` | `--micugpt2` | t2i + Vision |
| gpt-image-2 生图 | `XINGCHENGGPT_API_KEY` | `--xingchengpt` | t2i 文生图 |
| gpt-image-2 生图 | `XINCHENGPT_API_KEY` | `--xinchengpt` | t2i 文生图 |
| Gemini 编辑 | `XINGCHENGEMINI_API_KEY` | `--xingchengemini` | Vision + 扩图 + mask |
| 即梦 | `VOLC_ACCESS_KEY_ID` + `VOLC_SECRET_ACCESS_KEY` | `--jimeng` | 火山引擎生图 |
| 可选 | `ANTHROPIC_API_KEY` | `--prompt-engine-claude` | Claude 推导描述 |

组合示例：`--xingchengpt --packy7s` = gpt-image-2 生图 + Gemini 编辑。

## 目录

| 路径 | 用途 |
|------|------|
| `scripts/` | 主入口脚本 + 管线模块 |
| `scripts/changtu/` | 活动长图合成管线 |
| `scripts/battle_report/` | 战报合成管线 |
| `scripts/email_poster/` | 邮件长图合成管线 |
| `scripts/ranking/` | 排行榜合成管线 |
| `docs/` | 流程规则、AI 协作规范等 |
| `input/` | 输入素材（图片、奖品等） |
| `output/` | 输出结果 |
| `fonts/` | 字体文件 |

## 入口脚本速查

### 主入口脚本

| 文件 | 功能 | 关键参数 |
|------|------|----------|
| `run_banner.py` | 最简入口：单图 → 单张 Banner | `-i 图片` `-m 主标题` `-s 副标题` `--preset 预设` |
| `run_all_presets.py` | 多尺寸批量合成 | `image` `-m` `-s` `-g 分组` `--skip-a4-outpaint` `--packygpt/--micugpt2` |
| `run_full_with_custom_prompt.py` | 全流程（描述→生图→叠字） | `--description/--description-file` `-m` `-s` `-g` `--prompt-engine` |
| `run_changtu.py` | 活动长图仅合成（复用已有 KV） | `--kv` `-m` `-s` |
| `run_battle_report.py` | 战报仅合成（复用已有 KV） | `--kv` `--report-dir` `-m` `-s` |
| `run_email_poster.py` | 邮件长图仅合成 | `--kv` `-m` `-s` `--prize-dir` `--method-dir` `--history-dir` |
| `run_ranking.py` | 排行榜仅合成 | `--csv` `--output-dir` `--skip-icons` `--skip-bg` |
| `run_mobile_presets.py` | 商店移动端日常管线 | `bg.png` `-m` `-s` |
| `run_from_a4.py` | 从 tianchong.png 直接出所有预设（跳过 A1-A4） | `image` `-m` `-s` `-g` |
| `run_wide_only.py` | 仅生成商店专题长图 3320×460 | `image` `-m` `-s` |
| `run_banner_compose_only.py` | 仅叠字合成（不跑 prepare_background） | `-i 背景图` `-m` `-s` `-o` |
| `run_hd.py` | HD 生产线（多人物→3840×1200） | `-p prompt` `-g` `--packy7s` `--images` |
| `run_shop_mobile_tianzige.py` | 商店移动端田字格 355×350 | `-i 输入` `-m 主标题` `-c 颜色` |

### 基础工具模块

| 文件 | 功能 |
|------|------|
| `_env.py` | 统一 .env 加载，带缓存 |
| `_packy.py` | 多后端 Key 调度，设置 `BANNER_IMAGE_BACKEND` |
| `_paths.py` | 路径定义、验证、`auto_extract_latest` |
| `ensure_python.py` | 检测可用 Python 解释器（跳过 Windows Store 存根） |

## 新增后端

本指南用于向项目中添加新的图像生成/编辑后端。已验证后端：gemini、packygpt、micugpt2、jimeng、t8star、nano-banana。

---

### Step 1: generate_from_description.py（生图核心）

文件：`.claude/skills/banner-background-from-description/scripts/generate_from_description.py`

#### 1a. 新增生图函数

```python
def _generate_image_xxx(
    prompt: str,
    output_path: str,
    reference_image: str | None = None,
) -> Optional[Path]:
```

职责：
- t2i（无 `reference_image`）：调文生图端点
- i2i（有 `reference_image`）：图生图或图片编辑

必须处理：
- API key 读取和验证（`sk-` 前缀）
- 代理自动检测（`winreg` + `HTTPS_PROXY`）
- 超时（t2i 180s，i2i 300-600s）
- 图片下载（`requests.get` + 代理）
- 返回 `Path` 或 `None`

#### 1b. 新增 Vision 函数（可选）

```python
def _vision_xxx(image_path: str, question: str) -> Optional[str]:
```

只在新后端支持图像识别时实现。

#### 1c. MODEL_ALIASES 注册

```python
MODEL_ALIASES = {
    ...
    "xxx": ("xxx", ["model-name"]),  # 别名 → (backend, [model_list])
}
```

#### 1d. dispatch 分支

在 `generate_image()` 中：
```python
if be == "xxx":
    result = _generate_image_xxx(prompt, output_path, reference_image=reference_image)
    if result is not None:
        return result
    print("[banner] XXX 生图失败。", file=sys.stderr)
    sys.exit(1)
```

在 `generate_from_description()` 的 i2i 分支：
```python
elif be == "xxx":
    result = _generate_image_xxx(prompt_i2i, temp_path, reference_image=reference_image)
    if result is None:
        print("[banner] XXX 图生图失败。", file=sys.stderr)
        sys.exit(1)
```

---

### Step 2: 入口脚本（共 8 个）

#### 2a. _packy.py（集中式后端处理器）

```python
# 块2 添加新分支
if getattr(args, "xxx", False):
    xxx_key = parsed.get("XXX_API_KEY") or os.environ.get("XXX_API_KEY")
    if xxx_key and str(xxx_key).strip().startswith("sk-"):
        os.environ["XXX_API_KEY"] = str(xxx_key).strip()
        os.environ["BANNER_IMAGE_BACKEND"] = "xxx"
    else:
        print("Error: 使用 -xxx 时请在 .env 中设置 XXX_API_KEY", file=sys.stderr)
        sys.exit(1)
```

#### 2b. argparse flag（8 个入口脚本）

每个文件加一行：
```python
parser.add_argument("--xxx", "-xxx", action="store_true", dest="xxx", help="...")
```

需要修改的脚本：
- `scripts/run_full_with_custom_prompt.py` — 含 inline 逻辑
- `scripts/run_all_presets.py`
- `scripts/run_banner.py`
- `scripts/run_hd.py`
- `scripts/run_from_a4.py` — 含 inline 逻辑
- `scripts/run_wide_only.py` — 含 inline 逻辑
- `scripts/run_hd_line.py` — 含 inline 逻辑（需改 `_apply_env_to_os` / `_make_env`）
- `scripts/_packy.py` — 集中处理器

#### 2c. inline 逻辑（4 个脚本）

`run_full_with_custom_prompt.py`、`run_from_a4.py`、`run_wide_only.py`、`run_hd_line.py` 有自己的 key 加载逻辑，需同步添加。

---

### Step 3: prepare_background.py（图像编辑，可选）

文件：`.claude/skills/banner-background-from-image/scripts/prepare_background.py`

只在需要后端做图像编辑（去干扰、扩图、修复）时修改。

#### 3a. _has_image_edit_key() 注册

```python
def _has_image_edit_key() -> bool:
    if BANNER_IMAGE_BACKEND == "xxx":
        key = os.environ.get("XXX_API_KEY", "").strip()
        return key.startswith("sk-")
    ...
```

#### 3b. _xxx_edit_image() 辅助函数

```python
def _xxx_edit_image(image_path, output_path, prompt, *, keep_returned_size=False):
```

必须处理：
- 尺寸约束（最低像素、最大 ratio、16 倍数等）
- 低于最低像素时自动 upscale → 编辑 → downscale
- 代理检测
- CDN 图片下载

#### 3c. _strip_direct_to_canvas() 分支

```python
if BANNER_IMAGE_BACKEND == "xxx":
    _xxx_edit_image(temp_canvas, output_path, STRIP_DIRECT_FILL_PROMPT)
elif BANNER_IMAGE_BACKEND == "yyy":
    ...
else:
    edit_image(...)  # Gemini 默认
```

3 个替换点：A1 去干扰、S5 扩图、S6b 修复。

#### 3d. _remove_text_with_gemini() 分支

如需在 A1 去干扰步骤启用新后端。

---

### Step 4: 配置与环境

#### 4a. .env

```bash
# XXX 后端（命令行加 -xxx）
# 文档: https://...
XXX_API_KEY=sk-your_token
```

#### 4b. .env.example

添加对应的注释示例行。

#### 4c. 入口脚本的 _ENV_KEYS 列表

`run_full_with_custom_prompt.py` 的 `_ENV_KEYS` 中加 `"XXX_API_KEY"`。

---

### 代理通用模式

所有后端函数复用以下代理检测逻辑：

```python
import winreg
_proxies = None
_sys_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
if not _sys_proxy:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
    if winreg.QueryValueEx(key, "ProxyEnable")[0]:
        _sys_proxy = winreg.QueryValueEx(key, "ProxyServer")[0]
        if _sys_proxy and not _sys_proxy.startswith("http"):
            _sys_proxy = "http://" + _sys_proxy
    winreg.CloseKey(key)
if _sys_proxy:
    _proxies = {"https": _sys_proxy, "http": _sys_proxy}
```

支持 `{BACKEND}_NO_PROXY=1` 环境变量跳过代理。

## 开发规范

> 记录于 2026-07-15，来源：邮件长图「巅峰对决不容错过」开发过程中的实际踩坑。

---

### 一、代码结构

#### 问题 1：嵌套函数破坏缩进
**现象**：在 `make_email_poster` 函数体内定义了 `def _draw_section_bg_box`，导致后续所有渲染代码（标题、分区循环、保存）跑到模块层级，函数隐式返回 `None`。  
**预防**：所有辅助函数一律定义在模块顶层，函数体内只写调用。代码审查时重点检查函数内是否有 `def`。

---

#### 问题 2：工具函数透传对象忽略参数
**现象**：`_load_font` 传入已加载的 `FreeTypeFont` 对象时直接返回，忽略 `size` 参数，导致主副标题都渲染成同一字号（200pt）。  
**预防**：工具函数接收对象时，明确用对象的属性重新构造（`ImageFont.truetype(path.path, size)`），禁止无条件 `return path`。加单元测试验证传入不同 size 时输出确实不同。

---

#### 问题 3：循环变量未初始化
**现象**：`sy = kv_display_h` 遗漏，section 渲染时 `UnboundLocalError`。  
**预防**：循环前强制列出所有在循环体内会被累加/读取的变量并赋初值，形成固定的"初始化块"。

---

#### 问题 4：replaceAll 误替换全局常量
**现象**：用 `replaceAll` 把 `COMBINED_BANNER_H` 全部替换为 `COMBINED_BANNER_DISPLAY_H`，连 API 生成高度参数也被替换，需手动逐一回滚。  
**预防**：`replaceAll` 仅用于局部变量、参数名、字符串字面量。全局常量改名用精确字符串替换（提供足够上下文），改完后 `grep` 确认无遗漏或误替换。

---

### 二、图层与渲染顺序

#### 问题 5：PIL 绘制顺序即图层顺序
**现象**：背景框 `_draw_section_bg_box` 在内容之后绘制，直接盖住文字。  
**预防**：在函数顶部用注释写出图层顺序清单，每次新增绘制操作时对照清单插入正确位置：

```python
# 图层顺序（从下到上）：
# 1. decor_bg
# 2. overlay（遮罩）
# 3. kv_image
# 4. brand_header / kv_title
# 5. section_banner
# 6. section_bg_box
# 7. section_content
```

---

#### 问题 6：全局遮罩位置反复返工
**现象**：遮罩位置改了三次才对：标题之后 → KV 之后 → KV 之前。  
**预防**：需求阶段先画图层草图，确认每层覆盖范围后再写代码，不在实现阶段反复调整。

---

#### 问题 7：常量职责混用
**现象**：`COMBINED_BANNER_H` 同时承担 API 生成尺寸和显示高度两个职责，改一个破坏另一个。  
**预防**：命名时加后缀区分职责：`_GEN_H`（生成尺寸）vs `_DISPLAY_H`（显示尺寸），出现两个不同场景时立即拆分。

---

### 三、数据与分区映射

#### 问题 8：数据-分区映射与业务语义不符
**现象**：`prizes`（奖品）绑在 event01，`history_items` 绑在 event03，与"奖品展示在 event03"的业务含义相反。  
**预防**：用一张映射表集中声明，而不是散落在各处：

```python
# event01: 活动时间 → event_date + date_images
# event02: 参与方法 → method_texts + screenshots
# event03: 奖品展示 → prizes
# event04: 活动规则 → intro_text
```

改映射时只改这一处，渲染和高度计算都从这里读。

---

#### 问题 9：高度预计算与渲染逻辑不同步
**现象**：`_calc_event*_height` 和 `_draw_*` 多次独立修改导致内容溢出或空白过多。  
**预防**：两者强制成对出现，命名一致（`_calc_event01_height` / `_draw_event01`），修改渲染逻辑时必须同步检查对应的预计算函数。

---

#### 问题 10：文字-截图 1:1 配对设计过窄
**现象**：截图比文字多时，多余截图被丢弃，只显示 1 张。  
**预防**：配对逻辑默认按 `max(len(a), len(b))` 遍历，缺少一方补 `None`，而不是按最短一方截断。

---

#### 问题 11：CLI 参数与素材目录未一一对应
**现象**：`--date-dir` 参数缺失，活动时间分区图片被遗漏。  
**预防**：设计 CLI 时先列出所有分区，每个分区对应一个 `--xxx-dir`，参数设计与素材目录结构同步完成。

---

### 四、API 限制

#### 问题 12：生图宽高比超限
**现象**：`1920×320` 宽高比 6:1 超过 API 上限 3:1，返回 400 报错。  
**预防**：封装 `validate_image_size(w, h)` 工具函数，调用 API 前统一校验宽高比，超限时自动调整并打印警告。生成尺寸与显示尺寸分开处理（生成 640，裁剪到 320 显示）。

---

### 五、缓存与文件管理

#### 问题 13：缓存路径与输出目录耦合
**现象**：缓存文件放在 `out_dir` 下，每次改 `--output-dir` 就换目录，缓存全部失效。  
**预防**：缓存目录独立配置（如固定为 `output/_cache/`），与每次运行的输出目录解耦，多次运行共享同一份缓存。

---

#### 问题 14：临时文件删除后忘记重建
**现象**：`section_titles_tmp.json` 清理后未重建，脚本静默回退到错误默认值，无任何警告。  
**预防**：临时文件缺失时打印明确警告而不是静默回退；或改为直接传参（`--section-titles`），不依赖外部临时文件。

---

#### 问题 15：默认值与业务语义脱节
**现象**：默认分区标题"往期中奖/游戏介绍"与业务叫法"奖品展示/活动规则"不符，每次不传参就显示错误标题。  
**预防**：默认值贴近最常见的业务场景，加注释说明"这是业务默认值"，上线前与业务方核对。

---

### 六、调试效率

#### 问题 16：长时间 API 调用无进度提示
**现象**：OCR 串行调用多张截图，每次 180s timeout，外层命令完全无响应。  
**预防**：每次 API 调用前后打印 `[开始]` / `[完成/失败]` + 耗时，串行多次调用显示进度 `[1/4]`。设置合理超时并在超时后打印明确提示。

---

#### 问题 17：关键路径缺少日志
**现象**：函数返回 `None`、图层被遮盖等问题靠反复运行才定位，没有日志辅助。  
**预防**：约定必须打日志的节点：函数入口参数、数据加载结果（几张图/几段文字）、每个分区高度预计算结果、图层绘制顺序。

---

#### 问题 18：无测试保护
**现象**：预计算与渲染逻辑紧耦合，改一处悄悄破坏另一处，没有任何断言。  
**预防**：至少写一个冒烟测试：给定固定素材，验证生成图尺寸正确、文件不为空、预计算高度与画布高度一致，每次改动后跑一遍。

---

### 七、协作与需求确认

#### 问题 19：核心设计决策应在动工前确认
**现象**：图层顺序、分区内容映射、配对规则都是边做边发现，导致反复返工。  
**预防**：接到任务后先输出"设计确认单"：每个分区展示什么内容、图层从上到下的顺序、CLI 参数列表。用户确认后再写代码。

---

#### 问题 20：多处改动一起运行难以定位
**现象**：多次改动后一次运行，出错时难以判断是哪次引入的问题。  
**预防**：每次只改一个逻辑点，立即运行验证，确认无误再继续，不攒多个改动一起跑。

---

#### 问题 21：间距常量命名不清晰
**现象**：`SECTION_PAD_BOTTOM`、`BADGE_CONTENT_GAP`、`SECTION_GAP` 用途交叉，容易改错。  
**预防**：格式统一为 `FROM_TO_GAP` 或加注释说明"谁到谁的距离"，新增常量前先检查是否已有同语义的常量。

## 流程与规则

### 一、整体流程

本仓库支持两种入口：

#### 1. 图片输入 → Banner（run_all_presets.py）

| 阶段 | 说明 | 输出 |
|------|------|------|
| **Step 1** | prepare_background：去干扰 → 主体检测 → 对齐安全区 → 拼画布 → Gemini 填空白 | 各规范尺寸 step1 |
| **Step 2** | compose：叠渐变蒙层 + 主标题 + 副标题 | 各规范最终 Banner |

#### 2. 描述输入 → Banner（run_full_with_custom_prompt.py，方案 A）

| 阶段 | 说明 | 输出 |
|------|------|------|
| **Step 1** | 文生图（描述→背景）：API 生图 → crop 到目标画布 | `bg.png` |
| **Step 1b** | 文字艺术字管线（`--text-art`）：API 生图 → 亮度蒙版抠图 → RGBA | `text_art_rgba.png` |
| **Step 1c** | 对话框横幅（自动取色）：裁切背景 `dialog_rect` 区域 → 取主色 → PIL 绘制六边形 | `dialog_raw.png` |
| **Step 2** | compose：背景 cover-scale + 贴艺术字 + 贴对话框 | 最终 Banner |

**环境**：需设置 `GEMINI_API_KEY`（可从项目根 `.env` 读取）。Python 使用 `py` 命令（Windows Python Launcher），详见 `scripts/ensure_python.py`。

**生图/图编后端**：默认使用 **nano-banana-2**（需安装 Bun）。文生图（description→图）与图像编辑（outpaint/去字）均优先走 nano-banana，失败时回退到 Gemini API。可通过环境变量 `BANNER_IMAGE_BACKEND=gemini` 强制仅用 Gemini API；`NANO_BANANA_EXE` 可指定 nano-banana 可执行文件路径。

---

### 二、共享规范（画布与安全区）

- **画布尺寸**：默认 **1976 × 464**（与 banner-composer 一致）。
- **安全区**（固定数值，不按比例换算）：
  - **x = 770～1457**
  - **y = 0～464**
- **用途**：主体须落在安全区内；主标题、副标题也落在安全区内（由 compose 规范规定）。

---

### 三、Step 1 详细流程（A1～A5，safe_zone_scale_outpaint）

| 步骤 | 说明 | 输出 |
|------|------|------|
| **A1** | 去干扰：Gemini 去除叠加文案与干扰元素 | 与输入同尺寸（仅当 `--remove-text` 时执行） |
| **A2** | 主体 bbox 检测：Gemini Vision 检测主体框 | `(x_min, y_min, x_max, y_max)` 比例 0～1 |
| **A3** | 标注保存：在图上画 bbox 红框并保存 | `output/zhuti.png` |
| **A4** | 填充画面：以 bbox 区域为中心向四周延展填充，保持 bbox 内不变；不新增人物或文字；生成 4096×1024；未填满则重填 | `output/tianchong.png` |
| **A5** | 按画布裁切：主体 bbox 等比缩放到安全区 90%，中心对齐后裁切 | `output/step1_prepared_background.png` |

#### A1) 去干扰（Gemini remove-text）

- **条件**：`--remove-text` 时执行。
- **规则**：去除促销文案、日期、logo、色块、按钮、UI、徽章、文字阴影；按周围背景/人物外观自然填充；不改变未被叠加覆盖的画面；输出与输入同尺寸。
- **提示词**：`INPAINT_REMOVE_TEXT_PROMPT`。

#### A2) 主体 bbox 检测（Gemini Vision）

- **规则**：主体为整个人物/角色（头+躯干+主要肢体）；bbox 须完整框入头部（含头发、头饰）、双手（含指尖）、重点特征（肩饰、飘带等）。
- **提示词**：`SUBJECT_PROMPT_BBOX`。
- **输出**：`(x_min, y_min, x_max, y_max)`，比例 0～1。

#### A3) 标注保存

- 在去干扰图上绘制主体红框并保存。**输出**：`output/zhuti.png`。

#### A4) 填充画面

- **规则**：合成时主体 bbox 中心落在画面**水平 2/3 处**（纵向居中），主体 bbox 约占画布 75%；再以 bbox 区域为中心向四周做延展填充，保持 bbox 内区域不变；不新增人物或文字；生成一张尺寸 **4096×1024** 的图片；检查是否有没填充完整的地方，如果有则重新填充。
- **提示词**：`OUTPAINT_FILL_TO_3840x1080_PROMPT`。
- **输出**：`output/tianchong.png`。

#### A5) 按画布裁切

- **规则**：① 识别 tianchong.png 的主体区域（Gemini Vision）；② 读取规范的安全区；③ 主体 bbox 等比缩放到安全区 90%，中心对齐后裁切。
- **实现**：`_crop_step5_to_canvas`（在 tianchong 上检测主体 → 读安全区 → 等比缩放整图使主体 bbox 为安全区的 90% → 中心对齐后裁切 width×height）。
- **产出**：`output/step1_prepared_background.png`（最终背景图）。

---

### 四、Gemini 返回尺寸处理规则（gemini_image_edit.py）

- **返回尺寸 = 输入尺寸**：直接使用。
- **返回尺寸 ≥ 输入尺寸**：缩小到输入尺寸（1976×464）后保存。
- **返回尺寸 < 输入尺寸**：**不放大**；用**原图**覆盖输出（避免小图放大变糊）。  
  - 副作用：若 Step 5/5b 返回小图，则空白未被填充，可能留下黑边；后续可改为「重试或报错」策略。

---

### 五、Step 2 规则（compose_banner）

- **输入**：Step 1 的背景图 + 主标题 + 副标题。
- **画布**：1976×464（或预设）。
- **主标题**：微软雅黑 Bold，52pt，位置 (567, 183)；AI 智能换行（8 字/行回退）。
- **副标题**：微软雅黑 Regular，28pt，位置 (567, 254)，80% 不透明度。
- **渐变蒙层**：全画布，左黑→右透明，不透明度 40%；顺序：背景 → 渐变 → 主标题 → 副标题。
- **输出**：`output/office_visual_banner_upload_test.png`（或配置的 OUTPUT）。

---

### 六、配置摘要（run_banner.py 当前）

| 项 | 值 |
|----|-----|
| 图片 | `IMAGE`（需在 run_banner.py 中配置路径） |
| 主标题 | 办公视觉效率 |
| 副标题 | 从设计到出图快人一步 |
| 画布 | 1976×464 |
| Step 1 结果 | `output/step1_prepared_background.png` |
| Step 2 结果 | `output/office_visual_banner_upload_test.png` |
| 参数 | `--preset default --remove-text --safe-zone-scale-outpaint` |

---

### 七、strip（1470×200）主体未落安全区的原因

- **现象**：用 `run_all_presets.py` 跑「所有规范」时，strip 输出（1470×200）中主体可能未落在该画布的安全区（x=512～1312，y=53～171）。
- **原因**：
  1. Step 1 只按 **default 预设（1976×464）** 跑一次 prepare_background，得到的 `step1_prepared_background.png` 是按 **default 的安全区**（752～1457）做「主体 90% 安全区、中心对齐」裁切的。
  2. strip、wide 等其它预设**共用这一张 step1**，compose 时只是把 step1 **按 cover 缩放**到 1470×200（或 3320×500），**没有按 strip/wide 的安全区重新裁切**。
  3. 因此主体在 strip 画布上的位置完全由 default 的裁切结果决定；strip 的安全区是居中 (512～1312)，与 default 的安全区（偏右 752～1457）形状和位置都不同，主体容易偏左/偏右或超出 strip 安全区。
- **可行做法**：若要求 strip（或 wide）主体严格落在各自安全区，需**按该预设单独跑一次 prepare_background**（例如 `--preset strip`），得到针对 1470×200 安全区裁切后的 step1，再仅对该 step1 做 compose strip。

---

### 八、已知问题与规避

#### 1. 多 Key 架构与 401 问题

- **架构**：PackyGPT（gpt-image-2）生图 + Gemini（图像编辑/主体检测）两条独立 API Key。`.env` 中同时配 `PACKYGPT_API_KEY` 和 `GEMINI_API_KEY`。
- **问题**：代码曾把 PackyGPT key 覆写到 `GEMINI_API_KEY`，导致 Gemini 编辑 401。已修复为不覆写。
- **问题**：Windows 用户级环境变量 `GEMINI_API_KEY` 优先于 `.env` 文件。`.env` 的值会被系统变量覆盖。
- **规避**：删除系统级 `GEMINI_API_KEY`（`[Environment]::SetEnvironmentVariable('GEMINI_API_KEY', $null, 'User')`），让 `.env` 生效。
- **问题**：`BANNER_IMAGE_BACKEND` 在 Step1/Step2 间传递不当会污染 Gemini 编辑路由。已修复为 Step 2 独立 env。
- **Key 权限**：PACKY7S key 需在 Packy 控制台勾选包含 `gemini-3.1-flash-image-preview` 的分组。

#### 2. 入口命令须用 `py` 而非 `python`

- **问题**：Windows 的 `python` 命令可能指向 `WindowsApps\python.exe`（Microsoft Store 存根），不会实际执行 Python，导致脚本无输出、静默失败。
- **规避**：所有 Python 命令用 `py` 开头，如 `py scripts/run_shop_mobile_tianzige.py`。
- **脚本层面**：`ensure_python.py` 已跳过 WindowsApps 存根，优先使用 `py` 路径；但 bash 入口仍须用 `py` 才能启动脚本。

#### 3. 自动提取图片可能拿错

- **问题**：脚本不传 `-i` 时，自动从 OpenCode DB 提取图片（`opencode_image_input.extract_latest()`），可能提取到旧图片。
- **规避**：明确用 `-i` 指定路径：
  ```bash
  py scripts/run_shop_mobile_tianzige.py -i input/xxx.png -m "标题" -c 蓝色
  ```
- **前提**：先确认目标图片已存在于 `input/` 目录。

#### 4. 多色/多版本输出互相覆盖

- **问题**：`run_shop_mobile_tianzige.py` 每次输出 `商店移动端田字格355x350.png`，多次运行后一个版本覆盖上一个。

#### 5. A4 扩图不完整导致黑边

- **问题**：Gemini A4 扩图有时输出尺寸小于目标（如 2064×512 而非 4096×1024），裁切时将黑色未填充区域带入最终结果。
- **规避**：`--skip-a4-outpaint` 跳过 A4，由 compose 的 `_paste_background` cover-scale 直接填满画布。对 `--packygpt` / `--packy7s` 已自动加此标志。

#### 6. 对话框透明通道丢失

- **问题**：`_paste_dialog()` 曾用 `convert("RGB")` 丢弃 alpha，六边形外透明像素变黑边。
- **修复**：改为 `convert("RGBA")` + `paste(dialog, (x,y), dialog)` 保留 alpha 蒙版。

#### 7. 亮度蒙版方向

- **问题**：白底黑字艺术字用 `255-x` 正确；黑底白字需 `x`。硬编码单向会导致文字被抠掉。
- **修复**：自动检测 `np.array(gray).mean() > 128` 选择蒙版方向。
- **适用场景**：纯色背景文字艺术字（白底/黑底），比 BiRefNet 更快更干净。
- **不适用**：自然图像抠图仍用 BiRefNet（人物/物体）。

---

### 九、决策原则（workflow 摘要）

- 是否裁切、是否扩图，以**目标宽高下最佳画面效果**为准。
- 主体须落在**安全区**内（default：x=752～1457，y=0～464；strip：x=512～1312，y=53～171；等）。
- 上传图对齐到安全区后，四周「空白」由 **Gemini 填充到画布尺寸**，不保留黑边为设计目标。

---

### 十、BANNER_BG_SIZE 环境变量（v2 新增）

控制 Step 1 `bg.png` 生图尺寸，不再绑定具体画布像素：

| 设置 | 效果 |
|------|------|
| `BANNER_BG_SIZE=1024x640` | bg.png 固定 1024×640 |
| （未设置） | packygpt/micugpt2 → 1024×640（原生）；其他 → 1920×1080（16:9） |

优先级：`--width --height` 命令行 > `BANNER_BG_SIZE` 环境变量 > 后端默认值

### 十一、context_prompt 辅助 Vision 检测（v2 新增）

Step 1 写入 `run_dir/prompt.txt` → Step 2 自动读取并传递给 Gemini Vision。

效果：Gemini 收到 `"Image content hint: {生图描述} ... Identify the MAIN subject..."`，bbox 检测更准确。

### 十二、多后端关键约束（v2 补充）

- **if/elif 链**：所有后端选择必须单一链路，严禁独立 if 块覆盖（3 处已修复）
- **BANNER_IMAGE vs BANNER_EDIT**：IMAGE_BACKEND 优先用于 strip S5/S6 分发，EDIT_BACKEND 仅作回退
- **S5b sentinel 阈值**：暗色物料（羊毛毡深棕等）需阈值 > 25 才能正确保护主体

### 十三、快速诊断

| 症状 | 根因 | 检查点 |
|------|------|--------|
| 生图走 Gemini 而非 gpt-image | if/elif 链 bug（3 处已于 2026-06 修复） | 日志有无 `[packygpt]`/`[micugpt2]` |
| packygpt/micuapi Vision 走 Gemini | gpt-image-2 不支持 Vision，需走 Gemini | Vision 日志 |
| packygpt 编辑返回黑边/未填充 | 旧版无 mask，编辑区域不可控 | 升级到 mask 路径（2026-06） |
| strip 扩图走 Gemini | EDIT_BACKEND 优先 | S5 日志 |
| bbox 不准 | context_prompt 未注入 | 日志有无 `✅ 已加载` |
| wide 无 BiRefNet | tianchong 不存在 + 回退失效 | Step1b 日志 |
| 人物消失（暗色风格） | sentinel 阈值 < 5 | S5b |

---

### 十四、scripts/ 文件清单

见上方「入口脚本速查」。

---

### 十五、API 约束与后端选用

#### API 约束速查

| 约束 | packyapi | micuapi |
|------|----------|---------|
| t2i 端点 | `/v1/images/generations` | `/v1/images/generations` |
| i2i 端点 | `/v1/images/edits`（multipart，支持 mask） | `/v1/chat/completions`（JSON base64） |
| 最大宽高比 | 无限制（已验证 8:1） | 无限制（已验证 1:8） |
| 最小像素 | ≥ 655,360 | 未限制 |
| 尺寸 16 倍数要求 | 必须 | 未限制 |

#### 后端选用建议

| 场景 | 推荐 | 原因 |
|------|------|------|
| 高质量背景生成 | `--packy7s` | Gemini 模型画质好 |
| 1:8 极端比例直出 | `--micugpt2` | gpt-image-2 无比例限制 |
| 纯生图（无需编辑） | `--packygpt` | gpt-image-2 速度快 |
| 国内直连 | `--packy7s` 或 `--packygpt` | 无需翻墙 |

#### 抠图方案选择

| 场景 | 方案 |
|------|------|
| 纯色背景文字 | 亮度蒙版（毫秒级，零依赖，自动检测底色） |
| 自然图像（人物/物体） | BiRefNet（AI 模型，耗时但精度高） |
