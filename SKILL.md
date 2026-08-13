---
name: pi-memory-evo
version: 0.1.0
description: >-
  ALWAYS ACTIVE 永久记忆与自进化技能（pi 原生，零依赖）：
  会话中主动保存用户偏好/项目决策/重要事实（fact）、反复出现的行为规律（pattern）、排坑经验（lesson），
  会话结束时自动沉淀摘要（session）并"经验路由"——可操作的方法论升级为技能或写入记忆库。
  新会话启动时先读 ~/.agents/memory/MEMORY.md 了解用户背景，实现跨会话连续记忆。
  工具：~/.agents/skills/pi-memory-evo/memory.py（add / search / session-save / stats / sync）。
  触发词：记住、记一下、别忘了、永久记忆、长期记忆、我的偏好、上次我们、我们之前、回顾、总结会话、沉淀、自进化、经验教训、记忆、memory、remember、save this、教训、排坑。
requires: python3>=3.8
---

# 永久记忆与自进化（memory）

> **核心原则：主动保存，不等用户要求。** 把用户环境变成"越用越懂你"的系统：
> 三层粒度记忆（事实/模式/经验）+ 会话摘要 + 经验路由（自进化）。

## 🚀 会话启动（每次新会话）

1. 若存在 `~/.agents/memory/MEMORY.md`，**先读取**，快速了解用户背景、偏好与近期会话。
2. 需要细节时用 `memory.py get <id>` 或 `memory.py search <关键词>` 深挖。
3. 向用户展示已记住的关键信息（简要），体现连续性。

## 📌 主动保存（ALWAYS ACTIVE，遇到即存，不要等会话结束）

出现以下情况时，**立即**调用 `memory.py add <type> <内容>` 保存：

| 类型 | 保存时机 | 示例 |
|------|----------|------|
| `fact` | 用户透露偏好/习惯/身份信息；项目重要决策、技术选型、约定；用户明确说"记住" | "用户偏好中文回复" "项目用 pnpm + TypeScript" |
| `pattern` | 同一行为/问题**出现 2 次以上**（含本次） | "每次装技能用户都要求先评估依赖" |
| `lesson` | 踩坑后学到的经验、排障结论、发现的坑 | "DuckDuckGo 的 ddgs 默认后端会走 Yandex 超时，须用 backend='html'" |

- 保存可附 `--tag a,b` 便于检索。
- 工具会自动**近似去重**，重复内容会提示而非重复存储。

## 🗂️ 会话结束（或用户要求"总结会话/沉淀"）

按序执行：

1. 回顾本次会话，提取 **2~5 条** 最重要的信息。
2. **归类保存**：`fact`（新偏好/决策）→ `pattern`（新规律）→ `lesson`（新经验）。
3. **经验路由（自进化）**：对每条 lesson 判断：
   - 属于**可复用方法论**（如"某类任务的标准流程"）→ 新建或更新 `~/.agents/skills/` 下的技能（用 write/edit 工具），让下次自动生效；
   - 属于**一次性事实** → 存 fact；
   - 属于**环境/账号专属**（如某工具需配置）→ 存 lesson 即可。
4. 用 `memory.py session-save "<本次会话一句话摘要>" --key 关键词1,关键词2` 保存会话记录。
5. 运行 `memory.py sync` 刷新 MEMORY.md 总览。

## 🔍 查询记忆

用户问"我之前说过/我们上次/我的偏好"之类 → `memory.py search <关键词>`；列全部 → `memory.py list`。

## ⚙️ 工具速查

```bash
P=~/.agents/skills/pi-memory-evo/memory.py
$P init                       # 首次初始化
$P add fact "内容" --tag 偏好    # 存事实/模式/经验
$P session-save "摘要" --key a  # 存会话摘要
$P search 关键词                # 搜索
$P list                        # 全部列出
$P get <id> / update <id> <新内容> / delete <id>   # 管理
$P stats                       # 统计
$P sync                        # 刷新总览 MEMORY.md
```

## 📂 存储位置

- 数据：`~/.agents/memory/memory.json`（四层记忆，JSON）
- 总览：`~/.agents/memory/MEMORY.md`（会话启动时读这个）
- 技能本体：`~/.agents/skills/pi-memory-evo/`（工具 + 本说明）

## ⚠️ 边界

- **不存敏感凭据**：token、密码、密钥一律不保存。
- **尊重用户意愿**：用户说"这个别记"则不存；说"忘掉 X"则 `delete` 对应条目。
- 记忆是辅助，不替代确认：涉及重要操作仍以用户当前意图为准。
