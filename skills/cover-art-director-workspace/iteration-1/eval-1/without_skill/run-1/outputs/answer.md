# 封面文生图 Prompt —「金融时间序列与冲击预测」

**项目主题:** 基于异质冲击编码的波动率量化模型
**目标工具:** Nano Banana
**画幅比例:** 16:10

---

## Prompt (English)

```
A sophisticated editorial cover illustration for a quantitative finance research project titled "Financial Time Series & Shock Forecasting." Aspect ratio 16:10, wide horizontal composition.

Central visual: a sweeping financial time-series candlestick and volatility curve flowing left to right across a deep midnight-blue background, rendered as luminous fine lines. The smooth curve is suddenly disrupted by sharp, jagged volatility spikes — visual "shocks" bursting upward in vivid amber and crimson, depicting heterogeneous market impacts of varying magnitude and color, each shock encoded as a distinct glowing glyph or particle cluster.

Behind the curve, a faint translucent grid and layered probability bands (forecast cones / confidence intervals) fan out toward the right edge, suggesting predictive uncertainty. Subtle abstract neural-encoding motifs — interconnected nodes and gradient heatmap cells — weave through the lower third, hinting at the "heterogeneous shock encoding" model. Faint floating numerals and ticker fragments add texture without clutter.

Style: modern data-driven scientific poster meets premium fintech editorial; clean, elegant, high-contrast. Color palette: deep navy and charcoal base, electric cyan and teal data lines, amber-to-crimson accent gradients for shocks, soft violet glow. Cinematic depth, soft volumetric lighting, crisp vector-like clarity with subtle glassmorphism. Negative space on the upper-left for a title. Professional, intelligent, slightly futuristic mood.

No text, no words, no letters, no watermark. High detail, 4K, sharp focus.

--ar 16:10
```

---

## 设计说明

- **核心隐喻:** 平滑波动率曲线 → 被异质冲击(不同颜色/量级的尖峰)打断,直观对应"异质冲击编码 + 波动率预测"的论文主旨。
- **预测感:** 右侧扇形展开的置信区间锥体表达"预测/不确定性"。
- **模型暗示:** 下方神经节点与热力网格暗示编码器结构,不喧宾夺主。
- **留白:** 左上角留出标题区,方便后期叠加中文标题「金融时间序列与冲击预测」。
- **配色:** 深海军蓝底 + 青色数据线 + 琥珀/绯红冲击色,兼顾金融的冷静与冲击的警示感。
- **negative prompt 已内嵌:** 明确禁止生成文字/水印,避免乱码英文污染封面。

> 提示:若 Nano Banana 仍生成多余文字,可把「No text...」一段提到 prompt 最前面强调,或在工具的负向输入框单独填入 `text, words, letters, watermark, signature`。
