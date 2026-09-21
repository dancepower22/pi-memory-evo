---
name: pi-memory-facts
version: 0.2.0
description: >-
  ALWAYS ACTIVE 永久记忆与自进化技能（pi 原生，零依赖），名字即宣言：FACTS。
  F=Frugal 速进场：开场只装 BOOT.md 预算包（≤3500 tokens），是目录不是正文；
  只读 OPEN_LOOPS（to-do），done 的不读，冷藏层（L6）永不进场——最大限度省 token。
  A=Accurate 存取一致：首次精准化写入（判据=零上下文读回来不走样）+ 后期纠偏，避免模糊混淆。
  C=Card 卡式：按触发场景/项目/skills 建卡索引（L1-L5），检索=匹配当前动作，不搞一锅粥。
  T=Trusted 可信度分级：每条记忆带验证等级（★human / ✓tested / ~review / ?self），
  猜测不伪装成事实，"我知道我不知道"。
  S=Self-evolving 任务卡自进化：端到端 SOP+坑表，做完必回写，同类错误不重犯。
  工具：~/.agents/skills/pi-memory-facts/memory.py（add / search / session-save / stats / sync / card / proj / icebox / doctor）。
  触发词：记住、记一下、别忘了、永久记忆、长期记忆、我的偏好、上次我们、我们之前、回顾、总结会话、沉淀、自进化、经验教训、记忆、memory、remember、save this、教训、排坑。
requires: python3>=3.8
---

# 永久记忆与自进化（memory）

> **核心原则：主动保存，不等用户要求。** 把用户环境变成"越用越懂你"的系统：
> 三层粒度记忆（事实/模式/经验）+ 会话摘要 + 经验路由（自进化）。

## 🚀 会话启动（每次新会话）

1. 若存在 `~/.agents/memory/MEMORY.md`，**先读取**，快速了解用户背景、偏好与近期会话。
2. **再读 `~/.agents/memory/OPEN_LOOPS.md`（未收尾事项，唯一待办真相源）**，汇报 🔴/🟢 条目；⏸ 搁置项不主动催。
3. 需要细节时用 `memory.py get <id>` 或 `memory.py search <关键词>` 深挖。
4. 向用户展示已记住的关键信息（简要），体现连续性。

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
4. **回写 `~/.agents/memory/OPEN_LOOPS.md`**：新增线头、改状态、把干完的移进「✅ 已结」（附结论与验证方式）。**这是硬动作，不许省**——会话摘要是回忆录，OPEN_LOOPS.md 才是任务单（2026-09-11 翻车教训）。
5. 用 `memory.py session-save "<本次会话一句话摘要>" --key 关键词1,关键词2` 保存会话记录。
6. 运行 `memory.py sync` 刷新 MEMORY.md 总览。

## 🔍 查询记忆

用户问"我之前说过/我们上次/我的偏好"之类 → `memory.py search <关键词>`；列全部 → `memory.py list`。

## ⚙️ 工具速查

```bash
P=~/.agents/skills/pi-memory-facts/memory.py
$P init                       # 首次初始化
$P add fact "内容" --tag 偏好    # 存事实/模式/经验
$P session-save "摘要" --key a  # 存会话摘要
$P search 关键词                # 搜索
$P list                        # 全部列出
$P get <id> / update <id> <新内容> / delete <id>   # 管理
$P stats                       # 统计
$P sync                        # 刷新总览 MEMORY.md
```

## 🧱 记忆机制 v2（分层卡片，2026-09-11 起）

除旧四层外，另有一套**分层卡片库**（`~/.agents/memory/cards.json`），面向"下次读回来不走样"设计：
L1 工作法（按触发场景）｜ L2 项目状态（开场只列名字，详情在本机项目总表）｜ L3 环境事实 ｜ L5 调优日志（用户的纠正与边界）｜ **L6 冷藏**（“先放放”的事，永不进开场）。

