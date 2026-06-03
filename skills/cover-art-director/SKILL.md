---
name: cover-art-director
description: >
  为平台三类产品（云课堂 / 代码实验室 / 互动场景）生成高质量、风格统一又各具特色的封面图 prompt，
  面向 Nano Banana（gemini flash image）及其他文生图模型。当用户需要为课程、notebook 实验、
  多 Agent 互动场景生成封面图 / 卡片图 / Banner / 缩略图 / 题图，或提到 cover、封面、配图、
  文生图 prompt、Nano Banana、批量出图时使用。即使用户没有明确说"封面"，只要是在为这三类产品
  生成展示用主视觉图，也应触发。当输入里带有 title 字段、产品类型或一批要批量出图的条目时尤其要使用。
---

# Cover Art Director

为一个学习平台生成封面图 prompt。平台有三类产品，每类有自己的视觉领地，但整体看上去要像同一个品牌出品。

这个 skill 的工作不是"写一句华丽的 prompt"，而是**做艺术指导**：判断产品类型 → 选定该类型的视觉领地 → 在池子里挑一个不重复的组合 → 套上全平台共享的"质感 DNA" → 组装成一条可直接喂给 Nano Banana 的英文 prompt。

## 它要同时解决的三个矛盾

1. **统一 vs 区分**：三类产品要像一家人，但又必须一眼能区分开。统一**不靠固定配色**（平台主题是暖紫，但封面配色要多元）——统一靠的是共享的**手工质感、构图克制、光照逻辑、去 AI 味的成片标准**。区分靠的是每类产品不同的**色彩领地 + 媒介 + 母题**。
2. **多样 vs 杂乱**：配色要多元但不能乱。做法是每条 prompt 只用 **2–3 个锚定色 + 中性色**，且色板从该产品类型的"和谐色族"里取——多样来自轮换色族，而不是每张都堆满彩虹。
3. **有特色 vs AI 味**：每张图是一个被认真执行的单一想法（像 Behance/编辑设计作品），而不是"赛博朋克或玻璃拟态或瑞士风都行"的大杂烩。后者正是 AI 味的来源。

## 工作流程

按顺序做这几步，最后产出 prompt：

1. **识别产品类型**（见下"产品类型路由"）。输入里通常有显式类型；没有就从标题/简介关键词判断。判不准时，向用户确认，不要瞎猜。
2. **打开风格池**：读 `references/style-pools.md` 里对应类型那一节，拿到它的色族、媒介、母题、构图原型和范例。
3. **把标题/概念翻译成一个具体的视觉隐喻**——不要照搬字面（"Rust 内存模型"不是画一块内存条，而是"所有权与边界"的视觉化）。一张图一个核心想法。
4. **挑一个不重复的组合**：媒介 × 色族 × 构图原型 × 母题。批量出图时按"多样引擎"轮换，保证相邻封面至少在媒介和色族上不同。
5. **套上平台 DNA**（见下），让它和全平台同源。
6. **处理标题**（若传入 title，见"标题处理"）。
7. **按 prompt 结构组装**，输出英文 prompt + 一行规格说明。

## 产品类型路由

| 产品类型 | 指向 | 关键词信号 |
|---|---|---|
| **云课堂** Cloud Classroom | 课程 tutorial、学习路径、结构化讲义、被引导的学习过程 | course, tutorial, 课程, 讲义, 学习路径, lesson, 入门, 进阶, 体系, 路线 |
| **代码实验室** Code Lab | JupyterLab、notebook、code、data、experiment、computational workspace | notebook, jupyter, 实验, code, 数据, data, 量化, 模型训练, pipeline, kernel |
| **互动场景** Interactive Scenarios | 多个 AI Agent 的对话环境、多角色协作、多智能体讨论、任务分工 | agent, 多智能体, 协作, 对话, 角色, 讨论, 分工, multi-agent, roleplay, 沙盒 |

显式传入的产品类型永远优先于关键词推断。

## 平台 DNA（三类共享，统一感来自这里）

把这些当成"这家品牌出品的成片标准"，无论什么颜色、什么题材都成立：

- **一张图一个想法，认真执行**。像一位真人艺术总监做的编辑级作品，不是 stock 3D 渲染。
- **克制的色板**：2–3 个锚定色 + 中性色（米白/象牙/石墨/纸色之一）。颜色是被选择的，不是被堆砌的。
- **真实的光照逻辑**：有一个可信的主光源和方向，阴影自洽——即使是抽象画面。
- **留白与呼吸感**：构图不挤；留白同时也是标题安全区。
- **哑光手工质感（品牌签名）**：matte finish、细腻胶片颗粒、干净的几何骨架。**不要**塑料高光、廉价反光、玻璃拟态滥用。这层"哑光 + 几何骨架 + 颗粒"是让三类产品看起来同源的暗线。
- **16:10 画幅**，主体不顶满四边，给标题留出干净区域。

## 去 AI 味清单（在 prompt 里显式排除）

