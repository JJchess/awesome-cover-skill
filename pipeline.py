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
import os, sys, json, base64, logging, time, re
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
# 锚定到脚本目录：从任何 cwd 跑都读写仓库里这份输出（曾因 cwd 漂移把图写去过桌面散件）
OUT = os.path.join(BASE_DIR, "output_covers_gemini")
TARGET_RATIO = 16 / 10

# 后期排版字体库：每种风格一条回退链。多样化的同时保质感——
# 思源黑/宋（可变字重）扛拉丁与重权重；华文楷体/仿宋/幼圆给中文标题加气质，
# 但原始字重撑不起海报字号，用 stroke（按字号比例的描边）做轻微加粗。
# axes = 可变字体 wght 轴；track = 字距系数；stroke = 描边宽度系数（0 = 不描）。
FONT_STYLES = {
    "sans": {"label": "现代黑体", "axes": [640], "track": 0.06, "stroke": 0,
             "paths": ["C:/Windows/Fonts/NotoSansSC-VF.ttf", "C:/Windows/Fonts/msyhbd.ttc",
                       "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/Dengb.ttf"]},
    "sans-black": {"label": "重磅黑体", "axes": [860], "track": 0.04, "stroke": 0,
             "paths": ["C:/Windows/Fonts/NotoSansSC-VF.ttf", "C:/Windows/Fonts/simhei.ttf"]},
    "serif": {"label": "思源宋体", "axes": [780], "track": 0.035, "stroke": 0,
             "paths": ["C:/Windows/Fonts/NotoSerifSC-VF.ttf", "C:/Windows/Fonts/STZHONGS.TTF",
                       "C:/Windows/Fonts/simsun.ttc"]},
    "kai": {"label": "华文楷体", "axes": None, "track": 0.045, "stroke": 0.028,
            "paths": ["C:/Windows/Fonts/STKAITI.TTF", "C:/Windows/Fonts/simkai.ttf"]},
    "round": {"label": "幼圆", "axes": None, "track": 0.055, "stroke": 0.016,
              "paths": ["C:/Windows/Fonts/SIMYOU.TTF", "C:/Windows/Fonts/msyh.ttc"]},
    "fangsong": {"label": "华文仿宋", "axes": None, "track": 0.08, "stroke": 0.034,
                 "paths": ["C:/Windows/Fonts/STFANGSO.TTF", "C:/Windows/Fonts/simfang.ttf"]},
    "light": {"label": "轻细黑体", "axes": [350], "track": 0.10, "stroke": 0,
              "paths": ["C:/Windows/Fonts/NotoSansSC-VF.ttf", "C:/Windows/Fonts/msyhl.ttc",
                        "C:/Windows/Fonts/Dengl.ttf"]},
    "xinwei": {"label": "华文新魏", "axes": None, "track": 0.05, "stroke": 0,
               "paths": ["C:/Windows/Fonts/STXINWEI.TTF", "C:/Windows/Fonts/STKAITI.TTF"]},
    "xingkai": {"label": "华文行楷", "axes": None, "track": 0.04, "stroke": 0,
                "paths": ["C:/Windows/Fonts/STXINGKA.TTF", "C:/Windows/Fonts/STKAITI.TTF"]},
    "lishu": {"label": "华文隶书", "axes": None, "track": 0.06, "stroke": 0.012,
              "paths": ["C:/Windows/Fonts/STLITI.TTF", "C:/Windows/Fonts/SIMLI.TTF",
                        "C:/Windows/Fonts/STKAITI.TTF"]},
}

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


