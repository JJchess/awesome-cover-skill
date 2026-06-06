# -*- coding: utf-8 -*-
"""
全 Gemini 封面生成管线：
  stage 1  gemini-3.5-flash  扮演 cover-art-director skill，把请求编译成英文出图 prompt
  stage 2  Nano Banana       把 prompt 渲染成封面（线程池并发出图），本地裁 16:10 存盘

一批 N 张封面 = 1 次文本调用（一次产出 N 条 prompt，内部跑多样引擎）+ N 次并发文生图调用
（WORKERS 环境变量控制并发数，默认 6；遇 429 限流可调小）。

用法:
  python pipeline.py                 # 跑内置测试用例（对齐 cover-generation-test-cases.md §2）
  python pipeline.py requests.json   # 读自定义请求批次
requests.json 形如:
  [{"product_type":"云课堂","title":"Rust 内存模型深度拆解","brief":"所有权、生命周期与无畏并发"},
   {"title":"金融时间序列与冲击预测","brief":"用 notebook 跑量化实验"}]   # product_type 可省，由关键词推断
"""
import os, sys, json, base64, logging, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Optional, List
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TEXT_MODEL = "gemini-3.5-flash"          # 艺术总监：编 prompt
# Nano Banana 出图。gemini-2.5-flash-image 是经典 Nano Banana，但渲染中文标题会丢字；
# gemini-3.1-flash-image 同属 flash-image 线、能正确渲染中文。带中文 title 时必须用 3.1。
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-3.1-flash-image")
# 标题模式：overlay = 模型只出画面+留安全区，标题用真字体后期合成（默认，质感最稳）；
#           baked   = 让模型把标题直接烤进图里（旧行为，CJK 偶尔糊字/繁体）。
TITLE_MODE = os.getenv("TITLE_MODE", "overlay")
# stage 2 出图并发数（线程池）。出图是纯 I/O 等待，并发可线性提速；遇 429 限流就调小。
WORKERS = max(1, int(os.getenv("WORKERS", "6")))
# overlay 模式下硬性禁止模型烤任何文字（notebook/蓝图/编辑类媒介最爱自己加英文标签），
# 标题完全交给后期真字体合成。
NO_TEXT_CLAUSE = (
    " ABSOLUTELY NO text of any kind in the image: no letters, no words, no numbers, no "
    "captions, no titles, no headings, no labels, no axis ticks text, no UI, no typography "
    "anywhere. Keep the reserved title area clean, quiet and empty."
)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(BASE_DIR, "skills", "cover-art-director")
OUT = "output_covers_gemini"
TARGET_RATIO = 16 / 10

# 后期排版用的高质量中文字体（按优先级回退）
FONT_CANDIDATES = [
    "C:/Windows/Fonts/NotoSansSC-VF.ttf",   # 思源黑体（可变字重，首选）
    "C:/Windows/Fonts/msyhbd.ttc",          # 微软雅黑 Bold
    "C:/Windows/Fonts/simhei.ttf",          # 黑体
    "C:/Windows/Fonts/Dengb.ttf",           # 等线 Bold
]

# 内置用例对齐 cover-generation-test-cases.md §2 中影响出图输入的 case。
# 后端 build_prompt() 只消费 title/subtitle 两个字段，这里 brief ≈ subtitle；
# brief 缺省 = subtitle 为空（Core Concept 回退用 title），title 缺省 = 无标题纯氛围图。
DEMO_REQUESTS = [
    # —— 互动场景（workflow_scene）——
    # WS-01 正常生成：title + subtitle 齐全
    {"product_type": "互动场景", "title": "太阳系行星探索",
     "brief": "拖拽行星观察轨道与公转周期变化"},
    # WS-02 subtitle 为空回退：Core Concept 用 title
    {"product_type": "互动场景", "title": "垃圾分类小游戏"},
    # WS-04 regenerate 已知现状：title/subtitle 均为空 → 无标题文字的纯氛围封面
    {"product_type": "互动场景"},
    # WS-06 长标题与特殊字符：80+ 字、含引号/emoji/换行（记录排版实际表现）
    {"product_type": "互动场景",
     "title": "「从零到一」打造你的专属 AI 学习助手 🤖：涵盖意图识别、多轮对话管理、"
              "知识库检索增强（RAG）与外部工具调用的全栈实战训练营——零基础也能跟上的 12 周陪跑计划\n（第二期）",
     "brief": "多个 AI Agent 分工协作，从需求拆解到上线演示完整走一遍"},
    # —— 代码实验室（lab，plaza 分享直取失败后的 AI 回退链路）——
    # LAB-02 回退 AI：title 走回退链（result_block.title），subtitle = share.description
    {"product_type": "代码实验室", "title": "金融时间序列与冲击预测",
     "brief": "在 notebook 里对收益率序列做平稳性检验与异质冲击预测"},
    # LAB-03 prompt_hint 覆盖 subtitle：画面需体现该风格
    {"product_type": "代码实验室", "title": "Web 代码沙盒实验",
     "brief": "赛博朋克风格的代码编辑器"},
    # LAB-04 标题回退链：result_block 无 title，用 query 前 80 字当标题
    {"product_type": "代码实验室", "title": "做一个贪吃蛇小游戏"},
    # LAB-05 全部回退兜底：标题 = "Untitled {content_type}"（验证英文兜底标题观感）
    {"product_type": "代码实验室", "title": "Untitled lab"},
    # —— 云课堂（cloud_course）——
    # CC-01 正常生成：title + subtitle 齐全
    {"product_type": "云课堂", "title": "机器学习导论",
     "brief": "从线性回归到神经网络的十周课程"},
    # CC-02 regenerate 回查 DB：title/subtitle 取自 cloud_courses 表
    {"product_type": "云课堂", "title": "高等数学(上)",
     "brief": "极限、导数与一元积分"},
    # CC-03 description 为空：subtitle=None，Core Concept 回退用 title
    {"product_type": "云课堂", "title": "Python 数据分析入门"},
]

