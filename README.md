<div align="center">

# 🧠 pi-memory-facts

**永久记忆 + 自进化技能 · 为 pi 编码助手打造**
**Persistent Memory & Self-Evolving Skill for the pi coding agent**

零依赖 · 主动保存 · 三层粒度 · 经验路由
Zero-dependency · Always-Active · 3-layer memory · Lesson routing

> **名字即宣言 FACTS：** F=Frugal 速进场（省 token）｜ A=Accurate 存取一致（零上下文读回不走样）｜ C=Card 卡式（按场景建卡索引）｜ T=Trusted 可信度分级（★✓~?）｜ S=Self-evolving 任务卡自进化（坑表回写）

</div>

---

## 🇨🇳 简介

`pi-memory-facts` 是一个 **pi 原生**的永久记忆与自进化技能，把"越用越懂你"变成现实。

**名字即宣言，FACTS 五个字母是这套记忆系统的五根柱子：**

- **F = Frugal（速进场）**：开场只装 BOOT.md 预算包（≤3500 tokens），是目录不是正文；只读 to-do，done 的不读，冷藏层永不进场——最大限度省 token
- **A = Accurate（存取一致）**：首次精准化写入（判据＝零上下文读回来不走样）＋后期纠偏，避免模糊混淆
- **C = Card（卡式）**：按触发场景/项目/skills 建卡索引，检索＝匹配当前动作，不搞一锅粥
- **T = Trusted（可信度分级）**：每条记忆带验证等级（★human / ✓tested / ~review / ?self），猜测不伪装成事实
- **S = Self-evolving（任务卡自进化）**：端到端 SOP＋坑表，做完必回写，同类错误不重犯

除此之外：

- **🧠 永久记忆**：跨会话记住用户偏好、项目决策、重要事实（`fact`）、行为规律（`pattern`）、排坑经验（`lesson`）
- **⚡ 主动保存（ALWAYS ACTIVE）**：会话中遇到值得记住的信息立即保存，不等用户要求
- **🗂️ 会话摘要**：每次会话结束自动沉淀摘要（`session`），新会话启动时读取总览，实现连续对话
- **🔧 自进化（经验路由）**：从会话中提取教训，可复用的方法论自动升级为技能或写入记忆库，让 agent 越来越强
- **🌱 零依赖**：纯 Python 标准库实现，无 API key、无外部服务、无数据库

## 🇬🇧 Overview (EN)

`pi-memory-facts` is a **pi-native** persistent memory & self-evolving skill:

- **🧠 Persistent memory** across sessions: user preferences, project decisions, facts, recurring patterns, and hard-won lessons
- **⚡ Always-active capture**: saves important information immediately during conversation — no need to ask
- **🗂️ Session summaries**: auto-distills each session; the next session starts with context restored
- **🔧 Self-evolution via lesson routing**: actionable lessons become new skills or knowledge entries automatically
- **🌱 Zero dependencies**: pure Python standard library — no API keys, no external services, no databases

---

## 🚀 快速开始 / Quick Start

### 安装方式 1：一行命令（推荐，给 pi-Agent 自动安装）

复制下面这条命令给你的 pi-Agent，它会自动把技能装进 pi 的全局技能目录 `~/.pi/agent/skills/`，重启 pi 即生效：

```bash
npx skills add dancepower22/pi-memory-facts -g -a pi
```

> 注意：`npx skills` 装的是**静态副本**（无 .git）。如果技能仓库更新了，需要重新执行该命令获取新版。

### 安装方式 2：git clone（手动，同样生效）

```bash
git clone --depth=1 https://github.com/dancepower22/pi-memory-facts.git ~/.agents/skills/pi-memory-facts
```

### 安装方式 3：手动放置

把本仓库的 `SKILL.md`、`memory.py`、`cards.py` 放入 `~/.agents/skills/pi-memory-facts/` 即可（pi 会自动发现带非空 description 的 SKILL.md）。

### 安装后（任选一种安装方式都接着做）

```bash
# 1. 初始化记忆库（首次）
~/.agents/skills/pi-memory-facts/memory.py init

# 2. 使用
~/.agents/skills/pi-memory-facts/memory.py add fact "用户偏好中文回复" --tag 偏好
~/.agents/skills/pi-memory-facts/memory.py search 偏好
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
P=~/.agents/skills/pi-memory-facts/memory.py

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
| 技能本体 / Skill | `~/.agents/skills/pi-memory-facts/` |
| 记忆数据 / Memory data | `~/.agents/memory/memory.json` |
| 记忆总览 / Overview | `~/.agents/memory/MEMORY.md` |

> 数据目录与技能目录分离：升级技能不会丢失记忆。

## ⚠️ 边界 / Boundaries

- **不存敏感凭据**（token / 密码 / 密钥）—— Never store credentials
- **尊重用户意愿**："这个别记"则不存，"忘掉 X"则删除
- 记忆是辅助，不替代确认—— Memory assists, never overrides current intent

## 📄 License

MIT
