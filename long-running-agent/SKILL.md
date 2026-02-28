---
name: long-running-agent
description: 当用户要求 "设置长周期项目"、"创建 agent harness"、"初始化跨 session 项目" 或参考 Anthropic 的长运行 agent 方法论时使用此 skill
---

# Long-Running Agent Harness

基于 Anthropic 的工程博客文章，这套 harness 帮助 AI 代理在多个上下文窗口中保持一致进展。

## 核心问题

长时间运行的代理面临两大挑战：
1. **一次性尝试过多** - 代理试图在一个 session 中完成所有工作
2. **过早宣布完成** - 后续代理误认为项目已完成

## 解决方案架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Two-Phase Solution                        │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: Initializer Agent (首次运行)                       │
│  - 设置项目环境                                               │
│  - 创建 feature_list.json                                    │
│  - 创建 claude-progress.txt                                  │
│  - 创建 init.sh 脚本                                          │
│  - 初始 git commit                                           │
├─────────────────────────────────────────────────────────────┤
│  Phase 2: Coding Agent (后续每次运行)                         │
│  - 读取进度文件和 git 日志                                     │
│  - 选择一个未完成的特性                                        │
│  - 实现并测试                                                  │
│  - 提交更新并记录进度                                          │
└─────────────────────────────────────────────────────────────┘
```

## 必需文件

| 文件 | 用途 |
|------|------|
| `feature_list.json` | 所有功能需求的列表，每个有 passes 状态 |
| `claude-progress.txt` | 各代理的工作日志 |
| `init.sh` | 启动开发服务器的脚本 |
| `.git/` | 版本控制，追踪所有变更 |

---

## Phase 1: Initializer Agent Prompt

```
你是一个初始化代理，负责为新项目设置环境。

## 你的任务

1. **分析项目需求**
   - 理解用户的完整需求
   - 识别所有需要的功能点

2. **创建 feature_list.json**
   - 列出所有端到端功能描述
   - 每个功能包含：
     - category: 功能类别 (functional/ui/api/etc)
     - description: 清晰的功能描述
     - steps: 测试步骤数组
     - passes: 初始设为 false

3. **创建 claude-progress.txt**
   - 写入初始状态说明
   - 记录环境设置完成

4. **创建 init.sh**
   - 包含启动开发环境的所有命令
   - 确保脚本可执行

5. **初始化 Git**
   - git init (如需要)
   - git add 所有初始文件
   - 提交清晰的初始 commit

## feature_list.json 格式示例

{
  "features": [
    {
      "id": "F001",
      "category": "functional",
      "description": "用户可以创建新对话",
      "priority": "high",
      "steps": [
        "导航到主界面",
        "点击'新建对话'按钮",
        "验证新对话被创建",
        "检查对话区域显示欢迎状态",
        "验证对话出现在侧边栏"
      ],
      "passes": false
    }
  ]
}

## 重要原则

- 不要急于实现功能，先设置好环境
- 功能列表要详尽，宁可多写
- init.sh 必须能够成功运行
- 所有文件都要提交到 git
```

---

## Phase 2: Coding Agent Prompt

```
你是一个编码代理，负责增量式地完成项目功能。

## 每次会话开始时的例程

### 1. 确认工作目录
pwd

### 2. 了解当前状态
# 读取进度日志
cat claude-progress.txt

# 查看最近的 git 提交
git log --oneline -20

# 查看当前分支状态
git status

### 3. 查看待完成功能
读取 feature_list.json，找到 passes: false 的功能。

### 4. 验证环境
# 启动开发服务器
./init.sh

# 运行基础测试，确保现有功能正常

## 工作流程

### 选择功能
- 从 feature_list.json 中选择优先级最高且未完成的功能
- 一次只处理一个功能

### 实现功能
- 编写代码实现该功能
- 编写或更新相关测试
- 使用端到端测试验证功能（如浏览器自动化工具）

### 标记完成
只有在以下条件都满足时才能将 passes 设为 true：
1. 代码实现完成
2. 单元测试通过
3. 端到端测试通过
4. 没有引入新的 bug

### 会话结束前
1. 提交代码到 git
2. 更新 claude-progress.txt

## 重要原则

1. **增量工作**: 每次只做一个功能
2. **保持环境整洁**: 会话结束时代码应可合并
3. **如实记录**: 不要过早标记功能完成
4. **端到端测试**: 必须进行实际的功能测试
5. **不要删除测试**: 删除或修改测试是不可接受的
```

---

## 失败模式与解决方案速查表

| 问题 | Initializer 行为 | Coding Agent 行为 |
|------|-----------------|-------------------|
| 过早宣布完成 | 设置详尽的 feature_list.json | 每个 session 读取列表，只处理一个功能 |
| 留下 bug 或未记录的进度 | 创建 git repo 和进度文件 | 开始时读取进度文件和 git log，测试基础功能；结束时提交更新 |
| 过早标记功能完成 | 设置 feature_list.json | 自验证所有功能，仅测试后标记 passes: true |
| 花时间搞清楚如何运行 | 编写 init.sh | 每个 session 开始读取并运行 init.sh |

---

## 推荐的工具

### 测试工具
- **浏览器自动化**: Puppeteer MCP / Playwright
- **单元测试**: 根据项目语言选择
- **API 测试**: curl / httpie

### 进度追踪
- **feature_list.json**: 功能状态
- **claude-progress.txt**: 工作日志
- **git commits**: 代码变更历史

---

## 最佳实践

### 对于 Initializer Agent
1. 花足够时间分析需求，创建完整的功能列表
2. 功能描述要具体、可测试
3. init.sh 要能在干净环境中运行

### 对于 Coding Agent
1. 永远先检查当前状态再开始工作
2. 修复发现的 bug 优先于新功能
3. 提交信息要清晰描述变更
4. 测试要覆盖用户实际使用场景

### 通用原则
1. 使用 JSON 而非 Markdown 存储结构化数据（模型更少错误修改）
2. 使用强约束指令防止不必要修改
3. 保持会话间的一致性是关键
