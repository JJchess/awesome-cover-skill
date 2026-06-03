这是「Rust 内存模型深度拆解」的云课堂封面 prompt。可以直接粘进 Nano Banana / Gemini flash image 的 `generate_content`。

视觉思路（不照搬字面）：不画内存条，而是把「所有权 / 生命周期 / 无畏并发」翻译成一组**有清晰边界的半透明地块**，每块由一个守卫标记单独持有（所有权与边界），几条整齐的平行通道安全地穿行其间、互不相撞（无畏并发）。等距结构化场景天然适合表达「分区 + 平行 + 拾级而上的体系」。配色走暖而平静的燕麦 / 黄铜 / 森林绿色族，避开 SKILL 范例已经用过的米白+琥珀，保证不撞车。

```text
Editorial-quality course cover art, art-directed and hand-crafted, looks like the work of a
real art director rather than a stock 3D render. Visual idea: an isometric arrangement of
distinct translucent territories, each region cleanly bordered and held by a single small
guardian marker — a calm visual metaphor for ownership and bounded lifetimes — while a few
orderly parallel channels glide safely through and between the regions without ever colliding,
evoking fearless concurrency. Medium: isometric structured scene, soft hand-crafted geometry,
gentle stepped depth. Composition: main subject grouped on the right with clean negative space
reserved on the lower-left for a title; intentional asymmetry, generous breathing room, 16:10
aspect ratio. Palette: restrained, warm and calm — oatmeal and warm white as the base, brass
accents, and deep forest green, plus a neutral paper tone; colors deliberately chosen, not piled
on. Light: one consistent soft daylight source from the upper-left, self-consistent shadows,
matte finish with subtle film grain and a clean geometric structure. Integrate the title text
"Rust 内存模型深度拆解" as a deliberate typographic element: clean modern sans-serif, single
font, horizontal, high contrast and highly legible, placed in the reserved lower-left negative
space as designed typography (not a watermark); spell it exactly, no extra words. Avoid: no
glowing neon circuit boards, no hexagon grids, no matrix code rain, no tech-blue-gradient-on-black,
no chrome spheres, no robot heads or glowing brains, no plastic glossy 3D render, no fake bokeh
everywhere, no lens flare spam, no floating UI panels, no centered symmetric hero blob, no
cluttered composition, no garbled or misspelled text.
```

规格：`云课堂 · 等距结构化场景 · 燕麦+黄铜+森林绿 · 右主体左留白`

两点提醒：
- 副标题「所有权、生命周期与无畏并发」只作为概念输入驱动画面，按惯例**不**渲染进图里；只渲染主标题。若你想让副标题也出现，告诉我，我把它加进排版块。
- 标题是中文且偏长，Nano Banana 渲染长中文串比短英文更容易出错。建议出 2–3 张挑字形最干净的一张；如果反复出错，可考虑把标题做成更短的版式（如「Rust 内存模型」），或后期用排版工具叠字以保证万无一失。