# 媒介关键词 → 字体候选（顺序即气质契合度；首条命中的规则生效）：
# 让字形气质跟画面媒介属于同一个世界——编辑/印刷→宋体系，蓝图→仿宋（工程图纸标准字），
# 剧场→新魏（碑刻海报气），动势→行楷，纸艺→楷/隶，黏土/剪影→圆体，
# 暗色/星座/数据可视化→轻细黑体，几何拼贴/字体海报→重磅黑体。
_MEDIUM_FONT_PREFS = [
    (("dark-mode",), ("light", "serif", "sans")),
    (("editorial", "risograph"), ("serif", "kai", "fangsong")),
    (("macro", "material"), ("serif", "light", "kai")),
    (("theatrical", "spotlight"), ("xinwei", "serif", "kai")),
    (("paper-craft",), ("kai", "lishu", "serif")),
    (("hand-annotated", "sketched"), ("kai", "xingkai", "fangsong")),
    (("motion", "dynamic"), ("xingkai", "kai", "sans-black")),
    (("clay", "playful"), ("round", "kai", "sans")),
    (("silhouette",), ("round", "sans-black", "sans")),
    (("constellation", "network"), ("light", "sans", "serif")),
    (("data-visualization",), ("light", "serif", "sans")),
    (("blueprint", "schematic"), ("fangsong", "light", "sans")),
    (("isometric",), ("sans", "round", "light")),
    (("geometric collage", "typographic", "modular"), ("sans-black", "sans", "round")),
]
_DEFAULT_FONT_PREFS = ("sans", "serif", "round", "light", "sans-black")
# 思源双族（黑/宋）才有过硬的拉丁字形；书法/圆体系列的西文撑不起海报
_LATIN_OK = ("sans", "sans-black", "serif", "light")
_LATIN_RE = re.compile(r"[A-Za-z0-9]")


def _font_prefs(medium: str, title) -> List[str]:
    """该媒介下按气质排序的字体候选；拉丁占比高的标题只留思源双族。"""
    m = (medium or "").lower()
    prefs = _DEFAULT_FONT_PREFS
    for keys, p in _MEDIUM_FONT_PREFS:
        if any(k in m for k in keys):
            prefs = p
            break
    if title:
        t = re.sub(r"\s+", "", str(title))
        if t and sum(1 for ch in t if _LATIN_RE.match(ch)) / len(t) > 0.34:
            prefs = [s for s in prefs if s in _LATIN_OK] or ["serif", "sans"]
    return list(prefs)


def assign_variants(requests: List[dict]) -> List[dict]:
    """同一产品类型内，给每条预分配互不相同的 媒介×色族×构图，强制铺开、防同质；
    字体在整批范围内按「候选里用得最少的优先」分配，保证字面也铺开、不塌回黑体。"""
    seen = {}
    font_used = {}   # 字体全局使用计数（跨产品类型），无标题的请求不占名额
    out = []
    for r in requests:
        r = dict(r)
        pt = r.get("product_type")
        pool = POOLS.get(pt)
        if pool:
            j = seen.get(pt, 0)
            seen[pt] = j + 1
            medium = pool["media"][j % len(pool["media"])]
            r["variant"] = {
                "medium": medium,
                "palette": pool["palettes"][j % len(pool["palettes"])],
                # 构图用错步长(2)，让媒介/色族/构图三轴尽量不对齐
                "composition": COMPOSITIONS[(j * 2) % len(COMPOSITIONS)],
            }
            if r.get("title"):
                # 后期排版字体（不进模型 payload，出图前会剥掉）
                prefs = _font_prefs(medium, r["title"])
                font = min(prefs, key=lambda s: (font_used.get(s, 0), prefs.index(s)))
                font_used[font] = font_used.get(font, 0) + 1
                r["variant"]["font"] = font
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


def _load_font(size: int, spec: dict = None):
    spec = spec or FONT_STYLES["sans"]
    for path in spec["paths"]:
        if os.path.exists(path):
            font = ImageFont.truetype(path, size)
            if spec.get("axes"):
                try:  # 可变字体拉字重轴（思源黑/宋），非可变字库直接跳过
                    font.set_variation_by_axes(spec["axes"])
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


_EMOJI_RANGES = (
    (0x1F000, 0x1FAFF),  # emoji 主区（含 🤖）
    (0x2600, 0x27BF),    # 杂项符号与装饰符
    (0x2300, 0x23FF),    # 技术符号（⌚⏰ 等）
    (0x2B00, 0x2BFF),
    (0xFE00, 0xFE0F),    # 变体选择符
    (0x200D, 0x200D),    # 零宽连接符
)


def _clean_title(text: str) -> str:
    """标题字库（思源黑/宋、华文楷/仿宋、幼圆）都没有 emoji 字形，画出来是方框——剔除并收紧空格。"""
    s = "".join(ch for ch in text
                if not any(a <= ord(ch) <= b for a, b in _EMOJI_RANGES))
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r" +(?=[：、。，！？；）])", "", s)   # 剔除 emoji 后残留在全角标点前的空格
    s = re.sub(r" ?\n ?", "\n", s)
    return s.strip()