# 风格池（与 references/style-pools.md 对齐）——用于确定性变体分配，强制同类不撞车
POOLS = {
    "云课堂": {
        "media": [
            "modern editorial illustration, flat with visible paper grain and printed texture",
            "layered paper-craft diorama, soft 3D cut-paper with felt-like texture",
            "isometric structured scene of ascending platforms and terraces",
            "hand-annotated 'diagram-as-art', sketched notes and arrows as design",
            "risograph textured print with grainy overprint registration",
            "soft clay diorama miniature, tactile matte sculpted forms",
        ],
        "palettes": [
            "cream / amber / deep ink",
            "sage green / warm white / terracotta",
            "dusty blue / sand / coral",
            "oatmeal / brass / forest green",
        ],
    },
    "代码实验室": {
        "media": [
            "elegant data-visualization-as-art, charts and curves sculpted as physical objects",
            "isometric workspace desk scene, notebook and modular blocks, tidy and tactile",
            "blueprint / schematic linework, precise technical drawing reimagined",
            "material / macro study of paper, grid and ink, close and physical",
            "clean dark-mode editorial design, calm and ordered (not neon)",
            "modular blocks / typographic technical poster, constructed layout",
        ],
        "palettes": [
            "slate / off-white / electric-blue accent",
            "ink navy / paper / lime accent",
            "graphite / warm white / signal-orange accent",
            "deep teal / paper / magenta spark",
        ],
    },
    "互动场景": {
        "media": [
            "abstract agent-character shapes mid-dialogue, roles by silhouette",
            "network constellation of nodes-as-characters linked by dialogue lines",
            "theatrical staging with warm spotlights, each agent in its own pool of light",
            "bold geometric collage of speech forms and connected figures",
            "dynamic motion illustration, energy and gesture between figures",
            "playful matte 3D cast of characters, hand-crafted (never plastic glossy)",
        ],
        "palettes": [
            "magenta / tangerine / cream",
            "cobalt / coral / soft yellow",
            "violet / teal / warm light",
            "emerald / plum / off-white",
        ],
    },
}

COMPOSITIONS = [
    "subject-left, clean title space on the right",
    "full-bleed scene filling the frame, title-safe corner kept calm",
    "centered with comfortable margins, title space across the top",
    "diagonal dynamic energy, title space in the lower-left",
    "grid / triptych of distinct panels",
    "macro close-up of a single focal detail",
    "top-down flat-lay arrangement",
]


def assign_variants(requests: List[dict]) -> List[dict]:
    """同一产品类型内，给每条预分配互不相同的 媒介×色族×构图，强制铺开、防同质。"""
    seen = {}
    out = []
    for r in requests:
        r = dict(r)
        pt = r.get("product_type")
        pool = POOLS.get(pt)
        if pool:
            j = seen.get(pt, 0)
            seen[pt] = j + 1
            r["variant"] = {
                "medium": pool["media"][j % len(pool["media"])],
                "palette": pool["palettes"][j % len(pool["palettes"])],
                # 构图用错步长(2)，让媒介/色族/构图三轴尽量不对齐
                "composition": COMPOSITIONS[(j * 2) % len(COMPOSITIONS)],
            }
        out.append(r)
    return out