**检索铁律**：先查项目总表 → 再查 L1–L5 → 都找不到才翻 L6（`memory.py icebox`）。

```bash
P=~/.agents/skills/pi-memory-facts/memory.py
$P card add --layer L1 --scene writing --text "要这么做的一句话" [--note 例/边界] [--why 仅在防读偏时写] [--tag a,b] [--src 来源] [--verify tested] [--evidence "命令/输出/谁说的"]
$P card add --layer L2 --project <项目> --status active --text "现状或下一步"
$P card verify <id> self|review|tested|human [--evidence "证据"]   # 标验证等级（升级/降级都行）
$P card search <词> / card list --layer L1 / card show <id>
$P proj set <名> --title 中文名 --oneliner "一句话" --alias "别名1,别名2" --path <路径>
$P proj find <关键词>      # 项目名记不全时搜别名
$P build [--scene writing] [--budget 3500]   # 生成 BOOT.md + 项目总表(md+HTML) + playbook/ projects/ 正文镜像
$P doctor                                    # 体检：超长/缺场景/指代词/重复/疑似重复/无标签/预算
$P icebox                                    # 列出冷藏层（用户说“先放放”的事）
```

**开场读 `~/.agents/memory/BOOT.md`**（自动生成的目录，≤3.5k tokens）：**项目只列名字**，详情在本机项目总表（HTML 带实时搜索版 + MD 版）；工作法正文按需 `card search` 或读 `playbook/<场景>.md`。
写入判据：**零上下文读回来必须不走样**——写成"要这么做"的指令式，禁指代词，一条一件事（≤200 字）。

### 🔍 验证等级（借 AutoFyn 的 assurance class，2026-09-12）

每条卡还有一个 `verify` 字段，回答"我有多确定"，与内容分开存：

| 标记 | 等级 | 含义 | 谁给的 |
|:---:|---|---|---|
| ★ | `human` | 用户当场确认或纠正过 | 最高 |
| ✓ | `tested` | 我实跑过，有可复现的命令/结果 | |
| ~ | `review` | 独立来源 / 另一上下文交叉核对过 | |
| ? | `self` | **默认**——我自己推断/写的，没人验过 | 用前先核 |

- **读时兑底**：没标过 `verify` 的卡一律按 `?`（自评）算，所以"未确认卡数量"不用额外记账，天然可观测。
- **排序影响**：`card search` 会把已确认的排前面、自评的沉底；**BOOT.md 每条前面带标记**。
- **提醒**：`card verify <id> ...` 升级后，**行为要跟着变**（★ 可直接引用；? 要先验证再当真话说）。
- 体检：`$P doctor` 会报验证等级分布、**L2/L3 里还待确认的清单**、以及**疑似路径失效的卡**（引用的本机文件已不存在 → 该退役）。
- **改过 doctor 后先跑 `$P doctor --selftest`**：9 个用例（2 正例 + 7 反例）证明检测器真能报出东西。
  教训（09-12）："报告里是空的"≠"真的没问题"——第一版路径检测不报假就是瞎（压根不匹配 `/home/` 路径）。

> 设计文档：本仓库 `DESIGN.md`（长线项目，P1 已完，P2 迁移存量中）

## 📂 存储位置

- 数据：`~/.agents/memory/memory.json`（四层记忆，JSON）
- 总览：`~/.agents/memory/MEMORY.md`（会话启动时读这个——**回顾型**）
- 待办：`~/.agents/memory/OPEN_LOOPS.md`（会话启动时也读——**前瞻型**，唯一待办真相源）
- 技能本体：`~/.agents/skills/pi-memory-facts/`（工具 + 本说明）

## ⚠️ 边界

- **不存敏感凭据**：token、密码、密钥一律不保存。
- **尊重用户意愿**：用户说"这个别记"则不存；说"忘掉 X"则 `delete` 对应条目。
- 记忆是辅助，不替代确认：涉及重要操作仍以用户当前意图为准。