def _compress_steps(text: str) -> List[str]:
    """标题自适应压缩候选（保真度降序）：全文 → 去掉换行尾巴 → 强分隔符前的主标题
    → 逗号前段。封面是海报不是说明书：排不下时宁可只放主标题，也不把长文挤成小字。"""
    steps = [text]
    para = text.split("\n", 1)[0].strip()
    if para and para not in steps:
        steps.append(para)                      # 丢掉硬换行后的尾巴（如“（第二期）”）
    head = re.split(r"\s*(?:：|:|——|—|\||｜|·)\s*", para, maxsplit=1)[0].strip()
    if head and head not in steps:
        steps.append(head)                      # 只留主标题
    if len(head) > 24:
        head2 = re.split(r"[，,、；;。]", head, maxsplit=1)[0].strip()
        if head2 and head2 not in steps:
            steps.append(head2)                 # 主标题仍太长，再砍到第一个逗号
    return steps


def _line_w(font, track: int, line: str) -> float:
    if not line:
        return 0.0
    return sum(font.getlength(ch) for ch in line) + track * (len(line) - 1)


_NO_LINE_HEAD = "、。，．！？：；…—·）」』】〉》,.!?:;)]}"   # 避头：不出现在行首
_NO_LINE_TAIL = "（「『【〈《([{"                              # 避尾：不留在行尾


def _wrap_lines(text: str, font, track: int, max_w: float) -> List[str]:
    """按字符贪心折行（CJK 可任意断），带简易避头尾；\\n 视为硬换行。"""
    lines = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        cur, cur_w = "", 0.0
        for ch in para:
            w = font.getlength(ch)
            add = w if not cur else w + track
            if cur and cur_w + add > max_w:
                if ch in _NO_LINE_HEAD:          # 闭合标点黏回上一行，宁可微超宽
                    lines.append(cur + ch)
                    cur, cur_w = "", 0.0
                    continue
                if cur[-1] in _NO_LINE_TAIL:     # 行尾开括号挪到下一行
                    carry = cur[-1]
                    lines.append(cur[:-1])
                    cur = carry + ch
                    cur_w = font.getlength(carry) + track + w
                    continue
                lines.append(cur)
                cur, cur_w = ch, w
            else:
                cur, cur_w = cur + ch, cur_w + add
        if cur:
            lines.append(cur)
    return lines