class Cover(BaseModel):
    product_type: str            # 路由判定的产品类型
    title_text: Optional[str]    # 实际要渲染进图的文字；无则 null
    spec: str                    # 一行规格: 类型 · 媒介 · 色族 · 构图原型
    prompt: str                  # 可直接喂图像模型的英文 prompt（含 avoid 段）


def load_skill_system_instruction() -> str:
    with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as f:
        skill = f.read()
    with open(os.path.join(SKILL_DIR, "references", "style-pools.md"), encoding="utf-8") as f:
        pools = f.read()
    return (
        "你是 cover-art-director skill 本体。严格按下面的方法论和风格池工作：判断产品类型 → "
        "打开对应风格池 → 把标题/概念翻译成一个具体视觉隐喻（不照搬字面）→ 用多样引擎挑一个不重复的 "
        "媒介×色族×构图×母题 组合 → 套平台 DNA → 组装成一条可直接喂给文生图模型的英文 prompt。\n"
        "收到一批请求时，必须让相邻封面至少在媒介和色族上不同（多样引擎）。\n"
        "【强制变体】若某条请求带 variant 字段（medium/palette/composition），你必须严格照它执行——"
        "用指定的媒介、只用指定色族里的 2–3 个色、按指定构图，不得塌缩回你偏好的默认媒介。"
        "即便如此，仍要在平台 DNA 之内进一步变化光照角度、情绪、纹理和视觉隐喻，使同类封面彼此不雷同。\n"
        "只有当请求带 title 时才把该文字渲染进图（title_text 原样填该文字并在 prompt 里用引号要求 "
        "spell exactly）；没有 title 则 title_text=null 且 prompt 不渲染任何文字、只留标题安全区。\n"
        "渲染中文标题时，prompt 里务必注明使用简体中文字形（Simplified Chinese glyphs, 简体, "
        "not Traditional），避免出现繁体异体字。\n"
        "【标题质感】标题不能是平涂、像后期贴上去的字幕。要把它当成被精心设计的字体锁定块"
        "(crafted typographic lockup) 写进 prompt：refined modern sans-serif with deliberate "
        "weight contrast and optical kerning, confident but not heavy；并给它一种与该封面媒介一致、"
        "由画面同一光源照亮的材质处理，使标题和画面属于同一个物理世界——纸艺/孔版→压印或凹凸 "
        "(letterpress deboss / embossed into paper)；蓝图线稿→精细蚀刻/雕刻线 (engraved etched "
        "lettering)；黏土/3D/等距→轻微挤出的哑光立体字并带一致柔和投影 (subtly extruded matte "
        "3D type with one consistent soft shadow)；编辑插画/数据可视化→油墨印刷质感带细颗粒 "
        "(ink-printed type with subtle grain)。标题颜色从该条色板里取一个锚定色或中性深色、与背景"
        "拉开对比，可有极克制的微立体或细投影。务必强调：effect stays subtle, every stroke crisp "
        "and perfectly legible, do not distort/warp/over-texture the Chinese characters。\n"
        "对每个请求产出一个对象：product_type / title_text / spec（一行：类型 · 媒介 · 色族 · 构图原型）/ "
        "prompt（英文，含浓缩的 avoid 段）。\n\n"
        "===== SKILL.md =====\n" + skill +
        "\n\n===== references/style-pools.md =====\n" + pools
    )


def author_prompts(client: genai.Client, requests: List[dict], retries: int = 12) -> List[Cover]:
    user_payload = "请为以下批次逐条产出封面 prompt（保持顺序，整批在媒介+色族上铺开）：\n" + \
        json.dumps(requests, ensure_ascii=False, indent=2)
    cfg = types.GenerateContentConfig(
        system_instruction=load_skill_system_instruction(),
        response_mime_type="application/json",
        response_schema=list[Cover],
        temperature=1.0,   # 拉开多样性
    )
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=TEXT_MODEL, contents=user_payload, config=cfg)
            if resp.parsed:
                return resp.parsed
            logging.warning("  stage1 空结果，重试 %d", attempt + 1)
        except Exception as e:
            logging.warning("  stage1 attempt %d 失败: %s", attempt + 1, e)
    raise SystemExit("stage 1 多次失败，请重跑")


def _load_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            font = ImageFont.truetype(path, size)
            try:  # 思源黑体是可变字重，拉到 SemiBold/Bold 更有分量
                font.set_variation_by_axes([640])
            except Exception:
                pass
            return font
    return ImageFont.load_default()


