import os, shutil, json

ROOT = os.path.dirname(os.path.abspath(__file__))
IT = os.path.join(ROOT, "iteration-1")

for ev in ["eval-0", "eval-1", "eval-2", "eval-3"]:
    evdir = os.path.join(IT, ev)
    # copy eval_metadata.json into each config dir for the viewer
    meta_src = os.path.join(evdir, "eval_metadata.json")
    for cfg in ["with_skill", "without_skill"]:
        cfgdir = os.path.join(evdir, cfg)
        if not os.path.isdir(cfgdir):
            continue
        run1 = os.path.join(cfgdir, "run-1")
        os.makedirs(run1, exist_ok=True)
        # move outputs, grading.json, timing.json into run-1
        for item in ["outputs", "grading.json", "timing.json"]:
            src = os.path.join(cfgdir, item)
            dst = os.path.join(run1, item)
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.move(src, dst)
        # copy metadata to config level so viewer (run_dir.parent) finds the prompt
        if os.path.exists(meta_src):
            shutil.copy(meta_src, os.path.join(cfgdir, "eval_metadata.json"))
    print(f"{ev}: restructured")
print("done")
