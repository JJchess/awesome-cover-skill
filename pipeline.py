# -*- coding: utf-8 -*-
"""
全 Gemini 封面生成管线：
  stage 1  gemini-3.5-flash  扮演 cover-art-director skill，把请求编译成英文出图 prompt
  stage 2  Nano Banana       把 prompt 渲染成封面，本地裁 16:10 存盘

一批 N 张封面 = 1 次文本调用（一次产出 N 条 prompt，内部跑多样引擎）+ N 次文生图调用。

用法:
  python pipeline.py                 # 跑内置 demo（三类各一张）
  python pipeline.py requests.json   # 读自定义请求批次
requests.json 形如:
  [{"product_type":"云课堂","title":"Rust 内存模型深度拆解","brief":"所有权、生命周期与无畏并发"},
   {"title":"金融时间序列与冲击预测","brief":"用 notebook 跑量化实验"}]   # product_type 可省，由关键词推断
"""
import os, sys, json, base64, logging
from io import BytesIO
from typing import Optional, List
from pydantic import BaseModel
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TEXT_MODEL = "gemini-3.5-flash"          # 艺术总监：编 prompt
# Nano Banana 出图。gemini-2.5-flash-image 是经典 Nano Banana，但渲染中文标题会丢字；
# gemini-3.1-flash-image 同属 flash-image 线、能正确渲染中文。带中文 title 时必须用 3.1。
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-3.1-flash-image")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(BASE_DIR, "skills", "cover-art-director")
OUT = "output_covers_gemini"
TARGET_RATIO = 16 / 10

DEMO_REQUESTS = [
    {"product_type": "云课堂", "title": "Rust 内存模型深度拆解",
     "brief": "所有权、生命周期与无畏并发；被引导的结构化学习"},
    {"product_type": "代码实验室", "title": "金融时间序列与冲击预测",
     "brief": "在 notebook 里跑量化实验，处理异质冲击"},
    {"product_type": "互动场景", "title": None,
     "brief": "多个 AI Agent 分工协作完成一次市场调研，多角色讨论"},
]


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
        "只有当请求带 title 时才把该文字渲染进图（title_text 原样填该文字并在 prompt 里用引号要求 "
        "spell exactly）；没有 title 则 title_text=null 且 prompt 不渲染任何文字、只留标题安全区。\n"
        "对每个请求产出一个对象：product_type / title_text / spec（一行：类型 · 媒介 · 色族 · 构图原型）/ "
        "prompt（英文，含浓缩的 avoid 段）。\n\n"
        "===== SKILL.md =====\n" + skill +
        "\n\n===== references/style-pools.md =====\n" + pools
    )


def author_prompts(client: genai.Client, requests: List[dict], retries: int = 4) -> List[Cover]:
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


def render(client: genai.Client, prompt: str, out_path: str, retries: int = 3) -> bool:
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
                    img = crop_to_ratio(img, TARGET_RATIO)
                    img.save(out_path)
                    logging.info("  ✅ %s (%dx%d)", out_path, *img.size)
                    return True
            logging.warning("  无图像数据，重试 %d", attempt + 1)
        except Exception as e:
            logging.warning("  attempt %d 失败: %s", attempt + 1, e)
    return False


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("No GEMINI_API_KEY in .env")
    requests = DEMO_REQUESTS
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            requests = json.load(f)

    client = genai.Client(api_key=api_key)
    os.makedirs(OUT, exist_ok=True)

    logging.info("stage 1: %s 编译 %d 条 prompt …", TEXT_MODEL, len(requests))
    covers = author_prompts(client, requests)

    manifest = []
    logging.info("stage 2: %s 出图 …", IMAGE_MODEL)
    for i, c in enumerate(covers):
        name = f"{i+1:02d}_{c.product_type}"
        logging.info("[%d] %s", i + 1, c.spec)
        path = os.path.join(OUT, f"{name}.png")
        ok = render(client, c.prompt, path)
        manifest.append({"index": i + 1, "product_type": c.product_type,
                         "title_text": c.title_text, "spec": c.spec,
                         "prompt": c.prompt, "image": path if ok else None})

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    logging.info("完成。manifest 写入 %s/manifest.json", OUT)


if __name__ == "__main__":
    main()