def _zone_from_composition(comp: str):
    """根据构图原型里预留的标题安全区位置，返回 (锚点, 对齐)。"""
    c = (comp or "").lower()
    if "right" in c:
        return "right", "left"
    if "top" in c or "flat-lay" in c:
        return "top", "center"
    if "triptych" in c or "grid" in c or "full-bleed" in c:
        return "bottom", "center"
    return "lowerleft", "left"   # 含 diagonal / macro / 默认


def _region_rect(W, H, zone):
    m = int(W * 0.055)
    if zone == "right":
        return (int(W * 0.52), int(H * 0.30), W - m, int(H * 0.70))
    if zone == "top":
        return (m, m, W - m, int(H * 0.26))
    if zone == "bottom":
        return (m, int(H * 0.80), W - m, H - m)
    return (m, int(H * 0.66), int(W * 0.70), H - m)  # lowerleft


def _fit_font(text, max_w, max_h, tracking_ratio=0.06):
    """在区域内自适应字号；返回 (font, size, 每字宽列表, 字距像素)。"""
    for size in range(max(28, max_h), 24, -2):
        font = _load_font(size)
        track = int(size * tracking_ratio)
        widths = [font.getbbox(ch)[2] - font.getbbox(ch)[0] for ch in text]
        total = sum(widths) + track * (len(text) - 1)
        bb = font.getbbox("国Ag")
        line_h = bb[3] - bb[1]
        if total <= max_w and line_h <= max_h:
            return font, size, track, line_h
    font = _load_font(28)
    return font, 28, 2, font.getbbox("国")[3]


def _luma_stats(img, rect):
    crop = img.crop(rect).convert("L").resize((32, 32))
    px = list(crop.getdata())
    n = len(px)
    mean = sum(px) / n
    std = (sum((v - mean) ** 2 for v in px) / n) ** 0.5
    return mean, std


