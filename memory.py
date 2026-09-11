#!/usr/bin/env python3
"""pi 永久记忆工具：facts(事实) / patterns(模式) / lessons(经验) / sessions(会话) 四层记忆。

零依赖（Python 标准库），数据存于 ~/.agents/memory/。

用法:
  memory.py init                                   # 初始化空记忆库
  memory.py add <type> <内容> [--tag a,b]          # 添加记忆, type: fact|pattern|lesson
  memory.py session-save <摘要> [--key a,b]        # 保存会话摘要
  memory.py search <关键词>                        # 全文搜索所有记忆
  memory.py list [type]                            # 列出（默认全部）
  memory.py get <id>                               # 查看单条
  memory.py update <id> <新内容> [--tag a,b]       # 更新
  memory.py delete <id>                            # 删除
  memory.py stats                                  # 统计概览
  memory.py sync                                   # 重新生成 MEMORY.md 总览

记忆机制 v2（分层卡片，见 /mnt/d/Pi/projects/agent-memory/DESIGN.md）：
  memory.py card add --layer L1 --scene writing --text "..."   # 新增卡片
  memory.py card list|search|show|edit|rm|use ...              # 卡片读写
  memory.py build [--scene writing] [--budget 3500]            # 生成 BOOT.md 与正文镜像
  memory.py doctor                                             # 体检
  memory.py icebox                                             # 列出冷藏层（先放放的事）
  （旧四层 memory.json 保持不变；卡片存于 cards.json）
"""
import argparse
import contextlib
import json
import os
import sys
import time
from datetime import datetime, timezone

try:
    import fcntl as _fcntl
    _HAVE_LOCK = True
except ImportError:  # 非 POSIX(如 Windows)退化为无锁
    _HAVE_LOCK = False

MEM_DIR = os.path.expanduser("~/.agents/memory")
DATA_FILE = os.path.join(MEM_DIR, "memory.json")
MD_FILE = os.path.join(MEM_DIR, "MEMORY.md")

TYPES = ("fact", "pattern", "lesson")
ALL_TYPES = TYPES + ("session",)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load():
    if not os.path.exists(DATA_FILE):
        return {"version": 1, "facts": [], "patterns": [], "lessons": [], "sessions": []}
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save(data):
    os.makedirs(MEM_DIR, exist_ok=True)
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


@contextlib.contextmanager
def _file_lock():
    """跨进程互斥锁: 锁独立 .lock 文件(不随 memory.json 被 replace 换 inode)"""
    if not _HAVE_LOCK:
        yield
        return
    os.makedirs(MEM_DIR, exist_ok=True)
    lf = open(os.path.join(MEM_DIR, ".lock"), "w")
    try:
        _fcntl.flock(lf, _fcntl.LOCK_EX)
        yield
    finally:
        _fcntl.flock(lf, _fcntl.LOCK_UN)
        lf.close()


def mutate(op):
    """读-改-写 整体持锁: 并发 add/update/delete 不再互相覆盖或写坏"""
    with _file_lock():
        data = load()
        out = op(data)
        save(data)
    return out


def gen_id(prefix, data):
    keys = [x["id"] for t in ALL_TYPES for x in data.get(t + "s", [])]
    nums = [int(k[len(prefix):]) for k in keys if k.startswith(prefix) and k[len(prefix):].isdigit()]
    return f"{prefix}{max(nums) + 1 if nums else 1}"


def normalize(s):
    return "".join(ch.lower() for ch in s if not ch.isspace())


def find_duplicate(data, kind, content):
    """近似去重：normalize 后相同或互为子串视为重复。"""
    nc = normalize(content)
    items = data.get(kind + "s", [])
    for it in items:
        n = normalize(it["content"])
        if nc and (nc == n or nc in n or n in nc):
            return it
    return None


