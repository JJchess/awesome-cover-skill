# -*- coding: utf-8 -*-
"""
用 cover-art-director skill 产出的 prompt 调用 Nano Banana (gemini flash image) 实际出图。
输出裁剪为 16:10，存到 output_covers/。
"""
import os, base64, logging
from io import BytesIO
from PIL import Image
from google import genai
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MODEL = "gemini-3.1-flash-image"  # Nano Banana
OUT = "output_covers"
TARGET_RATIO = 16 / 10

# skill 产出的 prompt（逐字取自 eval 输出）
COVERS = {
    "01_yunketang_rust": {
        "spec": "云课堂 · 等距结构化场景 · 燕麦+黄铜+森林绿 · 右主体左留白",
        "prompt": (
            "Editorial-quality course cover art, art-directed and hand-crafted, looks like the work of a "
            "real art director rather than a stock 3D render. Visual idea: an isometric arrangement of "
            "distinct translucent territories, each region cleanly bordered and held by a single small "
            "guardian marker — a calm visual metaphor for ownership and bounded lifetimes — while a few "
            "orderly parallel channels glide safely through and between the regions without ever colliding, "
            "evoking fearless concurrency. Medium: isometric structured scene, soft hand-crafted geometry, "
            "gentle stepped depth. Composition: main subject grouped on the right with clean negative space "
            "reserved on the lower-left for a title; intentional asymmetry, generous breathing room, 16:10 "
            "aspect ratio. Palette: restrained, warm and calm — oatmeal and warm white as the base, brass "
            "accents, and deep forest green, plus a neutral paper tone; colors deliberately chosen, not piled "
            "on. Light: one consistent soft daylight source from the upper-left, self-consistent shadows, "
            "matte finish with subtle film grain and a clean geometric structure. Integrate the title text "
            '"Rust 内存模型深度拆解" as a deliberate typographic element: clean modern sans-serif, single '
            "font, horizontal, high contrast and highly legible, placed in the reserved lower-left negative "
            "space as designed typography (not a watermark); spell it exactly, no extra words. Avoid: no "
            "glowing neon circuit boards, no hexagon grids, no matrix code rain, no tech-blue-gradient-on-black, "
            "no chrome spheres, no robot heads or glowing brains, no plastic glossy 3D render, no fake bokeh "
            "everywhere, no lens flare spam, no floating UI panels, no centered symmetric hero blob, no "
            "cluttered composition, no garbled or misspelled text."
        ),
    },
    "02_codelab_finance": {
        "spec": "代码实验室 · 数据可视化即雕塑 · 深青+纸色+品红火花 · 左主体右留白",
        "prompt": (
            "Editorial-quality cover art for a computational notebook experiment, art-directed and "
            "hand-crafted, looks like a real studio piece rather than a stock 3D render. The core image: "
            "a single smooth volatility curve rendered as a sculpted matte ribbon flowing left to right "
            "along a faint plotted time-axis, its surface disturbed by a small series of discrete shock "
            "impulses — sharp spikes and clean step-discontinuities of distinctly different shapes, each "
            "one a heterogeneous shock encoded into the curve, a few faint forecast nodes plotted ahead "
            "of the last spike like an experiment in progress. Medium: elegant data-visualization-as-art, "
            "tactile and precise, sitting over a faint coordinate grid with clean geometric structure. "
            "One consistent studio light source from the upper-left, intentional asymmetry, matte finish "
            "with subtle film grain, generous breathing room. Composition: subject anchored on the left, "
            "clean negative space on the right reserved for a title. Palette: deep teal and paper-neutral "
            "off-white with one restrained magenta spark used only on the shock impulses, calm and "
            'controlled. Integrate the title text "金融时间序列与冲击预测" as a deliberate typographic '
            "element: clean modern sans-serif, single font, horizontal, high contrast and high legibility, "
            "placed in the reserved right-side negative space, spell it exactly with no extra words. "
            "16:10 aspect ratio. Avoid: no glowing neon circuit boards, no hexagon grids, no matrix code "
            "rain, no tech-blue-gradient-on-black, no chrome spheres, no robot heads or glowing brains, "
            "no plastic glossy 3D render, no fake bokeh everywhere, no lens flare spam, no floating UI "
            "panels, no centered symmetric hero blob, no cluttered composition, no garbled or misspelled "
            "text."
        ),
    },
    "03_interactive_agents": {
        "spec": "互动场景 · 舞台聚光调度 · 紫罗兰+青+暖光 · 对角动势+右上留白",
        "prompt": (
            "Editorial-quality cover art for a multi-agent collaboration scene — art-directed, "
            "hand-crafted, looks like the work of a real art director rather than a stock render. "
            "The single idea: a small cast of distinct abstract agent-figures staged mid-conversation, "
            "each lit by its own pool of light to read as a separate role, while flowing dialogue lines "
            "arc and weave between them and converge toward one brighter focus at the front of the "
            "stage — the shared market-research insight they assemble together. Theatrical staging with "
            "warm spotlights against a calm dark backdrop; roles distinguished by silhouette and shape, "
            "not by faces; one figure leans in, another points, a third holds back, giving a real sense "
            "of division of labor and discussion. Render as a hand-crafted theatrical diorama with a "
            "clean geometric structure, intentional asymmetry, and one consistent warm key light from "
            "the upper-left so every shadow agrees. Matte finish with subtle film grain, no plastic "
            "gloss. Composition: diagonal dynamic energy reading lower-left to upper-right, with clean "
            "negative space in the upper-right kept open as a title-safe area. Palette restrained to "
            "violet and teal as the two anchors with a warm amber light accent over an off-white / "
            "graphite neutral — bold and lively but harmonized, not rainbow. Generous breathing room, "
            "subject not touching the four edges. 16:10 aspect ratio. Avoid: no glowing neon circuit "
            "boards, no hexagon grids, no matrix code rain, no tech-blue-gradient-on-black, no chrome "
            "spheres, no robot heads or glowing brains, no plastic glossy 3D render, no fake bokeh "
            "everywhere, no lens flare spam, no floating UI panels, no centered symmetric hero blob, "
            "no cluttered composition, no garbled or misspelled text."
        ),
    },
    "04_batch_python": {
        "spec": "云课堂 · 等距结构化场景 · 燕麦+黄铜+森林绿 · 居中带边距",
        "prompt": (
            "Editorial-quality course cover art, art-directed and hand-crafted, looks made by a real "
            "designer not a stock 3D render. Visual idea: scattered loose data points and rough tally "
            "marks being gently gathered and sorted into a clean ascending staircase of small labeled "
            "trays — a calm, guided first step into data analysis, turning mess into clear structure. "
            "Medium: isometric structured scene, tactile soft 3D with paper-like surfaces and clean "
            "geometric construction. Single consistent daylight from the upper-left, self-consistent "
            "shadows, matte finish, subtle film grain. Composition: subject anchored center with "
            "comfortable margins, clean negative space across the top reserved as a title safe area. "
            "Palette: oatmeal and warm white with brass and forest-green accents, restrained and warm, "
            "2-3 anchored hues plus a neutral. Intentional asymmetry, generous breathing room. "
            'Integrate the title text "Python 数据分析入门" as a deliberate typographic element: clean '
            "modern sans-serif, single font, horizontal, high contrast and legibility, placed in the "
            "reserved top negative space; spell it exactly, no extra words. 16:10 aspect ratio. "
            "Avoid: no glowing neon circuit boards, no hexagon grids, no matrix code rain, no "
            "tech-blue-gradient-on-black, no chrome spheres, no robot heads or glowing brains, no "
            "plastic glossy 3D render, no fake bokeh everywhere, no lens flare spam, no floating UI "
            "panels, no centered symmetric hero blob, no cluttered composition, no garbled or "
            "misspelled text."
        ),
    },
    "05_batch_deeplearning": {
        "spec": "云课堂 · 层叠纸艺 diorama · 雾霾蓝+沙色+珊瑚 · 对角动势",
        "prompt": (
            "Editorial-quality course cover art, art-directed and hand-crafted, editorial finish rather "
            "than a generic render. Visual idea: a winding path climbing diagonally through layered, "
            "deepening terrain — early hills folding upward into higher, more intricate ridges, small "
            "guiding lanterns marking each stage of the ascent — a metaphor for a deepening journey "
            "from foundations into advanced mastery of deep learning. Medium: layered paper-craft "
            "diorama, soft 3D cut-paper landscape with felt-like texture. One warm light source from the "
            "upper-left, coherent soft shadows, matte finish, gentle film grain, clean geometric "
            "layering. Composition: diagonal dynamic flow rising left-to-right, clean negative space on "
            "the lower-left reserved as a title safe area. Palette: dusty blue and sand with coral "
            "accents, calm and warm, 2-3 anchored hues plus a neutral, deliberately chosen not piled on. "
            'Intentional asymmetry and generous breathing room. Integrate the title text "深度学习进阶之路" '
            "as a deliberate typographic element: clean modern sans-serif, single font, horizontal, high "
            "legibility against the background, placed in the lower-left negative space; spell it exactly, "
            "no extra words. 16:10 aspect ratio. Avoid: no glowing neon circuit boards, no hexagon grids, "
            "no matrix code rain, no tech-blue-gradient-on-black, no chrome spheres, no robot heads or "
            "glowing brains, no plastic glossy 3D render, no fake bokeh everywhere, no lens flare spam, "
            "no floating UI panels, no centered symmetric hero blob, no cluttered composition, no "
            "garbled or misspelled text."
        ),
    },
    "06_batch_algorithms": {
        "spec": "云课堂 · 现代编辑插画(概念星座地图) · 米白+琥珀+墨 · 左留白右主体",
        "prompt": (
            "Editorial-quality course cover art, art-directed and hand-crafted, looks like a designed "
            "editorial illustration, not a stock asset. Visual idea: a calm constellation map where many "
            "small distinct concept-nodes — stacks, trees, linked chains, sorting steps — are connected by "
            "clean lines into one coherent, well-organized structure, like an entire curriculum mapped as "
            "a single elegant network — a metaphor for a systematic body of algorithms and data "
            "structures. Medium: flat modern editorial illustration with visible paper grain and printed "
            "texture, clean geometric linework. Single consistent light implied by soft layered shading, "
            "matte finish, subtle film grain. Composition: subject on the right as the constellation, "
            "clean negative space on the left reserved as a title safe area. Palette: cream and warm "
            "ivory with amber accents and deep ink, restrained and warm, 2-3 anchored hues plus a "
            'neutral. Intentional asymmetry, generous breathing room. Integrate the title text '
            '"算法与数据结构体系课" as a deliberate typographic element: clean modern sans-serif, single '
            "font, horizontal, high contrast and legibility, placed in the left negative space; spell it "
            "exactly, no extra words. 16:10 aspect ratio. Avoid: no glowing neon circuit boards, no "
            "hexagon grids, no matrix code rain, no tech-blue-gradient-on-black, no chrome spheres, no "
            "robot heads or glowing brains, no plastic glossy 3D render, no fake bokeh everywhere, no "
            "lens flare spam, no floating UI panels, no centered symmetric hero blob, no cluttered "
            "composition, no garbled or misspelled text."
        ),
    },
}


