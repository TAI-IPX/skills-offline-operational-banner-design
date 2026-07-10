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

## 快速命令

```bash
# 活动长图（全流程）
py scripts/run_full_with_custom_prompt.py -g 活动长图 --xingchengpt --packy7s \
  -m "主标题" -s "副标题" --event-date "活动时间" \
  --prize-dir input/prizes --rules "规则一|规则二|规则三"

# 活动长图仅合成（跳过 Step1，复用已有 KV）
py scripts/run_changtu.py --kv input/kv.jpg -m "主标题" -s "副标题" --xingchengpt

# 战报（全流程）
py scripts/run_full_with_custom_prompt.py -g 战报 --xingchengpt \
  --report-dir <素材目录> -m "主标题" -s "副标题" \
  --stat-group "标题|标签|值|标签|值" --font-family "字体名"

# 战报仅合成（跳过 Step1，复用已有 KV）
py scripts/run_battle_report.py --kv input/KV.jpg --report-dir <素材目录> \
  -m "主标题" -s "副标题"

# 邮件长图（全流程）
py scripts/run_full_with_custom_prompt.py -g 邮件长图 \
  -m "主标题" -s "副标题" --kv input/kv.png --xingchengpt \
  --event-date "2026/7/6-2026/10/10" \
  --prize-dir input/prizes --prize-order "礼盒2|礼盒1|礼盒4|礼盒3" \
  --method-dir input/screenshots \
  --method-desc "在联想应用商店...|在LegionZone..." \
  --history-dir input/history --history-order "礼品1|礼品4|礼品3|礼品2" \
  --intro-text "游戏介绍文字..."

# 邮件长图仅合成（跳过 Step1，复用已有 KV）
py scripts/run_email_poster.py --kv input/kv.png -m "主标题" -s "副标题" --xingchengpt \
  --event-date "2026/7/6-2026/10/10" \
  --prize-dir input/prizes --prize-order "礼盒2|礼盒1|礼盒4|礼盒3" \
  --method-dir input/screenshots \
  --method-desc "在联想应用商店...|在LegionZone..." \
  --history-dir input/history --history-order "礼品1|礼品4|礼品3|礼品2" \
  --intro-text "游戏介绍文字..."

# 排行榜（全流程，CSV→JSON + 图标 + 背景 + 截图）
py scripts/run_full_with_custom_prompt.py -g 排行榜 --xingchengpt \
  --ranking-csv "input/ranking/榜单.csv" --ranking-theme gold

# 排行榜（跳过 AI 背景，用 CSS 渐变兜底）
py scripts/run_full_with_custom_prompt.py -g 排行榜 \
  --ranking-csv "input/ranking/榜单.csv" --skip-bg

# 排行榜仅合成（复用已有数据，跳过图标和背景）
py scripts/run_ranking.py --csv output/排行榜_xxx/data.json \
  --output-dir output/排行榜_xxx --skip-icons --skip-bg
```

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
