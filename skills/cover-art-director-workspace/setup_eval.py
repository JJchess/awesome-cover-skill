import json, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
IT = os.path.join(ROOT, "iteration-1")

timing = {
    ("eval-0", "with_skill"): (52527, 28363),
    ("eval-0", "without_skill"): (41440, 19500),
    ("eval-1", "with_skill"): (47993, 28218),
    ("eval-1", "without_skill"): (32375, 18824),
    ("eval-2", "with_skill"): (48344, 28004),
    ("eval-2", "without_skill"): (37082, 19156),
    ("eval-3", "with_skill"): (61575, 29519),
    ("eval-3", "without_skill"): (33911, 19256),
}

evals = {
    "eval-0": {"eval_id": 0, "eval_name": "yunketang-with-title", "type": "云课堂", "title": "Rust 内存模型深度拆解"},
    "eval-1": {"eval_id": 1, "eval_name": "code-lab-notebook", "type": "代码实验室", "title": "金融时间序列与冲击预测"},
    "eval-2": {"eval_id": 2, "eval_name": "interactive-multiagent", "type": "互动场景", "title": None},
    "eval-3": {"eval_id": 3, "eval_name": "yunketang-batch-diversity", "type": "云课堂", "title": None},
}

prompts = {
    "eval-0": "云课堂课程封面，title「Rust 内存模型深度拆解」，要求图里显示标题。",
    "eval-1": "代码实验室 notebook 实验「金融时间序列与冲击预测」封面，16:10。",
    "eval-2": "互动场景：多个 AI Agent 协作完成市场调研的封面。",
    "eval-3": "云课堂一次出 3 门课封面（Python数据分析入门/深度学习进阶之路/算法与数据结构体系课）。",
}

AI_SMELL = ["neon", "matrix", "circuit", "glassmorphism", "volumetric", "4k", "cyberpunk", "glowing", "futuristic", "hologram", "holographic"]

def read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def grade(eval_id, txt):
    low = txt.lower()
    res = []
    # A1: 16:10 present
    res.append({"text": "声明 16:10 画幅", "passed": "16:10" in txt, "evidence": "found '16:10'" if "16:10" in txt else "missing 16:10"})
    # A2: explicit avoid list with multiple AI-smell terms
    has_avoid = ("avoid" in low or "no neon" in low or "negative" in low)
    avoid_terms = sum(1 for t in ["neon", "circuit", "matrix", "glossy", "plastic", "bokeh", "lens flare", "floating ui", "chrome", "garbled"] if t in low)
    res.append({"text": "含明确的去AI味排除清单(≥4项)", "passed": has_avoid and avoid_terms >= 4, "evidence": f"avoid section={has_avoid}, terms={avoid_terms}"})
    # A3: does NOT itself reach for AI-smell aesthetics as the look (count smell words in positive desc)
    # count occurrences that are NOT inside an avoid/negative clause.
    # A smell word is "negative" if its surrounding window contains 'no ' or 'avoid'.
    pos_smell = 0
    for t in AI_SMELL:
        for m in re.finditer(re.escape(t), low):
            window = low[max(0, m.start()-40):m.end()+5]
            if "no " in window or "avoid" in window or "without" in window:
                continue
            pos_smell += 1
    res.append({"text": "未把AI味美学(霓虹/玻璃拟态/体积光等)当作正向风格", "passed": pos_smell == 0, "evidence": f"positive AI-smell mentions={pos_smell}"})
    # A4: routed to correct product type mentioned
    t = evals[eval_id]["type"]
    res.append({"text": f"正确识别产品类型({t})", "passed": t in txt, "evidence": f"'{t}' present={t in txt}"})
    # A5: title rendering for title cases
    if evals[eval_id]["title"]:
        title = evals[eval_id]["title"]
        # exact quoted title + spell exactly instruction
        quoted = (f'"{title}"' in txt) or (f"「{title}」" in txt and "spell" in low)
        spell = "spell" in low and ("exact" in low or "exactly" in low)
        res.append({"text": "标题以引号锁定确切文字并要求精确拼写", "passed": (f'"{title}"' in txt) and spell, "evidence": f"quoted={f'\"{title}\"' in txt}, spell-exactly={spell}"})
    # A6: batch diversity for eval-3
    if eval_id == "eval-3":
        mediums = ["isometric", "paper-craft", "paper craft", "editorial illustration", "diorama", "risograph", "collage", "blueprint"]
        found_med = set(m for m in mediums if m in low)
        # count distinct palette anchor words
        palettes = ["sage", "amber", "terracotta", "dusty blue", "coral", "oatmeal", "brass", "forest green", "cream", "ink", "sand", "ivory"]
        found_pal = set(p for p in palettes if p in low)
        diverse = len(found_med) >= 2 and len(found_pal) >= 4
        res.append({"text": "批量3张媒介与色族明显铺开(≥2媒介 & ≥4色彩词)", "passed": diverse, "evidence": f"mediums={sorted(found_med)}, palette_words={len(found_pal)}"})
    return res

for ev, cfgs in [("eval-0", None)] + [(e, None) for e in ["eval-1","eval-2","eval-3"]]:
    meta = {"eval_id": evals[ev]["eval_id"], "eval_name": evals[ev]["eval_name"], "prompt": prompts[ev], "assertions": []}
    os.makedirs(os.path.join(IT, ev), exist_ok=True)
    with open(os.path.join(IT, ev, "eval_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

for (ev, cfg), (ms, tok) in timing.items():
    d = os.path.join(IT, ev, cfg)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "timing.json"), "w", encoding="utf-8") as f:
        json.dump({"total_tokens": tok, "duration_ms": ms, "total_duration_seconds": round(ms/1000, 1)}, f, indent=2)
    txt = read(os.path.join(d, "outputs", "answer.md"))
    exps = grade(ev, txt) if cfg == "with_skill" else grade(ev, txt)
    passed = sum(1 for e in exps if e["passed"])
    with open(os.path.join(d, "grading.json"), "w", encoding="utf-8") as f:
        json.dump({"expectations": exps, "summary": {"passed": passed, "total": len(exps)}}, f, ensure_ascii=False, indent=2)
    print(f"{ev}/{cfg}: {passed}/{len(exps)} passed")

print("done")
