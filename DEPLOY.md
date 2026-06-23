# 封面生成管线 · 交付说明

单文件管线 `pipeline.py`：本地模板编译 prompt → `gemini-3.1-flash-image` 出图
（**每张封面 = 1 次模型调用**，无文本模型前置）→ 本地裁 16:10 → 真字体排版中文标题。
架构对齐后端 `cover_engine.build_prompt()`；内置用例对齐 `cover-generation-test-cases.md` §2。

## 快速跑通

```bash
pip install -r requirements.txt
cp .env.example .env          # 填 GEMINI_API_KEY
python pipeline.py            # 跑内置 11 个测试用例
python pipeline.py requests.json   # 自定义批次
```

`requests.json` 形如：

```json
[{"product_type": "云课堂", "title": "Rust 内存模型", "brief": "所有权与生命周期"}]
```

- `product_type` 可省（标题/简介关键词路由：代码实验室 / 互动场景 / 云课堂）
- `brief` ≈ 后端 `subtitle`；为空时 Core Concept 回退用 `title`（与后端一致）
- `title` 为空 → 无字纯氛围封面（对应 WS-04 regenerate 现状）

输出 `output_covers_gemini/NN_类型.png` + `manifest.json`（每张的 prompt / spec /
composition / font / image 路径全记录，失败条目 `image=null`）。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `GEMINI_API_KEY` | 必填 | `.env` 或环境 |
| `IMAGE_MODEL` | `gemini-3.1-flash-image` | 出图模型 |
| `WORKERS` | `6` | 出图并发数，遇 429 限流调小 |

## 部署注意

1. **字体路径与授权（最重要）**：`FONT_STYLES` 里全是 `C:/Windows/Fonts/` 路径，
   Linux 部署需自带字体文件并改路径。思源黑体/宋体（`Noto*SC-VF`，OFL 协议）可随服务
   分发；**华文楷体/仿宋/隶书/新魏/行楷、幼圆、微软雅黑是 Windows/Office 授权字体，
   不可拷到服务器**。OFL 替代：楷体 → 霞鹜文楷；找不到替代的条目直接从 `FONT_STYLES`
   删掉即可——字体分配按候选列表逐级回退，池子缩小会自动收敛，不需要改其他代码。
2. **SOCKS 代理**：环境存在 `ALL_PROXY=socks5://…` 时 httpx 会报错，
   `pip install httpx[socks]` 或清掉该变量（保留 `HTTPS_PROXY=http://…` 即可）。
3. **重试**：`render()` 内置 3 次指数退避，SSL 瞬断 / 偶发限流靠它兜。

## 后端移植要点

三块纯函数可直接搬走，互相解耦：

| 模块 | 函数/数据 | 用途 |
|---|---|---|
| prompt 模板 | `compile_cover()` + `PLATFORM_DNA` / `AVOID_CLAUSE` / `TYPE_VIBE` / `POOLS` / `COMPOSITIONS` | 替换现 `build_prompt()` 的模板段（平台 DNA、去 AI 味清单、三类调性已固化） |
| 多样性分配 | `assign_variants()` + `_font_prefs()` | 批量场景防同质：媒介×色族×构图×字体四轴轮换 |
| 标题排版 | `draw_title_overlay()` 及其下排版函数 | 中文标题真字体合成：自适应折行/超长压缩/亮度自动对比/压印质感；输入 PIL Image + 标题 + 构图字符串 + 字体键 |

换 OPENROUTER 出图通道时只需重写 `render()`（输入 prompt 字符串，返回 PIL Image）。

## 交付清单

```
pipeline.py                      # 主程序（唯一代码文件）
requirements.txt                 # 3 个依赖
DEPLOY.md                        # 本文件
.env.example                     # 环境变量模板（不要用真实 key 的 .env）
cover-generation-test-cases.md   # 测试用例基准（内置 DEMO_REQUESTS 与之对齐）
skills/cover-art-director/       # 风格池设计文档（维护 POOLS/模板时参考，非运行依赖）
output_covers_gemini/            # 11 张验收样张 + manifest.json
```