def _layout_title(text: str, max_w: float, max_block_h: int, size_cap: int = 0,
                  spec: dict = None):
    """多行自适应排版：自上而下扫字号，按行数各记录能用的最大字号，
    再按「有效字号（封顶 size_cap）足够大时行数越少越好」选方案——
    短标题保持单行大字，长标题才折行；最小字号仍放不下时按行截断、末行补 '…'。
    返回 (font, size, lines, track, line_h, gap, truncated)，text 为空返回 None。"""
    spec = spec or FONT_STYLES["sans"]
    upper = max(28, max_block_h)
    cap = size_cap or upper
    cands = {}      # 行数 -> 该行数下最大可用字号的布局
    fallback = None
    for size in range(upper, 25, -2):
        font = _load_font(size, spec)
        track = int(size * spec["track"])
        lines = _wrap_lines(text, font, track, max_w)
        if not lines:
            return None
        bb = font.getbbox("国Ag")
        line_h = bb[3] - bb[1]
        gap = int(line_h * 0.22)
        block_h = len(lines) * line_h + (len(lines) - 1) * gap
        widest = max(_line_w(font, track, ln) for ln in lines)
        if widest <= max_w * 1.02 and block_h <= max_block_h:
            cands.setdefault(len(lines), (font, size, lines, track, line_h, gap))
            if len(lines) == 1:
                break       # 字号再小行数只会不变或更差
        else:
            fallback = (font, size, lines, track, line_h, gap)
    if cands:
        # 行数更少的方案只要有效字号不低于最优的 60% 就优先——
        # 字符级折行没有词感，宁可单行小一点也别在词中间断行。
        # 另加绝对豁免：字号本身够体面（≥55% 封顶值）的少行方案直接合格，
        # 防止行高紧凑的字库（如幼圆）用虚高的多行字号把单行挤掉。
        best_eff = max(min(c[1], cap) for c in cands.values())
        n = min(k for k, c in cands.items()
                if min(c[1], cap) >= min(best_eff * 0.6, cap * 0.55))
        font, size, lines, track, line_h, gap = cands[n]
        return font, size, lines, track, line_h, gap, False
    font, size, lines, track, line_h, gap = fallback
    keep = max(1, int((max_block_h + gap) // (line_h + gap)))
    truncated = keep < len(lines)
    if truncated:
        lines = lines[:keep]
        last = lines[-1]
        while last and _line_w(font, track, last + "…") > max_w:
            last = last[:-1]
        lines[-1] = last + "…"
    return font, size, lines, track, line_h, gap, truncated


def _luma_stats(img, rect):
    crop = img.crop(rect).convert("L").resize((32, 32))
    px = list(crop.getdata())
    n = len(px)
    mean = sum(px) / n
    std = (sum((v - mean) ** 2 for v in px) / n) ** 0.5
    return mean, std


def draw_title_overlay(img: Image.Image, text: str, composition: str,
                       font_style: str = "sans") -> Image.Image:
    """把标题用真字体排进预留安全区：多行自适应折行、自动对比、字距、压印式细投影。
    font_style 取 FONT_STYLES 的键，由媒介气质决定（见 _pick_font_style）。"""
    img = img.convert("RGB")
    W, H = img.size
    text = _clean_title(text)
    if not text:
        return img
    spec = FONT_STYLES.get(font_style) or FONT_STYLES["sans"]
    zone, align = _zone_from_composition(composition)
    rx0, ry0, rx1, ry1 = _region_rect(W, H, zone)
    max_w, max_h = rx1 - rx0, ry1 - ry0
    size_cap = int(H * 0.16)
    size_floor = int(H * 0.05)                      # 低于这个字号就不体面了 → 压缩文案
    lines_cap = 2 if zone in ("top", "bottom") else 3
    block_h = int(max_h * 0.85)
    chosen, layout = text, None
    for cand in _compress_steps(text):
        lay = _layout_title(cand, max_w, block_h, size_cap=size_cap, spec=spec)
        if lay is None:
            return img
        if not lay[6] and lay[1] >= size_floor and len(lay[2]) <= lines_cap:
            chosen, layout = cand, lay
            break
    if layout is None:
        # 压到只剩主标题仍放不下：在 floor 字号下硬截 + …
        chosen = _compress_steps(text)[-1]
        font = _load_font(size_floor, spec)
        track = int(size_floor * spec["track"])
        wrapped = _wrap_lines(chosen, font, track, max_w)[:lines_cap]
        last = wrapped[-1]
        while last and _line_w(font, track, last + "…") > max_w:
            last = last[:-1]
        wrapped[-1] = last + "…"
        bb = font.getbbox("国Ag")
        lh = bb[3] - bb[1]
        layout = (font, size_floor, wrapped, track, lh, int(lh * 0.22), True)
    font, size, lines, track, line_h, gap, truncated = layout
    stroke_w = int(size * spec["stroke"])   # 细笔画字库（楷/仿宋/幼圆）轻微加粗
    if chosen != text or truncated:
        logging.info("  标题自适应压缩: %r → %s", text, " / ".join(lines))

    line_ws = [_line_w(font, track, ln) for ln in lines]
    block_w = max(line_ws)
    block_h = len(lines) * line_h + (len(lines) - 1) * gap
    xs = [rx0 + (max_w - lw) // 2 if align == "center" else rx0 for lw in line_ws]
    by0 = ry0 + (max_h - block_h) // 2

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

    # 背景在安全区偏花/对比不足时，只在文字块范围垫一层羽化柔光底（不横贯全图）
    contrast = abs(main[0] - luma)
    if std > 40 or contrast < 95:
        pad_x, pad_y = int(size * 0.55), int(size * 0.4)
        x_min = min(xs)
        x_max = max(x + w for x, w in zip(xs, line_ws))
        bx = (int(x_min - pad_x), int(by0 - pad_y),
              int(x_max + pad_x), int(by0 + block_h + pad_y))
        scol = (0, 0, 0, 130) if main[0] > 120 else (248, 246, 240, 165)
        scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(scrim).rounded_rectangle(bx, radius=int(size * 0.6), fill=scol)
        scrim = scrim.filter(ImageFilter.GaussianBlur(int(size * 0.7)))
        img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def _draw_block(target: Image.Image, dx: float, dy: float, color):
        d = ImageDraw.Draw(target)
        y = by0 + dy
        for ln, lx in zip(lines, xs):
            cx = lx + dx
            for ch in ln:
                d.text((cx, y), ch, font=font, fill=color,
                       stroke_width=stroke_w, stroke_fill=color)
                cx += font.getlength(ch) + track
            y += line_h + gap

    # 1) 柔投影（光来自左上，投影落右下）→ 让字脱离背景、有体积
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_block(sh, int(size * 0.05), int(size * 0.06), shadow)
    sh = sh.filter(ImageFilter.GaussianBlur(max(1, size // 24)))
    layer = Image.alpha_composite(layer, sh)
    # 2) 压印高光/暗边（与光源一致的 1px 偏移）→ letterpress 质感
    _draw_block(layer, -1, -1, emboss)
    # 3) 主字面
    _draw_block(layer, 0, 0, main)

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
                composition: str, font_style: str, overlay: bool) -> dict:
    """单条封面：出图 →（overlay 时）后期排版标题 → 存盘。供线程池并发调用。"""
    name = f"{i+1:02d}_{c.product_type}"
    path = os.path.join(OUT, f"{name}.png")
    prompt = c.prompt + NO_TEXT_CLAUSE if overlay else c.prompt
    img = render(client, prompt)
    if img is not None and overlay and title:
        img = draw_title_overlay(img, title, composition, font_style)
        flabel = (FONT_STYLES.get(font_style) or FONT_STYLES["sans"])["label"]
        logging.info("  ✎ [%d] 后期排版标题（%s）: %s", i + 1, flabel, title)
    if img is not None:
        img.save(path)
        logging.info("  ✅ [%d] %s (%dx%d)", i + 1, path, *img.size)
    else:
        logging.error("  ❌ [%d] %s 出图失败", i + 1, name)
    return {"index": i + 1, "product_type": c.product_type,
            "title_text": title if overlay else c.title_text,
            "title_mode": TITLE_MODE, "spec": c.spec, "composition": composition,
            "font": font_style, "prompt": c.prompt,
            # manifest 里存相对路径，保持跨机器可读、git diff 干净
            "image": os.path.relpath(path, BASE_DIR) if img is not None else None}


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
            if rr.get("variant"):   # 字体是后期排版的事，别混进给模型的画面指令
                rr["variant"] = {k: v for k, v in rr["variant"].items() if k != "font"}
            art_requests.append(rr)

    logging.info("stage 1: %s 编译 %d 条 prompt …", TEXT_MODEL, len(art_requests))
    covers = author_prompts(client, art_requests)

    manifest = [None] * len(covers)
    logging.info("stage 2: %s 并发出图（%d workers）…", IMAGE_MODEL, WORKERS)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {}
        for i, c in enumerate(covers):
            logging.info("[%d] %s", i + 1, c.spec)
            title = real_titles[i] if i < len(real_titles) else None
            variant = (requests[i].get("variant") or {}) if i < len(requests) else {}
            comp, fstyle = variant.get("composition", ""), variant.get("font", "sans")
            futs[pool.submit(process_one, client, i, c, title, comp, fstyle, overlay)] = i
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                manifest[i] = fut.result()
            except Exception as e:   # render 内部已兜底，这里防存盘等意外异常
                logging.error("  ❌ [%d] 异常: %s", i + 1, e)
                c = covers[i]
                title = real_titles[i] if i < len(real_titles) else None
                variant = (requests[i].get("variant") or {}) if i < len(requests) else {}
                manifest[i] = {"index": i + 1, "product_type": c.product_type,
                               "title_text": title if overlay else c.title_text,
                               "title_mode": TITLE_MODE, "spec": c.spec,
                               "font": variant.get("font", "sans"),
                               "prompt": c.prompt, "image": None}

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    logging.info("完成。manifest 写入 %s/manifest.json", OUT)


if __name__ == "__main__":
    main()