def draw_title_overlay(img: Image.Image, text: str, composition: str) -> Image.Image:
    """把标题用真字体排进预留安全区：自动对比、字间距、压印式细投影——质感来自这里。"""
    img = img.convert("RGB")
    W, H = img.size
    zone, align = _zone_from_composition(composition)
    rx0, ry0, rx1, ry1 = _region_rect(W, H, zone)
    max_w, max_h = rx1 - rx0, ry1 - ry0
    font, size, track, line_h = _fit_font(text, max_w, int(max_h * 0.8))

    widths = [font.getbbox(ch)[2] - font.getbbox(ch)[0] for ch in text]
    text_w = sum(widths) + track * (len(text) - 1)

    if align == "center":
        x = rx0 + (max_w - text_w) // 2
    else:
        x = rx0
    y = ry0 + (max_h - line_h) // 2

    # 自动对比：安全区偏暗→米白字，偏亮→近黑墨字
    luma, std = _luma_stats(img, (rx0, ry0, rx1, ry1))
    if luma < 125:
        main = (244, 241, 233)        # 米白
        emboss = (0, 0, 0, 90)        # 下沉暗边
        shadow = (0, 0, 0, 70)
    else:
        main = (28, 28, 30)           # 墨黑
        emboss = (255, 255, 255, 110) # 上提亮边（压印高光）
        shadow = (0, 0, 0, 55)

    # 背景在安全区偏花/对比不足时，垫一层羽化柔光底，保证标题永远读得清（非 UI 方框）
    contrast = abs(main[0] - luma)
    if std > 40 or contrast < 95:
        pad_x, pad_y = int(size * 0.55), int(size * 0.4)
        bx = (x - pad_x, y - pad_y, x + text_w + pad_x, y + line_h + pad_y)
        scol = (0, 0, 0, 130) if main[0] > 120 else (248, 246, 240, 165)
        scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(scrim).rounded_rectangle(bx, radius=int(size * 0.6), fill=scol)
        scrim = scrim.filter(ImageFilter.GaussianBlur(int(size * 0.7)))
        img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    def _draw(dx, dy, color):
        cx = x + dx
        for ch, w in zip(text, widths):
            d.text((cx, y + dy), ch, font=font, fill=color)
            cx += w + track

    # 1) 柔投影（光来自左上，投影落右下）→ 让字脱离背景、有体积
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    cx = x
    for ch, w in zip(text, widths):
        ds.text((cx + int(size * 0.05), y + int(size * 0.06)), ch, font=font, fill=shadow)
        cx += w + track
    sh = sh.filter(ImageFilter.GaussianBlur(max(1, size // 24)))
    layer = Image.alpha_composite(layer, sh)
    d = ImageDraw.Draw(layer)
    # 2) 压印高光/暗边（与光源一致的 1px 偏移）→ letterpress 质感
    _draw(-1, -1, emboss)
    # 3) 主字面
    _draw(0, 0, main)

    out = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    return out


def crop_to_ratio(img, ratio):
    w, h = img.size
    cur = w / h
    if cur > ratio + 0.01:
        nw = int(h * ratio); left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    elif cur < ratio - 0.01:
        nh = int(w / ratio); top = (h - nh) // 2
        img = img.crop((0, top, w, top + nh))
    return img


def render(client: genai.Client, prompt: str, retries: int = 3):
    """出图并裁成 16:10，返回 PIL.Image（失败返回 None）。"""
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=IMAGE_MODEL, contents=[prompt])
            for part in resp.parts:
                inline = getattr(part, "inline_data", None)
                if inline is not None and inline.data:
                    data = inline.data
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    img = Image.open(BytesIO(data)).convert("RGB")
                    return crop_to_ratio(img, TARGET_RATIO)
            logging.warning("  无图像数据，重试 %d", attempt + 1)
        except Exception as e:
            logging.warning("  attempt %d 失败: %s", attempt + 1, e)
        if attempt < retries - 1:
            time.sleep(3 * (attempt + 1))   # 退避，并发跑时对限流更友好
    return None


def process_one(client: genai.Client, i: int, c: Cover, title: Optional[str],
                composition: str, overlay: bool) -> dict:
    """单条封面：出图 →（overlay 时）后期排版标题 → 存盘。供线程池并发调用。"""
    name = f"{i+1:02d}_{c.product_type}"
    path = os.path.join(OUT, f"{name}.png")
    prompt = c.prompt + NO_TEXT_CLAUSE if overlay else c.prompt
    img = render(client, prompt)
    if img is not None and overlay and title:
        img.save(os.path.join(OUT, "_art", f"{name}.png"))   # 留存无字底图，方便只改排版重跑
        img = draw_title_overlay(img, title, composition)
        logging.info("  ✎ [%d] 后期排版标题: %s", i + 1, title)
    if img is not None:
        img.save(path)
        logging.info("  ✅ [%d] %s (%dx%d)", i + 1, path, *img.size)
    else:
        logging.error("  ❌ [%d] %s 出图失败", i + 1, name)
    return {"index": i + 1, "product_type": c.product_type,
            "title_text": title if overlay else c.title_text,
            "title_mode": TITLE_MODE, "spec": c.spec,
            "prompt": c.prompt, "image": path if img is not None else None}


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("No GEMINI_API_KEY in .env")
    requests = DEMO_REQUESTS
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            requests = json.load(f)

    requests = assign_variants(requests)
    client = genai.Client(api_key=api_key)
    os.makedirs(OUT, exist_ok=True)

    overlay = TITLE_MODE == "overlay"
    logging.info("标题模式: %s", "overlay（后期真字体合成）" if overlay else "baked（模型烤字）")

    # overlay 模式：让模型只出画面+留安全区（不烤字），标题留到后期合成
    art_requests = requests
    real_titles = [r.get("title") for r in requests]
    if overlay:
        art_requests = []
        for r in requests:
            rr = dict(r); rr["title"] = None
            art_requests.append(rr)

    logging.info("stage 1: %s 编译 %d 条 prompt …", TEXT_MODEL, len(art_requests))
    covers = author_prompts(client, art_requests)

    manifest = [None] * len(covers)
    if overlay:
        os.makedirs(os.path.join(OUT, "_art"), exist_ok=True)
    logging.info("stage 2: %s 并发出图（%d workers）…", IMAGE_MODEL, WORKERS)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {}
        for i, c in enumerate(covers):
            logging.info("[%d] %s", i + 1, c.spec)
            title = real_titles[i] if i < len(real_titles) else None
            comp = (requests[i].get("variant") or {}).get("composition", "") if i < len(requests) else ""
            futs[pool.submit(process_one, client, i, c, title, comp, overlay)] = i
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                manifest[i] = fut.result()
            except Exception as e:   # render 内部已兜底，这里防存盘等意外异常
                logging.error("  ❌ [%d] 异常: %s", i + 1, e)
                c = covers[i]
                title = real_titles[i] if i < len(real_titles) else None
                manifest[i] = {"index": i + 1, "product_type": c.product_type,
                               "title_text": title if overlay else c.title_text,
                               "title_mode": TITLE_MODE, "spec": c.spec,
                               "prompt": c.prompt, "image": None}

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    logging.info("完成。manifest 写入 %s/manifest.json", OUT)


if __name__ == "__main__":
    main()
