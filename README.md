# skills-offline-operational-banner-design — 线下活动运营竖版长图自动生成工具

活动长图 + 战报 + 邮件长图 + 排行榜一键生成。

## 技能列表

| 技能 | 说明 |
|------|------|
| **battle-report-composer** | 从 KV 图 + 截图素材 + 数据指标合成竖版战报长图（1080px 宽） |
| **banner-background-from-image** | 用用户提供的图片制备背景（裁剪/扩图、安全区、可选去字） |
| **banner-background-from-description** | 根据文案描述用 AI 生成背景图 |
| **banner-composer** | 从背景图 + 主标题 + 副标题合成横幅图 |
| **prompt-engine** | 主副标题→高质量中文文生图 Prompt（6 步推导 + 质检评分） |
| **skill-creator** | 创建与维护新技能的指南与脚本 |

## 快速开始

### 环境要求

- Python >= 3.8
- **必须用 `py` 而非 `python`**（Windows 下 `python` 可能指向 Microsoft Store 存根）

### 安装

```bash
py -m pip install -e .
# 可选
py -m pip install -e ".[birefnet]"   # AI 抠图
py -m pip install -e ".[ranking]"    # 排行榜渲染
```

### 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入对应 Key（GEMINI_API_KEY / XINGCHENGGPT_API_KEY / MOXINGPT_API_KEY 等）
```

### 使用

```bash
# 活动长图（全流程）
py scripts/run_full_with_custom_prompt.py -g 活动长图 --xingchengpt --packy7s \
  -m "主标题" -s "副标题" --event-date "活动时间" \
  --prize-dir input/prizes --rules "规则一|规则二|规则三"

# 战报（全流程）
py scripts/run_full_with_custom_prompt.py -g 战报 --xingchengpt \
  --report-dir <素材目录> -m "主标题" -s "副标题" \
  --stat-group "标题|标签|值|标签|值" --font-family "字体名"

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


## 项目结构
```
.
├── .env                     # API 密钥（勿提交）
├── .env.example             # 密钥模板
├── AGENTS.md                # Agent 协作说明
├── pyproject.toml           # 依赖配置
├── .claude/skills/          # 技能脚本
│   ├── banner-background-from-description/  # 文生图
│   ├── banner-background-from-image/       # 图生背景
│   ├── banner-composer/                    # 横幅合成
│   ├── battle-report-composer/             # 战报合成
│   ├── banner-spec/                        # 画布预设与安全区
│   └── prompt-engine/                      # Prompt 生成系统
├── scripts/                 # 主入口脚本 + 管线
│   ├── changtu/             # 活动长图合成（KV + 取色 + AI 背景 + 三区排版）
│   ├── battle_report/       # 战报合成（KV + 截图 + 数据卡）
│   ├── email_poster/        # 邮件长图合成（KV + EVENT01~04 四区）
│   ├── ranking/             # 排行榜合成（CSV→JSON + 图标 + 背景 + 截图）
│   ├── hd/                  # HD Banner 管线
├── docs/                    # 文档
├── input/                   # 输入素材（图片、奖品等，含 uploads/）
├── output/                  # 输出结果
└── fonts/                   # 字体文件
```

## 文档

- [流程与规则](docs/流程与规则.md)
- [AI 协作规范](docs/AI协作规范.md)
- [战报规范](docs/战报规范.md)
- [图片处理说明](docs/图片处理说明.md)
- [新增后端指南](docs/新增后端指南.md)
- [开发经验教训](docs/开发经验教训.md)
- [Icon 批量下载指南](docs/icon-fetch-guide.md)
