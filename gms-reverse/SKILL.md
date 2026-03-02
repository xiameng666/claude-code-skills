---
name: gms-reverse
description: 逆向分析GMS代码并还原Java实现，使用JEB MCP验证所有信息，按依赖顺序从叶子节点还原至根节点
license: MIT
compatibility: opencode
metadata:
  domain: reverse-engineering
  target: android-gms
  tools: jeb-mcp
  depends: reverse-workspace
---

## 前置条件

**开始任何工作前，必须先执行 `reverse-workspace` skill 的初始化流程。**

## 核心原则

**所有信息必须使用 JEB MCP 进行求证，禁止自我推导或猜测，避免幻觉。**

## 工作流程

### 0. 工作空间初始化（必须）

**基础初始化**（调用 reverse-workspace）：
1. 检查 `.reverse/` 目录是否存在
2. 不存在则创建基础脚手架
3. 存在则读取 `manifest.md` 恢复上下文

**类还原扩展初始化**（本 skill 特有）：
4. 检查 `queue-restored.md` 是否存在
5. 不存在则创建类还原队列文件（见下方命令）
6. 存在则读取队列汇报进度

**类还原队列初始化命令**：
```powershell
# queue-restored.md
@"
# 已还原队列

| 类名 | GMS原始名 | 还原日期 | 验证状态 |
|------|----------|----------|----------|
"@ | Out-File -Encoding utf8 ".reverse/queue-restored.md"

# queue-pending.md
@"
# 待还原队列

按依赖顺序排列（叶子节点优先）

| 优先级 | 类名 | GMS原始名 | 依赖项 | 备注 |
|--------|------|----------|--------|------|
"@ | Out-File -Encoding utf8 ".reverse/queue-pending.md"

# queue-placeholder.md
@"
# 占位类队列

与核心业务无关，仅作为依赖占位

| 类名 | GMS原始名 | 占位原因 | 处理方式 |
|------|----------|----------|----------|
"@ | Out-File -Encoding utf8 ".reverse/queue-placeholder.md"

# class-diagram.mermaid
@"
classDiagram
    direction TB
    class RootClass {
        <<目标>>
    }
"@ | Out-File -Encoding utf8 ".reverse/class-diagram.mermaid"
```

### 1. 业务熟悉阶段
- 通过 JEB MCP 分析目标模块的整体结构
- 确定需要还原的核心模块主类
- 理解类之间的依赖关系

### 2. 类图绘制
- 使用 mermaid 绘制树状类图
- 只体现类的继承关系或逆向还原关系
- 注重叶子节点与根节点的层级结构
- 不需要绘制方法和字段

### 3. 还原顺序
- **从叶子节点开始，逐步还原至根节点**
- 避免依赖未还原的类
- 每个类还原完成后立即验证

### 4. 验证流程
每次还原完一个类后：
1. 使用 JEB MCP 重复审阅代码逻辑是否与 GMS 一致
2. 确保编译通过
3. 检查与已还原类的接口兼容性

### 5. 重命名规范
使用 JEB MCP 重命名时，格式为：`原名称_重命名名称`
- 重命名目标类的成员变量
- 重命名内部函数
- 重命名内部成员变量
- 已重命名的跳过

## 文档更新模式（持久化）

**每完成一个类的还原，必须立即更新以下文件：**

### 1. `.reverse/queue-restored.md`
添加一行：`| 类名 | 原始名称 | 还原日期 | ✅ |`

### 2. `.reverse/queue-pending.md`
- 删除已完成的类
- 添加新发现的依赖类

### 3. `.reverse/class-diagram.mermaid`
- 更新类的状态标注（`<<已还原>>` / `<<待还原>>` / `<<占位>>`）
- 添加新发现的依赖关系

### 4. `.reverse/manifest.md`
- 更新进度统计
- 更新"最近活动"

### 5. 当前 session 日志
记录本次操作详情

## 何时使用此 Skill

- 逆向分析 Android GMS 相关代码
- 需要将反编译代码还原为可编译的 Java 实现
- 需要维护类依赖关系和还原进度文档
