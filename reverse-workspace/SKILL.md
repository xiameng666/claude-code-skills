---
name: reverse-workspace
description: 逆向工程工作空间管理，提供脚手架初始化、上下文持久化、会话生命周期管理
license: MIT
compatibility: opencode
metadata:
  domain: reverse-engineering
  tools: jeb-mcp, ida-mcp, frida
---

## 概述

此 Skill 为逆向工程项目提供**持久化上下文管理**，让 AI 的工作记忆保存在本地文件中，支持跨会话恢复。

## 触发条件

当用户提到以下关键词时，**必须首先执行初始化检查**：
- "逆向"、"还原"、"分析"
- 提及 JEB、IDA、Frida 等工具
- 开始新的逆向项目

## 工作空间结构（基础）

```
项目根目录/
├── .reverse/                      # 逆向工作空间根目录
│   ├── manifest.md                # 项目元信息与当前状态
│   ├── analysis-notes.md          # 分析笔记与关键发现
│   ├── analysis/                  # 专题分析文档目录
│   ├── logs/                      # 运行日志目录
│   └── sessions/                  # 会话日志目录
│       └── YYYY-MM-DD-HH-MM.md    # 单次会话记录
```

**注意**: 类还原队列（queue-*.md）和类图（class-diagram.mermaid）由 `gms-reverse` 等具体任务 skill 按需创建。

## 会话生命周期

### Phase 1: 初始化（每次会话开始时必须执行）

```
1. 检查 .reverse/ 目录是否存在
2. 如果不存在 → 执行脚手架初始化
3. 如果存在 → 读取 manifest.md 恢复上下文
4. 创建新的 session 日志文件
5. 向用户汇报当前状态
```

**脚手架初始化命令**（在项目根目录执行）：
```powershell
# 创建目录结构
New-Item -ItemType Directory -Force -Path ".reverse/sessions"
New-Item -ItemType Directory -Force -Path ".reverse/analysis"
New-Item -ItemType Directory -Force -Path ".reverse/logs"

# 创建 manifest.md
@"
# 逆向工程项目 Manifest

## 项目信息
- **目标**: [待填写]
- **创建时间**: $(Get-Date -Format "yyyy-MM-dd HH:mm")
- **当前阶段**: 初始化

## 目标模块
[待分析确定]

## 最近活动
[无]

## 文档索引
[按需添加]
"@ | Out-File -Encoding utf8 ".reverse/manifest.md"

# 创建 analysis-notes.md
@"
# 分析笔记

## 关键发现
[无]

## 疑难问题
[无]

## 技术细节
[无]
"@ | Out-File -Encoding utf8 ".reverse/analysis-notes.md"
```

### Phase 2: 工作中（持续更新）

**基础更新（所有任务）：**
1. 更新 `manifest.md` 的"最近活动"
2. 在当前 session 日志中记录操作
3. 重要发现写入 `analysis-notes.md`

**注意**: 具体任务（如类还原）的文件更新由对应的 skill 定义。

**Session 日志格式：**
```markdown
# Session: YYYY-MM-DD HH:MM

## 目标
[本次会话的目标]

## 完成事项
- [ ] 事项1
- [ ] 事项2

## 分析记录
### HH:MM - [操作]
[详细记录]

## 下次继续
[待处理事项]
```

### Phase 3: 会话结束

在用户结束会话前或长时间无操作时：

1. 更新 session 日志的"完成事项"和"下次继续"
2. 更新 `manifest.md` 的"最近活动"
3. 向用户汇报本次进度

## 文件格式规范

### manifest.md（通用）
```markdown
# 逆向工程项目 Manifest

## 项目信息
- **目标**: [APK/SO名称]
- **创建时间**: YYYY-MM-DD
- **当前阶段**: [分析/还原/验证]

## 目标模块
[描述]

## 最近活动
- YYYY-MM-DD: [活动描述]

## 文档索引
| 文档 | 位置 | 说明 |
|------|------|------|
```

### analysis-notes.md
```markdown
# 分析笔记

## 关键发现
### YYYY-MM-DD: [标题]
[内容]

## 疑难问题
[问题描述和思考]

## 技术细节
[参数、常量、算法细节等]
```

## 与其他 Skill 的协作

此 Skill 提供**基础工作空间**，具体任务 skill 在此基础上扩展：

| Skill | 扩展内容 |
|-------|----------|
| `gms-reverse` | queue-*.md, class-diagram.mermaid |
| `ida-arm64-restore` | functions-*.md |
| `reverse-code-review` | audit-report.md |

## 恢复上下文示例

当读取到 `manifest.md` 显示项目已在进行中时，向用户汇报：

```
检测到进行中的逆向项目：
- 目标: [xxx]
- 当前阶段: [xxx]
- 上次活动: [xxx]

是否继续上次的工作？
```

## 强制规则

1. **禁止**在没有初始化工作空间的情况下开始逆向工作
2. **禁止**仅依赖上下文记忆，所有关键信息必须写入文件
3. **每完成一个原子操作**（如还原一个类）必须立即更新文件
4. 发生错误或中断时，优先保存当前进度到文件