def crop_to_ratio(img, ratio):
    w, h = img.size
    cur = w / h
    if cur > ratio + 0.01:
        nw = int(h * ratio)
        left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    elif cur < ratio - 0.01:
        nh = int(w / ratio)
        top = (h - nh) // 2
        img = img.crop((0, top, w, top + nh))
    return img


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("No GEMINI_API_KEY in .env")
    client = genai.Client(api_key=api_key)
    os.makedirs(OUT, exist_ok=True)

    for name, cfg in COVERS.items():
        logging.info("生成: %s (%s)", name, cfg["spec"])
        try:
            resp = client.models.generate_content(model=MODEL, contents=[cfg["prompt"]])
            saved = False
            for part in resp.parts:
                if getattr(part, "text", None):
                    logging.info("  模型文本: %s", part.text[:160])
                inline = getattr(part, "inline_data", None)
                if inline is not None and inline.data:
                    data = inline.data
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    img = Image.open(BytesIO(data)).convert("RGB")
                    img = crop_to_ratio(img, TARGET_RATIO)
                    path = os.path.join(OUT, f"{name}.png")
                    img.save(path)
                    logging.info("  ✅ 已保存 %s  (%dx%d)", path, *img.size)
                    saved = True
                    break
            if not saved:
                logging.error("  ❌ 未返回图片数据")
        except Exception as e:
            logging.error("  ❌ 失败: %s", e)


if __name__ == "__main__":
    main()
