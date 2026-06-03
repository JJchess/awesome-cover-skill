# 云课堂封面图 — 文生图 Prompt

课程信息：
- Title（需显示在封面上）：「Rust 内存模型深度拆解」
- 副标题 / 概念：所有权、生命周期与无畏并发（Ownership · Lifetimes · Fearless Concurrency）

---

## 推荐 Prompt（直接复制使用）

```
A modern, high-end online-course cover illustration for a programming masterclass, 16:9 landscape, designed as a sleek tech-education thumbnail.

Theme: the Rust language memory model. Foreground hero element: a polished 3D crab mascot (Rust's Ferris) rendered in metallic burnt-orange, sitting confidently at the center-left, with subtle rust-colored gradient lighting. Behind it, an elegant abstract visualization of computer memory — glowing translucent boxes connected by clean directional arrows representing "ownership" passing between blocks, a few delicate timeline brackets suggesting "lifetimes", and two parallel light-trails weaving without collision to evoke "fearless concurrency / safe parallel threads".

Style: clean flat-design with soft 3D depth, isometric tech aesthetic, premium dark-mode background (deep charcoal #1a1a1f to midnight navy gradient), warm orange and amber accent glow (#dea584, #ff8c42), thin cyan highlight lines for the concurrency threads. Polished, professional, uncluttered, plenty of negative space on the right side for text. Subtle grid and circuit motifs in the far background, low opacity.

Prominent bold display title text, perfectly legible, sharp typography, placed in the upper-right area:
「Rust 内存模型深度拆解」
Below it, in a smaller, lighter weight subtitle:
所有权 · 生命周期 · 无畏并发

Text must be crisp, correctly spelled, well-kerned Chinese characters, high contrast against the dark background, integrated tastefully into the layout (not floating awkwardly). No watermark, no logos, no UI chrome. Cinematic studio lighting, sharp focus, 4k, high detail.
```

---

## 使用说明与小技巧

- **关于中文文字**：Nano Banana / Gemini Flash Image 渲染中文比英文更容易出错（笔画粘连、缺字）。建议：
  1. 先按上面的 prompt 生成；若标题中文不准确，把中文 title 用引号原样贴在 prompt 里再强调一次 "render this exact text: 「Rust 内存模型深度拆解」"。
  2. 若多次仍出错，退而求其次：让模型只渲染 "Rust" 英文 + 留白，中文标题后期用设计工具（Figma / Canva）叠加，质量最稳。
- **比例**：云课堂封面常用 16:9（1920×1080）或 16:10；上面已写 16:9，按平台需要替换。
- **风格切换**：想更"极客硬核"可把 `clean flat-design` 换成 `dark blueprint / schematic style`；想更亲和可强调 Ferris 螃蟹吉祥物并加 `friendly, approachable`。
- **概念到画面的映射**（方便你后续微调）：
  - 所有权 Ownership → 内存块之间传递的箭头（一个块"持有"另一个）
  - 生命周期 Lifetimes → 时间线括号 / scope brackets
  - 无畏并发 Fearless Concurrency → 多条并行且互不碰撞的光轨线程

---

## 纯英文精简版（如平台/模型对长 prompt 处理不佳）

```
Online course cover, 16:9, dark mode tech-education thumbnail about the Rust memory model. Centered metallic orange 3D Ferris crab mascot. Abstract memory blocks connected by ownership arrows, lifetime timeline brackets, and two parallel non-colliding glowing thread trails (fearless concurrency). Deep charcoal-to-navy gradient background, warm orange/amber accents, cyan thread highlights, isometric clean flat-design with soft 3D depth, negative space on the right. Bold legible title text top-right: 「Rust 内存模型深度拆解」, smaller subtitle below: 所有权 · 生命周期 · 无畏并发. Crisp correct Chinese typography, high contrast, no watermark, no logo, 4k, sharp focus.
```
