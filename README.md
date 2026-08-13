<div align="center">

# 🧠 pi-memory-evo

**永久记忆 + 自进化技能 · 为 pi 编码助手打造**
**Persistent Memory & Self-Evolving Skill for the pi coding agent**

零依赖 · 主动保存 · 三层粒度 · 经验路由
Zero-dependency · Always-Active · 3-layer memory · Lesson routing

</div>

---

## 🇨🇳 简介

`pi-memory-evo` 是一个 **pi 原生**的永久记忆与自进化技能，把"越用越懂你"变成现实：

- **🧠 永久记忆**：跨会话记住用户偏好、项目决策、重要事实（`fact`）、行为规律（`pattern`）、排坑经验（`lesson`）
- **⚡ 主动保存（ALWAYS ACTIVE）**：会话中遇到值得记住的信息立即保存，不等用户要求
- **🗂️ 会话摘要**：每次会话结束自动沉淀摘要（`session`），新会话启动时读取总览，实现连续对话
- **🔧 自进化（经验路由）**：从会话中提取教训，可复用的方法论自动升级为技能或写入记忆库，让 agent 越来越强
- **🌱 零依赖**：纯 Python 标准库实现，无 API key、无外部服务、无数据库

## 🇬🇧 Overview (EN)

`pi-memory-evo` is a **pi-native** persistent memory & self-evolving skill:

- **🧠 Persistent memory** across sessions: user preferences, project decisions, facts, recurring patterns, and hard-won lessons
- **⚡ Always-active capture**: saves important information immediately during conversation — no need to ask
- **🗂️ Session summaries**: auto-distills each session; the next session starts with context restored
- **🔧 Self-evolution via lesson routing**: actionable lessons become new skills or knowledge entries automatically
- **🌱 Zero dependencies**: pure Python standard library — no API keys, no external services, no databases

---

## 🚀 快速开始 / Quick Start

```bash
# 1. 安装技能到 pi 的技能目录
mkdir -p ~/.agents/skills/pi-memory-evo
# 将本仓库的 memory.py 与 SKILL.md 放入该目录

# 2. 初始化记忆库（首次）
~/.agents/skills/pi-memory-evo/memory.py init

# 3. 使用
~/.agents/skills/pi-memory-evo/memory.py add fact "用户偏好中文回复" --tag 偏好
~/.agents/skills/pi-memory-evo/memory.py search 偏好
```

## 📐 架构 / Architecture

```
┌─────────────────────────────────────────────────┐
│  SKILL.md（指令层 / Instruction layer）          │
│  · ALWAYS ACTIVE 主动保存                        │
│  · 三层粒度：fact / pattern / lesson            │
│  · 会话结束：摘要 + 经验路由（自进化）            │
├─────────────────────────────────────────────────┤
│  memory.py（工具层 / Tool layer）                │
│  · add / search / list / get / update / delete  │
│  · session-save / stats / sync                  │
│  · 近似去重 · 原子写入 · 时间戳                   │
├─────────────────────────────────────────────────┤
│  ~/.agents/memory/（数据层 / Data layer）        │
│  · memory.json（四层记忆 / 4-layer store）       │
│  · MEMORY.md（总览，新会话先读 / overview）      │
└─────────────────────────────────────────────────┘
```

## 🛠️ 命令参考 / Commands

```bash
P=~/.agents/skills/pi-memory-evo/memory.py

$P init                        # 初始化记忆库 / init store
$P add fact   "内容" --tag a,b  # 事实 / facts
$P add pattern "内容" --tag a,b # 行为模式（≥2次）/ patterns (≥2 occurrences)
$P add lesson "内容" --tag a,b  # 经验教训 / lessons
$P session-save "摘要" --key k  # 会话摘要 / session summary
$P search 关键词                 # 全文搜索 / full-text search
$P list [type]                  # 列出 / list (fact|pattern|lesson|session)
$P get <id>                     # 查看单条 / view one
$P update <id> <新内容>          # 更新 / update
$P delete <id>                  # 删除 / delete
$P stats                        # 统计 / stats
$P sync                         # 刷新总览 MEMORY.md / refresh overview
```

## 📂 数据位置 / Data Locations

| 内容 | 路径 |
|------|------|
| 技能本体 / Skill | `~/.agents/skills/pi-memory-evo/` |
| 记忆数据 / Memory data | `~/.agents/memory/memory.json` |
| 记忆总览 / Overview | `~/.agents/memory/MEMORY.md` |

> 数据目录与技能目录分离：升级技能不会丢失记忆。

## ⚠️ 边界 / Boundaries

- **不存敏感凭据**（token / 密码 / 密钥）—— Never store credentials
- **尊重用户意愿**："这个别记"则不存，"忘掉 X"则删除
- 记忆是辅助，不替代确认—— Memory assists, never overrides current intent

## 📄 License

MIT
