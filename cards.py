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
import difflib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone

MEM_DIR = os.path.expanduser("~/.agents/memory")
CARDS_FILE = os.path.join(MEM_DIR, "cards.json")
BOOT_FILE = os.path.join(MEM_DIR, "BOOT.md")

LAYERS = ("L1", "L2", "L3", "L5", "L6")
# L6 = 冷藏层（icebox）：老闫当时说“先放放”的、姜花一现的临时起意。
# 检索铁律（老闫 2026-09-11）：**先查项目总表 → L1-L5 → 都找不到才翻 L6**；L6 永不进开场。
SCENES = ("writing", "design", "coding", "ops", "asset", "collab", "meta", "other")
STATUSES = ("active", "paused", "done")
DEFAULT_BUDGET = 3500
# 项目总表：老闫要求落到 D 盘（他常开着 /mnt/d/Pi），便于他和阿衍两头都能查
PROJECT_TABLE = "/mnt/d/Pi/项目总表.md"
PROJECT_TABLE_HTML = "/mnt/d/Pi/项目总表.html"

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
        return {"version": 2, "cards": [], "projects": {}}
    with open(CARDS_FILE, encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("projects", {})
    return d


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


def _sim(a, b):
    """文本相似度（0~1）：difflib 序列比对，中文短句上比 n-gram 可靠"""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _similar_existing(data, layer, scene, project, text, topn=3, floor=0.2):
    """写入前提醒：同层（同场景/项目）里已有哪几条长得像——**写入时有上下文，此刻判断最准**"""
    hits = []
    for c in data["cards"]:
        if c["layer"] != layer:
            continue
        if scene and c.get("scene") != scene:
            continue
        if project and c.get("project") != project:
            continue
        s = _sim(text, c["text"])
        if s >= floor:
            hits.append((s, c))
    hits.sort(key=lambda x: -x[0])
    return hits[:topn]


# ---------------------------------------------------------------- 写

def cmd_add(a):
    if a.layer == "L2" and not a.project:
        print("❌ L2（项目状态）必须带 --project")
        return 1
    if a.layer in ("L1", "L5") and not a.scene:
        print("❌ L1/L5 必须带 --scene（触发场景）——这正是能被检索到的关键")
        return 1
    if a.layer == "L6" and not (a.note or a.why):
        print("❌ L6（冷藏）必须写 --note：当时为什么放放（否则以后翻到也不知道该不该拾起）")
        return 1
    data = load()
    n = norm(a.text)
    for c in data["cards"]:
        if norm(c["text"]) == n:
            print(f"⚠️ 内容完全相同，未添加（已有 {c['id']}）")
            return 1
    near = _similar_existing(data, a.layer, a.scene, a.project, a.text)
    if near:
        print("👀 写入前提醒——同层已有相似卡片，先确认是不是同一件事（是就该改/并，不是就忽略）：")
        for s, c in near:
            print(f"   {s:.0%} {c['id']}: {c['text'][:56]}")
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
    # 只覆盖**显式传了值**的字段：空默认值（""）一律视为“没传”，绝不能抹掉原字段
    for k in ("text", "note", "why", "scene", "project", "status", "src"):
        v = getattr(a, k, None)
        if v:
            c[k] = v.strip()
    if a.tag:
        c["tags"] = [t.strip() for t in a.tag.split(",") if t.strip()]
    if a.layer:
        c["layer"] = a.layer
    c["updated"] = now_iso()
    save(data)
    # 改完做一次基本校验
    if c["layer"] in ("L1", "L5") and not c.get("scene"):
        print(f"⚠️ {a.id} 是 {c['layer']} 但缺 scene（触发场景）——请补 --scene")
    if c["layer"] == "L2" and not c.get("project"):
        print(f"⚠️ {a.id} 是 L2 但缺 project")
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
    # 冷藏层永远排最后（老闫 2026-09-11：先查项目总表 → L1-L5 → 都找不到才翻 L6）
    hits.sort(key=lambda c: 1 if c["layer"] == "L6" else 0)
    if not hits:
        print("🔍 未找到。")
        return 0
    for c in hits:
        print(("🧊 " if c["layer"] == "L6" else "") + _fmt(c, 90))
    print(f"\n共 {len(hits)} 条匹配" + ("（🧊 = 冷藏层，当年说先放放的）" if any(c["layer"] == "L6" for c in hits) else ""))
    return 0


def cmd_icebox(a):
    """列出全部冷藏条目（L6）——只在项目总表与 L1-L5 都找不到时才翻这里"""
    data = load()
    cs = [c for c in data["cards"] if c["layer"] == "L6"]
    if not cs:
        print("🧊 冷藏层是空的（没有『先放放』的东西）")
        return 0
    for c in cs:
        print(f"🧊 {c['id']} {c['text']}")
        if c.get("note"):
            print(f"    放放的理由：{c['note']}")
    print(f"\n共 {len(cs)} 条冷藏。\n使用铁律：先查项目总表 → L1-L5 → 都找不到才翻这里。")
    return 0


def cmd_show(a):
    data = load()
    c = _find(data, a.id)
    if not c:
        print(f"❌ 未找到 {a.id}")
        return 1
    print(json.dumps(c, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------- 项目

def cmd_proj(a):
    data = load()
    P = data.setdefault("projects", {})
    if a.action == "list":
        if not P:
            print("（还没登记项目）")
            return 0
        for k, v in P.items():
            al = ("／" + "、".join(v.get("aliases", []))) if v.get("aliases") else ""
            print(f"· {k}{al} [{v.get('status','active')}] {v.get('title','')} {v.get('oneliner','')}")
        return 0
    if a.action == "find":
        q = (a.name or "").lower()
        hits = []
        for k, v in P.items():
            blob = " ".join([k, v.get("title", ""), v.get("oneliner", ""),
                             " ".join(v.get("aliases", [])), v.get("path", "")]).lower()
            if q in blob:
                hits.append((k, v))
        for k, v in hits:
            print(f"· {k} [{v.get('status','active')}] {v.get('title','')}｜{v.get('oneliner','')}"
                  + (f"\n    路径：{v.get('path')}" if v.get("path") else ""))
        print(f"\n共 {len(hits)} 个匹配" + ("" if hits else " ——换短一点的关键词，或直接看 " + PROJECT_TABLE))
        return 0
    if a.action == "show":
        v = P.get(a.name)
        print(json.dumps(v, ensure_ascii=False, indent=2) if v else f"❌ 未登记 {a.name}")
        return 0
    if a.action == "rm":
        P.pop(a.name, None)
        save(data)
        print(f"🗑️ 已移除项目 {a.name}（卡片未动）")
        return 0
    v = P.setdefault(a.name, {"aliases": [], "oneliner": "", "path": "", "status": "active", "title": ""})
    for k in ("title", "oneliner", "path", "status"):
        if getattr(a, k, None):
            v[k] = getattr(a, k)
    if a.alias:
        v["aliases"] = [x.strip() for x in a.alias.split(",") if x.strip()]
    v["updated"] = now_iso()
    save(data)
    print(f"✅ 项目已登记：{a.name} [{v['status']}] {v.get('title','')} {v.get('oneliner','')}")
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
        sc = c.get("scene", "")
        return (0 if (prefer_scene and sc == prefer_scene) else 1,
                SCENES.index(sc) if sc in SCENES else 99,   # 同场景相邻，便于扫读
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
    for layer, fname, title in (("L3", "env.md", "环境事实"), ("L5", "rationale.md", "调优日志"),
                                ("L6", "icebox.md", "冷藏库（先放放 / 姜花一现的临时起意）")):
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
    alloc = {"L1": int(b * 0.55), "L5": int(b * 0.40)}
    l5, d5 = _pick([c for c in cards if c["layer"] == "L5"], alloc["L5"], _render_l5, a.scene)
    l1, d1 = _pick([c for c in cards if c["layer"] == "L1"], alloc["L1"], _render_l1, a.scene)

    # —— L2：开场**只列项目名**（老闫 09-11：不需要每次记住每个项目的现状/决策/卡点/下一步）
    projs = data.get("projects", {})
    byp = {}
    for c in cards:
        if c["layer"] == "L2" and c["project"]:
            byp.setdefault(c["project"], []).append(c)

    def pst(p):
        return (projs.get(p) or {}).get("status") or (byp[p][0].get("status") or "active")

    def pname(p):
        return (projs.get(p) or {}).get("title") or p

    act = sorted(p for p in byp if pst(p) == "active")
    rest = sorted(p for p in byp if pst(p) != "active")
    out = [f"## 📁 项目（进行中 {len(act)}）", ""]
    out.append("**进行中**：" + (" ・ ".join(pname(p) for p in act) or "（无）"))
    if rest:
        out.append("**已完/搁置**（不进开场）：" + " ・ ".join(pname(p) for p in rest))
    out.append("")
    out.append(f"> 要看某项目的现状/决策/下一步 → 读 `{PROJECT_TABLE}`，或 `memory.py proj find <关键词>`。")
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
    print(f"   L5 {len(l5)} 条(弃{d5}) ｜ L1 {len(l1)} 条(弃{d1}) ｜ 项目 {len(act)} 个")
    print(f"   正文镜像 {len(written)} 个文件")
    _write_project_table(data, cards, projs, byp)
    return 0


def _write_project_table(data, cards, projs, byp):
    """生成 D 盘项目总表：项目名 / 别名 / 一句话 / 路径 / 状态 + 各自的 L2 卡片要点
    用途（老闫 09-11）：他和我两头都能查；项目名对不上时也能搜到。"""
    names = sorted(set(byp.keys()) | set(projs.keys()))
    if not names:
        return
    L = ["# 项目总表", "",
         f"> 生成于 {now_iso()} ｜ 数据源 `~/.agents/memory/cards.json`——**勿手改**，改卡片后 `memory.py build` 重生成。",
         "> 用法：Ctrl+F 搜项目名 / 别名 / 关键词。老闫问『某项目怎么样了』→ 阿衍先 `memory.py proj find <关键词>` 再读本节。",
         ""]
    def status_of(n):
        return (projs.get(n) or {}).get("status") or (byp.get(n, [{}])[0].get("status") or "active")
    for st, title in (("active", "🟢 进行中"), ("paused", "⏸ 搁置"), ("done", "✅ 已完成")):
        group = [n for n in names if status_of(n) == st]
        if not group:
            continue
        L += [f"## {title}（{len(group)}）", ""]
        for n in group:
            v = projs.get(n) or {}
            head = v.get("title") or n
            L.append(f"### {head}" + (f" · `{n}`" if head != n else ""))
            meta = []
            if v.get("aliases"):
                meta.append("别名：" + "、".join(v["aliases"]))
            if v.get("path"):
                meta.append(f"路径：`{v['path']}`")
            if v.get("updated"):
                meta.append("更新：" + v["updated"][:10])
            if meta:
                L.append("- " + " ｜ ".join(meta))
            if v.get("oneliner"):
                L.append(f"- 一句话：{v['oneliner']}")
            cs = byp.get(n, [])
            if cs:
                L.append("- 要点：")
                for c in cs:
                    L.append(f"  - {c['text']}" + (f"（{c['note']}）" if c.get("note") else ""))
            L.append("")
    path = PROJECT_TABLE if os.path.isdir(os.path.dirname(PROJECT_TABLE)) else os.path.join(MEM_DIR, "项目总表.md")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"   项目总表：{path}（{len(names)} 个项目）")
    _write_project_table_html(projs, byp, cards)


_CSS = """
*{box-sizing:border-box}
:root{--paper:#F3EDE2;--paper2:#FCFAF4;--ink:#221F1A;--ink2:#6B6459;--rule:#DFD7C8;--cz:#B03A2E;--jade:#2F6B5B}
body{margin:0;background:var(--paper);color:var(--ink);
  font:15px/1.7 -apple-system,"Segoe UI",system-ui,"PingFang SC","Microsoft YaHei",sans-serif;
  background-image:radial-gradient(120% 90% at 8% -10%,rgba(176,58,46,.05),transparent 60%),repeating-linear-gradient(90deg,rgba(0,0,0,.016) 0 1px,transparent 1px 3px)}
.wrap{max-width:1140px;margin:0 auto;padding:54px 28px 96px}
header{border-bottom:1px solid var(--rule);padding-bottom:20px;margin-bottom:8px}
h1::after{content:'';display:block;width:68px;height:3px;background:var(--cz);margin-top:13px}
h1{font-family:"Songti SC","Source Han Serif SC",SimSun,serif;font-size:clamp(26px,4vw,38px);
  letter-spacing:.06em;margin:0 0 6px}
.meta{color:var(--ink2);font-size:13.5px;letter-spacing:.02em;line-height:1.9}
.meta b{color:var(--cz);font-weight:600}
.toolbar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:22px 0 6px}
#q{flex:1 1 280px;min-width:220px;padding:11px 14px;border:1px solid var(--rule);background:var(--paper2);
  font:inherit;color:inherit;border-radius:2px;outline:none}
#q:focus{border-color:var(--cz);box-shadow:0 0 0 3px rgba(176,58,46,.08)}
.hint{color:var(--ink2);font-size:13px}
section{margin-top:48px}
.sthead{display:flex;align-items:baseline;gap:12px;border-bottom:1px solid var(--rule);padding-bottom:6px}
.sthead h2{font-family:"Songti SC",SimSun,serif;font-size:19px;letter-spacing:.08em;margin:0;font-weight:600}
.sthead h2::before{content:'';display:inline-block;width:9px;height:9px;background:var(--cz);margin-right:10px;vertical-align:2px}
.cnt{color:var(--cz);font-size:13px;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:22px;margin-top:20px;align-items:start}
.proj{background:var(--paper2);border:1px solid var(--rule);border-top:2px solid var(--ink);padding:20px 22px 18px}
.proj.done{border-top-color:var(--jade);opacity:.9}
.proj.paused{border-top-style:dashed;border-top-color:var(--ink2)}
.proj h3{font-family:"Songti SC",SimSun,serif;font-size:17.5px;margin:0 0 4px;letter-spacing:.03em}
.proj .code{font-size:12.6px;color:var(--ink2);font-family:ui-monospace,Menlo,Consolas,monospace;letter-spacing:.02em}
.aliases{margin:8px 0 10px;display:flex;flex-wrap:wrap;gap:6px}
.aliases span{font-size:12.8px;color:var(--ink2);border-bottom:1px dotted rgba(176,58,46,.5);padding-bottom:1px;line-height:1.6}
.one{margin:0 0 11px;font-size:14.5px;line-height:1.75}
.rows{font-size:13.6px;color:var(--ink2);line-height:2.05;border-top:1px dotted var(--rule);padding-top:9px;margin-top:2px}
.rows code{font-family:ui-monospace,Menlo,Consolas,monospace;color:var(--ink);background:rgba(0,0,0,.035);padding:1px 5px}
ul.pts{margin:11px 0 0;padding-left:1.2em}
ul.pts li{margin:6px 0;font-size:14px;line-height:1.8}
ul.pts li::marker{color:var(--cz)}
.ice{margin-top:34px;border:1px dashed var(--rule);padding:16px 18px;background:rgba(255,255,255,.35)}
.ice h2{font-family:"Songti SC",SimSun,serif;font-size:17px;margin:0 0 4px;letter-spacing:.06em}
.ice p{margin:2px 0 10px;color:var(--ink2);font-size:12.5px}
.ice li{margin:5px 0;font-size:13.5px}
.ice .why{color:var(--ink2);font-size:12.5px}
footer{margin-top:46px;color:var(--ink2);font-size:12px;border-top:1px solid var(--rule);padding-top:12px}
mark{background:rgba(176,58,46,.16);color:inherit}
@media print{body{background:#fff}#q{display:none}.proj{break-inside:avoid}}
"""

_JS = """
const q=document.getElementById('q');
const projs=[...document.querySelectorAll('.proj')];
q.addEventListener('input',()=>{
  const v=q.value.trim().toLowerCase();
  projs.forEach(el=>{el.style.display=(!v||el.dataset.search.includes(v))?'':'none';});
  document.querySelectorAll('section[data-sec]').forEach(s=>{
    const n=[...s.querySelectorAll('.proj')].filter(e=>e.style.display!=='none').length;
    s.querySelector('.cnt').textContent=n;
    s.style.display=n?'':'none';
  });
});
"""


def _write_project_table_html(projs, byp, cards):
    """生成 HTML 版项目总表（老闫 2026-09-11：md 看着眼累）——纸墨朱砂配色 + 实时搜索"""
    names = sorted(set(byp.keys()) | set(projs.keys()))
    if not names:
        return
    E = html.escape

    def st(n):
        return (projs.get(n) or {}).get("status") or (byp.get(n, [{}])[0].get("status") or "active")

    def blob(n):
        v = projs.get(n) or {}
        parts = [n, v.get("title", ""), v.get("oneliner", ""), v.get("path", ""),
                 " ".join(v.get("aliases", []))]
        parts += [c["text"] + c.get("note", "") for c in byp.get(n, [])]
        return E(" ".join(parts).lower()).replace('"', "&quot;")

    P = []
    for status, title in (("active", "🟢 进行中"), ("paused", "⏸ 搁置"), ("done", "✅ 已完成")):
        group = [n for n in names if st(n) == status]
        if not group:
            continue
        P.append(f'<section data-sec><div class="sthead"><h2>{title}</h2>'
                 f'<span class="cnt">{len(group)}</span></div><div class="grid">')
        for n in group:
            v = projs.get(n) or {}
            head = E(v.get("title") or n)
            P.append(f'<article class="proj {status}" data-search="{blob(n)}">')
            P.append(f'<h3>{head}</h3><div class="code">{E(n)}</div>')
            if v.get("aliases"):
                P.append('<div class="aliases">' + "".join(f"<span>{E(x)}</span>" for x in v["aliases"]) + "</div>")
            if v.get("oneliner"):
                P.append(f'<p class="one">{E(v["oneliner"])}</p>')
            rows = []
            if v.get("path"):
                rows.append("路径 <code>" + E(v["path"]) + "</code>")
            if v.get("updated"):
                rows.append("更新 " + E(v["updated"][:10]))
            if rows:
                P.append('<div class="rows">' + "　·　".join(rows) + "</div>")
            cs = byp.get(n, [])
            if cs:
                P.append('<ul class="pts">' + "".join(
                    f"<li>{E(c['text'])}" + (f"<br><span class=\"code\">{E(c['note'])}</span>" if c.get("note") else "")
                    + "</li>" for c in cs) + "</ul>")
            P.append("</article>")
        P.append("</div></section>")

    ice = [c for c in cards if c["layer"] == "L6"]
    if ice:
        P.append('<div class="ice"><h2>🧊 冷藏层（先放放的）</h2>'
                 '<p>铁律：先查上面的项目总表 → 再查 L1–L5 → 都找不到才翻这里。</p><ul>')
        for c in ice:
            P.append(f"<li>{E(c['text'])}<br><span class='why'>放放的理由：{E(c.get('note',''))}</span></li>")
        P.append("</ul></div>")

    n_active = len([n for n in names if st(n) == "active"])
    doc = ("<!doctype html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
           "<title>项目总表 · 阿衍</title>\n<style>" + _CSS + "</style>\n</head>\n<body>\n<div class=\"wrap\">\n"
           "<header><h1>项目总表</h1><div class=\"meta\">共 <b>" + str(len(names)) + "</b> 个项目　·　进行中 <b>"
           + str(n_active) + "</b>　·　生成于 " + now_iso() + "　·　阿衍维护<code>memory.py build</code>自动生成，勿手改</div></header>\n"
           "<div class=\"toolbar\"><input id=\"q\" type=\"search\" placeholder=\"搜项目名 / 别名 / 路径 / 要点…（如：协作、教师节、蓝图）\" autofocus>"
           "<span class=\"hint\">不用 Ctrl+F，直接打字过滤</span></div>\n"
           + "\n".join(P)
           + "\n<footer>数据源 <code>~/.agents/memory/cards.json</code>　·　L2 项目卡 + 项目元信息　·　<a href='项目总表.md'>同目录还有 md 版</a></footer>\n"
           "</div>\n<script>" + _JS + "</script>\n</body>\n</html>\n")
    path = PROJECT_TABLE_HTML if os.path.isdir(os.path.dirname(PROJECT_TABLE_HTML)) else os.path.join(MEM_DIR, "项目总表.html")
    open(path, "w", encoding="utf-8").write(doc)
    print(f"   项目总表(HTML)：{path}")


def _bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)}


def cmd_doctor(a):
    data = load()
    bad = {"超长": [], "缺场景": [], "指代词": [], "重复": [], "疑似重复": [], "缺字段": [], "无标签": []}
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
    # 疑似重复：同层、同场景/项目，且文本二元组相似度 ≥0.5（抓“同一件事写两遍”）
    cs = data["cards"]
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            x, y = cs[i], cs[j]
            if x["layer"] != y["layer"]:
                continue
            if x.get("scene", "") != y.get("scene", "") or x.get("project", "") != y.get("project", ""):
                continue
            bx, by = _bigrams(norm(x["text"])), _bigrams(norm(y["text"]))
            if not bx or not by:
                continue
            if _sim(x["text"], y["text"]) >= 0.35:
                bad["疑似重复"].append(f"{x['id']}≈{y['id']}")
    print(f"🩺 体检：{len(data['cards'])} 张卡片" + (f" ｜ BOOT {tk} tokens" if tk else " ｜ BOOT 未生成"))
    for k, v in bad.items():
        if v:
            print(f"  ⚠️ {k}（{len(v)}）: " + ", ".join(str(x) for x in v[:8]) + (" …" if len(v) > 8 else ""))
    sev = sum(len(v) for k, v in bad.items() if k in ("超长", "缺场景", "重复", "缺字段"))
    print(("✅ 无严重问题" if sev == 0 else f"❗ {sev} 个严重问题待处理"))
    return 0


def cmd_stats(a):
    from collections import Counter
    data = load()
    print(f"卡片库: {CARDS_FILE}")
    print("  按层:", dict(Counter(c["layer"] for c in data["cards"])))
    print("  按场景:", dict(Counter(c["scene"] for c in data["cards"] if c["scene"])))
    print(f"  项目: {len(data.get('projects', {}))} 个")
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
    s = sub.add_parser("icebox"); s.set_defaults(fn=cmd_icebox)
    s = sub.add_parser("show"); s.add_argument("id"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("rm"); s.add_argument("id"); s.set_defaults(fn=cmd_rm)
    s = sub.add_parser("use"); s.add_argument("id"); s.set_defaults(fn=cmd_use)
    s = sub.add_parser("build"); s.add_argument("--scene", default=None); s.add_argument("--budget", type=int, default=DEFAULT_BUDGET); s.set_defaults(fn=cmd_build)
    s = sub.add_parser("proj"); s.add_argument("action", choices=("set", "list", "show", "find", "rm")); s.add_argument("name", nargs="?", default="")
    s.add_argument("--title", default=""); s.add_argument("--oneliner", default=""); s.add_argument("--alias", default=""); s.add_argument("--path", default=""); s.add_argument("--status", choices=STATUSES, default=""); s.set_defaults(fn=cmd_proj)
    s = sub.add_parser("doctor"); s.set_defaults(fn=cmd_doctor)
    s = sub.add_parser("stats"); s.set_defaults(fn=cmd_stats)

    a = p.parse_args(argv)
    if not hasattr(a, "fn"):
        p.print_help()
        return 1
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