文生图模型默认会滑向这些"AI 味"陷阱，必须主动避开。把这些浓缩进 prompt 的 avoid 段：

> no glowing neon circuit boards, no hexagon grids, no matrix code rain, no generic "tech blue gradient on black", no chrome spheres, no robot heads or glowing brains, no plastic glossy 3D render, no fake bokeh everywhere, no lens flare spam, no floating UI panels, no centered symmetric hero blob, no cluttered composition, no garbled or misspelled text.

并且正向地要求：单一光源、有意的非对称、真实材质/媒介、克制配色、编辑级成片。

## Prompt 结构

不要每次套同一个句子骨架——那本身就是模板化。按下面**信息块**组装，但每次可以变换语序、开头和措辞，让 prompt 读起来不像流水线产出。一条 prompt 通常含这些块（英文）：

1. **质感框定**（简短，别注水）：editorial-quality cover art, art-directed, looks hand-crafted.
2. **核心视觉隐喻**：由标题/概念翻译来的那一个想法。
3. **媒介 + 风格**：来自该产品类型风格池。
4. **构图 + 画幅 + 标题安全区**：构图原型 + 16:10 + 留出标题区域。
5. **色板**：点名 2–3 个具体色 + 中性色（取自该类型色族）。
6. **光照 + 成片质感**：平台 DNA（哑光、颗粒、单一光源）。
7. **标题排版规格**（若有 title）。
8. **avoid 段**：去 AI 味清单的浓缩版。

> Nano Banana（Gemini flash image）走 `generate_content(contents=[prompt])`，**没有独立的 negative prompt 字段**，所以排除项要写进正文（用 "no ..." 短语）。

## 多样引擎（防模板 / 防同质）

模型没有记忆，连续出图很容易雷同。主动制造差异：

- **轮换四个维度**：媒介、色族、构图原型、母题。批量出图时，让相邻两张**至少**在媒介和色族上不同。
- **确定性轮转**：若输入带索引/序号，用它对池子取模来选媒介和色族（如 `medium = mediums[i % len]`），这样整批可控地铺开、不撞车。
- **构图原型**（三类通用，可与各自媒介自由组合）：左主体右留白、满版场景、居中带边距、对角动势、网格/三联、微距特写、俯视平铺。
- 一旦发现连续几条 prompt 长得像，换一个媒介或母题，不要靠堆细节硬凑差异。

## 标题处理

只有当输入带 `title` 字段时才在图里渲染文字；`subtitle`/简介一般只作为概念输入、**不**渲染（除非用户明确要求）。

Nano Banana 渲染短文字还算可靠，但仍要约束：

- 在 prompt 里**用引号给出要渲染的确切文字**，并要求 "spell exactly, no extra words"。
- 标题尽量短。过长时按原文渲染，但提醒用户文字越长越容易出错。
- 排版规格：clean modern sans-serif（或按品牌指定），单一字体，水平排版，高对比、高可读，放在为它预留的留白区里，作为有意设计的版式元素——不是贴上去的水印。
- 颜色：让标题色与背景拉开对比，可从色板里取中性色或锚定色。

标题排版示例片段：

> Integrate the title text "Rust 内存模型深度拆解" as a deliberate typographic element: clean modern sans-serif, horizontal, high legibility, placed in the reserved negative space on the lower-left; spell it exactly with no extra words.

## 输出格式

为每个请求输出：

1. **The prompt**（英文，可直接粘贴进 `generate_content`）。放在代码块里方便复制。
2. **一行规格说明**：`类型 · 媒介 · 色族 · 构图原型`，让用户一眼知道这张走的什么路子，也方便复盘多样性。

批量请求时，逐条输出 prompt + 规格说明，并确保整批在媒介和色族上铺开。

**输出示例（单条）：**

```text
Editorial-quality course cover art, art-directed and hand-crafted. A winding luminous path
climbing through layered translucent paper terraces, small guiding lanterns marking each
stage — a visual metaphor for a guided learning journey through Rust's ownership and
lifetimes. Layered paper-craft diorama, soft 3D, warm daylight from upper-left with one
consistent light source and gentle matte film grain. Composition: subject on the right,
clean negative space on the lower-left reserved for a title. Palette: cream and warm ivory
with amber accents and deep ink, restrained and calm. Integrate the title text "Rust 内存模型
深度拆解" as a deliberate typographic element: clean modern sans-serif, horizontal, high
legibility, placed in the lower-left negative space; spell it exactly, no extra words.
16:10 aspect ratio. Avoid: no neon circuit boards, no tech-blue-on-black, no plastic glossy
3D, no fake bokeh, no floating UI panels, no centered symmetric blob, no garbled text.
```

规格：`云课堂 · 层叠纸艺 diorama · 米白+琥珀+墨 · 右主体左留白`

## 详细风格池

每类产品的**色族、媒介清单、母题、构图建议和多条范例 prompt**都在 `references/style-pools.md`。开始组装前先读对应类型那一节——SKILL.md 只给方法，池子里才是具体素材。
