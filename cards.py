#!/usr/bin/env python3
"""记忆机制 v2 · 分层卡片工具（cards.py）

设计见 /mnt/d/Pi/projects/agent-memory/DESIGN.md
零依赖（Python 标准库）。数据：~/.agents/memory/cards.json
存量 memory.json **永不读写**（那是 L4 归档，P2 阶段才迁移）。

分层：
  L1 工作法   按触发场景分（writing/design/coding/ops/asset/collab/...）
  L2 项目状态 按项目分
  L3 环境事实 路径/端口/命令/坑
  L5 调优日志 老闫每次纠正我的原因与边界

核心原则（老闫 2026-09-11 定）：
  ① 条目写成"要这么做"的指令式；判据是**下次零上下文读回来不走样**
  ② 主维度 = 触发场景（when），主题只作副标签
  ③ 注入按**预算**取，不按条数取

用法:
  cards.py add --layer L1 --scene writing --text "..." [--note ...] [--why ...] [--tag a,b] [--src ...]
  cards.py add --layer L2 --project deep-signal --status active --text "..."
  cards.py list [--layer L1] [--scene writing] [--project x] [--tag t]
  cards.py search <关键词>
  cards.py show <id> / edit <id> [--text ...] / rm <id> / use <id>
  cards.py build [--scene writing] [--budget 3500]     # 生成 BOOT.md 与各层正文镜像
  cards.py doctor                                      # 体检
  cards.py stats
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

MEM_DIR = os.path.expanduser("~/.agents/memory")
CARDS_FILE = os.path.join(MEM_DIR, "cards.json")
BOOT_FILE = os.path.join(MEM_DIR, "BOOT.md")

LAYERS = ("L1", "L2", "L3", "L5")
SCENES = ("writing", "design", "coding", "ops", "asset", "collab", "meta", "other")
STATUSES = ("active", "paused", "done")
DEFAULT_BUDGET = 3500

# 场景 → 中文名（生成正文文件与 BOOT 标题用）
SCENE_CN = {
    "writing": "写文章/标题/摘要", "design": "设计/视觉/排版",
    "coding": "写代码/建系统", "ops": "服务器/部署/排障",
    "asset": "能力与工具(生图/搜索/发文)", "collab": "与老闫协作的方式",
    "meta": "记忆与方法论自身", "other": "其他",
}

# 指代词黑名单（doctor 告警用，启发式）
PRONOUNS = ("这个", "那个", "上次", "上述", "之前提到", "该方案", "它")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today():
    return datetime.now().strftime("%m-%d")


def est_tokens(s):
    """粗估 token：汉字×1.05 + 其他字符×0.3"""
    cjk = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    return int(cjk * 1.05 + (len(s) - cjk) * 0.3) + 1


def load():
    if not os.path.exists(CARDS_FILE):
        return {"version": 2, "cards": []}
    with open(CARDS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save(data):
    os.makedirs(MEM_DIR, exist_ok=True)
    tmp = CARDS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CARDS_FILE)


def next_id(data):
    nums = [int(c["id"][1:]) for c in data["cards"] if re.fullmatch(r"c\d+", c["id"])]
    return f"c{max(nums) + 1 if nums else 1}"


def norm(s):
    return "".join(ch.lower() for ch in s if not ch.isspace())


# ---------------------------------------------------------------- 写

def cmd_add(a):
    if a.layer == "L2" and not a.project:
        print("❌ L2（项目状态）必须带 --project")
        return 1
    if a.layer in ("L1", "L5") and not a.scene:
        print("❌ L1/L5 必须带 --scene（触发场景）——这正是能被检索到的关键")
        return 1
    data = load()
    n = norm(a.text)
    for c in data["cards"]:
        if norm(c["text"]) == n:
            print(f"⚠️ 内容完全相同，未添加（已有 {c['id']}）")
            return 1
    rec = {
        "id": next_id(data), "layer": a.layer,
        "scene": a.scene if a.layer != "L2" else "",
        "project": a.project or "", "status": a.status or "",
        "text": a.text.strip(),
        "note": (a.note or "").strip(), "why": (a.why or "").strip(),
        "tags": [t.strip() for t in a.tag.split(",") if t.strip()] if a.tag else [],
        "src": a.src or f"cli·{today()}",
        "created": now_iso(), "updated": now_iso(), "hits": 0,
    }
    data["cards"].append(rec)
    save(data)
    print(f"✅ 已存 {rec['id']} [{rec['layer']}"
          + (f"/{rec['scene']}" if rec["scene"] else f"/{rec['project']}")
          + f"] {rec['text'][:60]}")
    return 0


def _find(data, cid):
    for c in data["cards"]:
        if c["id"] == cid:
            return c
    return None


def cmd_edit(a):
    data = load()
    c = _find(data, a.id)
    if not c:
        print(f"❌ 未找到 {a.id}")
        return 1
    for k in ("text", "note", "why", "scene", "project", "status", "src"):
        v = getattr(a, k, None)
        if v is not None:
            c[k] = v.strip()
    if a.tag:
        c["tags"] = [t.strip() for t in a.tag.split(",") if t.strip()]
    c["updated"] = now_iso()
    save(data)
    print(f"✅ 已更新 {a.id}")
    return 0


def cmd_rm(a):
    data = load()
    for i, c in enumerate(data["cards"]):
        if c["id"] == a.id:
            del data["cards"][i]
            save(data)
            print(f"🗑️ 已删除 {a.id}")
            return 0
    print(f"❌ 未找到 {a.id}")
    return 1


def cmd_use(a):
    data = load()
    c = _find(data, a.id)
    if not c:
        print(f"❌ 未找到 {a.id}")
        return 1
    c["hits"] = c.get("hits", 0) + 1
    c["last_used"] = now_iso()
    save(data)
    print(f"✅ {a.id} 命中 +1（{c['hits']}）")
    return 0


# ---------------------------------------------------------------- 读

def _fmt(c, width=70):
    head = c["text"][:width] + ("…" if len(c["text"]) > width else "")
    loc = c["scene"] or c["project"] or "-"
    tag = (" #" + " #".join(c["tags"])) if c["tags"] else ""
    return f"· {c['id']} [{c['layer']}/{loc}]{tag} {head}"


def cmd_list(a):
    data = load()
    items = data["cards"]
    if a.layer:
        items = [c for c in items if c["layer"] == a.layer]
    if a.scene:
        items = [c for c in items if c["scene"] == a.scene]
    if a.project:
        items = [c for c in items if c["project"] == a.project]
    if a.tag:
        items = [c for c in items if a.tag in c.get("tags", [])]
    if not items:
        print("（无）")
        return 0
    for c in items:
        print(_fmt(c))
    print(f"\n共 {len(items)} 条")
    return 0


def cmd_search(a):
    data = load()
    q = norm(a.query)
    hits = [c for c in data["cards"]
            if q in norm(c["text"] + c.get("note", "") + c.get("why", "")
                         + " ".join(c.get("tags", [])) + c.get("scene", "") + c.get("project", ""))]
    if a.layer:
        hits = [c for c in hits if c["layer"] == a.layer]
    if not hits:
        print("🔍 未找到。")
        return 0
    for c in hits:
        print(_fmt(c, 90))
    print(f"\n共 {len(hits)} 条匹配")
    return 0


def cmd_show(a):
    data = load()
    c = _find(data, a.id)
    if not c:
        print(f"❌ 未找到 {a.id}")
        return 1
    print(json.dumps(c, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------- 生成

def _card_block(c, indent=""):
    out = [f"{indent}- **{c['text']}**"]
    if c.get("note"):
        out.append(f"{indent}  {c['note']}")
    if c.get("why"):
        out.append(f"{indent}  · 为什么：{c['why']}")
    out.append(f"{indent}  · `{c['id']}` {c['layer']}"
               + (f"/{c['scene']}" if c["scene"] else f"/{c['project']}")
               + (f" ｜ src: {c['src']}" if c.get("src") else ""))
    return "\n".join(out)


def _render_l1(c):
    return f"- `[{c['scene']}]` {c['text'][:52]}" + ("…" if len(c["text"]) > 52 else "") + f"  → {c['id']}"


def _render_l5(c):
    return (f"- {c['text'][:70]}" + ("…" if len(c["text"]) > 70 else "")
            + (f"  · 为什么：{c['why'][:40]}" if c.get("why") else ""))


def _render_l2(c):
    return f"  - {c['text']}" + (f"（{c['note']}）" if c.get("note") else "")


def _pick(cards, budget, render=None, prefer_scene=None):
    """按预算取卡片：场景匹配优先，其次更新时间倒序；返回 (选中列表, 丢弃数)"""
    render = render or _card_block

    def key(c):
        return (0 if (prefer_scene and c.get("scene") == prefer_scene) else 1,
                _rev(c.get("updated", "")))

    chosen, used, dropped = [], 0, 0
    for c in sorted(cards, key=key):
        cost = est_tokens(render(c)) + 2
        if used + cost > budget:
            dropped += 1
            continue
        chosen.append(c)
        used += cost
    return chosen, dropped


def _rev(ts):
    """越新的排越前：用负的时间戳排序必须同类型，转成字符串反转即可"""
    return "".join(chr(0x10FFFF - ord(ch)) for ch in ts)


def cmd_build(a):
    data = load()
    cards = data["cards"]
    if not cards:
        print("⚠️ 卡片库为空，先 add 几条。")
    os.makedirs(os.path.join(MEM_DIR, "playbook"), exist_ok=True)
    os.makedirs(os.path.join(MEM_DIR, "projects"), exist_ok=True)
    os.makedirs(os.path.join(MEM_DIR, "archive"), exist_ok=True)

    # —— 正文镜像（按需取用的"正文"）
    written = []
    for sc in SCENES:
        cs = [c for c in cards if c["layer"] == "L1" and c["scene"] == sc]
        if not cs:
            continue
        p = os.path.join(MEM_DIR, "playbook", f"{sc}.md")
        body = [f"# 工作法 · {SCENE_CN.get(sc, sc)}（{sc}）",
                "", f"> L1 正文。生成于 {now_iso()}，勿手改（改卡片库后 build）。", ""]
        body += [_card_block(c) for c in cs]
        open(p, "w", encoding="utf-8").write("\n".join(body) + "\n")
        written.append(p)
    for c in cards:
        if c["layer"] != "L2" or not c["project"]:
            continue
        p = os.path.join(MEM_DIR, "projects", f"{c['project']}.md")
        cs = [x for x in cards if x["layer"] == "L2" and x["project"] == c["project"]]
        body = [f"# 项目 · {c['project']}", "",
                f"> L2 正文。生成于 {now_iso()}，勿手改。", ""]
        body += [_card_block(x) for x in cs]
        open(p, "w", encoding="utf-8").write("\n".join(body) + "\n")
        written.append(p)
    for layer, fname, title in (("L3", "env.md", "环境事实"), ("L5", "rationale.md", "调优日志")):
        cs = [c for c in cards if c["layer"] == layer]
        if not cs:
            continue
        p = os.path.join(MEM_DIR, fname)
        body = [f"# {title}（{layer}）", "", f"> 生成于 {now_iso()}，勿手改。", ""]
        body += [_card_block(c) for c in cs]
        open(p, "w", encoding="utf-8").write("\n".join(body) + "\n")
        written.append(p)

    # —— BOOT.md：开场装载包（按预算取）
    b = a.budget
    alloc = {"L2": int(b * 0.30), "L5": int(b * 0.30), "L1": int(b * 0.40)}
    l2, d2 = _pick([c for c in cards if c["layer"] == "L2"], alloc["L2"], _render_l2, a.scene)
    l5, d5 = _pick([c for c in cards if c["layer"] == "L5"], alloc["L5"], _render_l5, a.scene)
    l1, d1 = _pick([c for c in cards if c["layer"] == "L1"], alloc["L1"], _render_l1, a.scene)

    out = [f"## 📁 项目状态（L2，{len(l2)} 条" + (f"，截断 {d2}" if d2 else "") + "）", ""]
    byproj = {}
    for c in l2:
        byproj.setdefault(c["project"], []).append(c)
    for pj, cs in byproj.items():
        st = cs[0].get("status") or "active"
        out.append(f"**{pj}** · {st} · 更新 {cs[0].get('updated', '')[:10]}")
        for c in cs:
            out.append(_render_l2(c))
        out.append("")
    out.append(f"## 🧭 工作法索引（L1，{len(l1)} 条" + (f"，截断 {d1}" if d1 else "") + "）")
    out.append("")
    for c in l1:
        out.append(_render_l1(c))
    out.append("")
    out.append(f"## 🎯 最近调优（L5，{len(l5)} 条" + (f"，截断 {d5}" if d5 else "") + "）")
    out.append("")
    for c in l5:
        out.append(_render_l5(c))
    out.append("")
    out.append("## 🧵 未收尾事项")
    out.append("")
    out.append("见 `~/.agents/memory/OPEN_LOOPS.md`（开场必读）。")

    body = "\n".join(out) + "\n"
    tk = est_tokens(body)
    head = [
        "# 🚀 开场装载包（BOOT.md）", "",
        f"> 自动生成于 {now_iso()}" + (f" ｜ 场景：**{a.scene}**" if a.scene else ""),
        f"> 预算 {b} tokens ｜ 本文件估算 **{tk}** tokens ｜ "
        + ("✅ 在预算内" if tk <= b else "⚠️ 超预算，需裁"),
        "> 读法：本文件是**目录**。要正文 → `memory.py card search <词>`，或直接读 `playbook/<场景>.md` / `projects/<项目>.md`。",
        "", "",
    ]
    open(BOOT_FILE, "w", encoding="utf-8").write("\n".join(head) + body)
    print(f"✅ BOOT.md 生成：{tk} tokens / 预算 {b} " + ("✅" if tk <= b else "⚠️ 超限"))
    print(f"   L2 {len(l2)} 条(弃{d2}) ｜ L5 {len(l5)} 条(弃{d5}) ｜ L1 {len(l1)} 条(弃{d1})")
    print(f"   正文镜像 {len(written)} 个文件")
    return 0


def cmd_doctor(a):
    data = load()
    bad = {"超长": [], "缺场景": [], "指代词": [], "重复": [], "缺字段": [], "无标签": []}
    seen = {}
    for c in data["cards"]:
        t = c.get("text", "")
        if len(t) > 200:
            bad["超长"].append((c["id"], len(t)))
        if c["layer"] in ("L1", "L5") and not c.get("scene"):
            bad["缺场景"].append(c["id"])
        hit = [p for p in PRONOUNS if p in t]
        if hit:
            bad["指代词"].append((c["id"], hit))
        n = norm(t)
        if n in seen:
            bad["重复"].append((c["id"], seen[n]))
        else:
            seen[n] = c["id"]
        if c["layer"] == "L2" and (not c.get("project") or not c.get("status")):
            bad["缺字段"].append(c["id"])
        if not c.get("tags"):
            bad["无标签"].append(c["id"])
    tk = est_tokens(open(BOOT_FILE, encoding="utf-8").read()) if os.path.exists(BOOT_FILE) else 0
    print(f"🩺 体检：{len(data['cards'])} 张卡片" + (f" ｜ BOOT {tk} tokens" if tk else " ｜ BOOT 未生成"))
    for k, v in bad.items():
        if v:
            print(f"  ⚠️ {k}（{len(v)}）: " + ", ".join(str(x) for x in v[:8]) + (" …" if len(v) > 8 else ""))
    sev = sum(len(v) for k, v in bad.items() if k in ("超长", "缺场景", "重复", "缺字段"))
    print(("✅ 无严重问题" if sev == 0 else f"❗ {sev} 个严重问题待处理"))
    return 0


def cmd_stats(a):
    data = load()
    from collections import Counter
    print(f"卡片库: {CARDS_FILE}")
    print("  按层:", dict(Counter(c["layer"] for c in data["cards"])))
    print("  按场景:", dict(Counter(c["scene"] for c in data["cards"] if c["scene"])))
    if os.path.exists(BOOT_FILE):
        print(f"  BOOT.md 估算: {est_tokens(open(BOOT_FILE, encoding='utf-8').read())} tokens")
    return 0


# ---------------------------------------------------------------- CLI

def main(argv=None):
    p = argparse.ArgumentParser(description="记忆机制 v2 · 分层卡片工具")
    sub = p.add_subparsers(dest="cmd")

    def add_common(sp):
        sp.add_argument("--layer", choices=LAYERS)
        sp.add_argument("--scene", default="")
        sp.add_argument("--project", default="")
        sp.add_argument("--status", choices=STATUSES, default="")
        sp.add_argument("--tag", default="")
        sp.add_argument("--note", default="")
        sp.add_argument("--why", default="")
        sp.add_argument("--src", default="")

    s = sub.add_parser("add"); s.add_argument("--text", required=True); add_common(s); s.set_defaults(fn=cmd_add)
    s = sub.add_parser("edit"); s.add_argument("id"); s.add_argument("--text"); add_common(s); s.set_defaults(fn=cmd_edit)
    s = sub.add_parser("list"); s.add_argument("--layer"); s.add_argument("--scene"); s.add_argument("--project"); s.add_argument("--tag"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--layer"); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("show"); s.add_argument("id"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("rm"); s.add_argument("id"); s.set_defaults(fn=cmd_rm)
    s = sub.add_parser("use"); s.add_argument("id"); s.set_defaults(fn=cmd_use)
    s = sub.add_parser("build"); s.add_argument("--scene", default=None); s.add_argument("--budget", type=int, default=DEFAULT_BUDGET); s.set_defaults(fn=cmd_build)
    s = sub.add_parser("doctor"); s.set_defaults(fn=cmd_doctor)
    s = sub.add_parser("stats"); s.set_defaults(fn=cmd_stats)

    a = p.parse_args(argv)
    if not hasattr(a, "fn"):
        p.print_help()
        return 1
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