def add(args):
    kind = args.type
    if kind not in TYPES:
        print(f"❌ 类型必须是 {'/'.join(TYPES)}")
        sys.exit(1)

    def _op(data):
        dup = find_duplicate(data, kind, args.content)
        if dup:
            return ("dup", dup)
        key = kind + "s"
        rec = {
            "id": gen_id(kind[0], data),
            "content": args.content,
            "tags": [t.strip() for t in args.tag.split(",")] if args.tag else [],
            "ts": now_iso(),
        }
        data[key].append(rec)
        return ("ok", rec)

    res = mutate(_op)
    if res[0] == "dup":
        dup = res[1]
        print(f"⚠️ 已有相似条目（{dup['id']}）: {dup['content'][:60]}")
        print("未重复添加。如确需更新请用 update 或 delete 后重加。")
    else:
        rec = res[1]
        print(f"✅ 已保存 {kind}: {rec['id']}")
        print(f"   {args.content[:80]}")


def session_save(args):
    def _op(data):
        rec = {
            "id": gen_id("s", data),
            "date": now_iso(),
            "summary": args.content,
            "keys": [k.strip() for k in args.key.split(",")] if args.key else [],
        }
        data["sessions"].append(rec)
        return rec

    rec = mutate(_op)
    print(f"✅ 已保存会话摘要: {rec['id']}")
    print(f"   {args.content[:80]}")


def search(args):
    data = load()
    q = normalize(args.query)
    if not q:
        print("❌ 请输入关键词")
        sys.exit(1)
    hits = []
    for t in ALL_TYPES:
        for it in data.get(t + "s", []):
            blob = normalize(it.get("content", "") + " " + " ".join(it.get("tags", it.get("keys", []))))
            if q in blob:
                hits.append((t, it))
    if not hits:
        print("🔍 未找到匹配记忆。")
        return
    for t, it in hits:
        extra = ""
        if t == "session":
            extra = f"  [{it.get('date', '')[:10]}]"
        else:
            extra = f"  [{it.get('ts', '')[:10]}]"
        print(f"· ({t}) {it['id']}{extra}: {it.get('content', it.get('summary', ''))[:100]}")
    print(f"\n共 {len(hits)} 条匹配。")


def list_items(args):
    data = load()
    types = [args.type] if args.type in ALL_TYPES else ALL_TYPES
    total = 0
    for t in types:
        items = data.get(t + "s", [])
        if not items:
            continue
        print(f"\n== {t}s ({len(items)}) ==")
        for it in items:
            if t == "session":
                print(f"  {it['id']} [{it.get('date', '')[:10]}]: {it.get('summary', '')[:80]}")
            else:
                tag = (" #" + ",".join(it.get("tags", []))) if it.get("tags") else ""
                print(f"  {it['id']} [{it.get('ts', '')[:10]}]{tag}: {it.get('content', '')[:80]}")
        total += len(items)
    print(f"\n共 {total} 条记忆。")


def get_item(args):
    data = load()
    for t in ALL_TYPES:
        for it in data.get(t + "s", []):
            if it["id"] == args.id:
                print(json.dumps(it, ensure_ascii=False, indent=2))
                return
    print(f"❌ 未找到 {args.id}")


def update_item(args):
    def _op(data):
        for t in ALL_TYPES:
            for it in data.get(t + "s", []):
                if it["id"] == args.id:
                    it["content"] = args.content
                    if args.tag and t != "session":
                        it["tags"] = [x.strip() for x in args.tag.split(",")]
                    it["ts"] = now_iso()
                    return True
        return False

    if mutate(_op):
        print(f"✅ 已更新 {args.id}")
    else:
        print(f"❌ 未找到 {args.id}")


def delete_item(args):
    def _op(data):
        for t in ALL_TYPES:
            items = data.get(t + "s", [])
            for i, it in enumerate(items):
                if it["id"] == args.id:
                    del items[i]
                    return True
        return False

    if mutate(_op):
        print(f"🗑️ 已删除 {args.id}")
    else:
        print(f"❌ 未找到 {args.id}")


def stats(args):
    data = load()
    print(f"记忆库: {DATA_FILE}")
    for t in ALL_TYPES:
        print(f"  {t}s: {len(data.get(t + 's', []))}")
    total = sum(len(data.get(t + "s", [])) for t in ALL_TYPES)
    print(f"总计: {total} 条")
    return data


def sync(args=None):
    data = load()
    lines = []
    lines.append("# 🧠 永久记忆总览（MEMORY.md）")
    lines.append("")
    lines.append(f"> 自动生成于 {now_iso()} · 由 memory 技能维护 · 勿手改此文件头部")
    lines.append("")
    for t, title, icon in (
        ("fact", "实体事实", "📌"),
        ("pattern", "行为模式", "🔁"),
        ("lesson", "经验教训", "💡"),
    ):
        items = data.get(t + "s", [])
        lines.append(f"## {icon} {title}（{len(items)}）")
        lines.append("")
        if not items:
            lines.append("_暂无_")
        else:
            for it in items[-15:]:
                tag = (" `#" + "` `#".join(it.get("tags", [])) + "`") if it.get("tags") else ""
                lines.append(f"- {it['content']}{tag}")
        lines.append("")
    s = data.get("sessions", [])
    lines.append(f"## 🗂️ 会话记录（{len(s)}）")
    lines.append("")
    if not s:
        lines.append("_暂无_")
    else:
        for it in s[-8:]:
            lines.append(f"- **{it.get('date', '')[:10]}** {it.get('summary', '')[:90]}")
    lines.append("")
    os.makedirs(MEM_DIR, exist_ok=True)
    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ 已生成总览: {MD_FILE}")
    print(f"   总记忆 {sum(len(data.get(t + 's', [])) for t in ALL_TYPES)} 条")


def init(args=None):
    if os.path.exists(DATA_FILE):
        print("⚠️ 记忆库已存在，跳过初始化。")
        return
    save(load())
    sync()
    print("✅ 记忆库初始化完成。")


def main():
    # —— 记忆 v2 转发：分层卡片工具 cards.py（memory.py 本体逻辑不动）
    if len(sys.argv) > 1 and sys.argv[1] in ("card", "proj", "build", "doctor", "icebox"):
        import cards
        return cards.main(sys.argv[2:] if sys.argv[1] == "card" else sys.argv[1:])

    p = argparse.ArgumentParser(description="pi 永久记忆工具")
    sub = p.add_subparsers(dest="cmd")

    a_init = sub.add_parser("init")
    a_init.set_defaults(fn=init)

    a_add = sub.add_parser("add")
    a_add.add_argument("type", choices=TYPES)
    a_add.add_argument("content")
    a_add.add_argument("--tag", default="")
    a_add.set_defaults(fn=add)

    a_ss = sub.add_parser("session-save")
    a_ss.add_argument("content")
    a_ss.add_argument("--key", default="")
    a_ss.set_defaults(fn=session_save)

    a_se = sub.add_parser("search")
    a_se.add_argument("query")
    a_se.set_defaults(fn=search)

    a_li = sub.add_parser("list")
    a_li.add_argument("type", nargs="?", default="")
    a_li.set_defaults(fn=list_items)

    a_ge = sub.add_parser("get")
    a_ge.add_argument("id")
    a_ge.set_defaults(fn=get_item)

    a_up = sub.add_parser("update")
    a_up.add_argument("id")
    a_up.add_argument("content")
    a_up.add_argument("--tag", default="")
    a_up.set_defaults(fn=update_item)

    a_de = sub.add_parser("delete")
    a_de.add_argument("id")
    a_de.set_defaults(fn=delete_item)

    a_st = sub.add_parser("stats")
    a_st.set_defaults(fn=stats)

    a_sy = sub.add_parser("sync")
    a_sy.set_defaults(fn=sync)

    args = p.parse_args()
    if not hasattr(args, "fn"):
        p.print_help()
        sys.exit(1)
    args.fn(args)


if __name__ == "__main__":
    main()
