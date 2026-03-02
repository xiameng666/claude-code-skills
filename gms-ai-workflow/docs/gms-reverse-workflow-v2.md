# GMS 逆向分析完整工作流 v2

## 核心设计理念

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         设计原则                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 数据库优先：拓扑阶段只写数据库，不生成文档                               │
│     - 混淆名阶段信息不完整，写文档没有意义                                   │
│     - 数据库更适合存储结构化数据（依赖关系、状态）                           │
│                                                                             │
│  2. 先理解业务，再还原代码：                                                 │
│     - Phase 4: 业务梳理 (叶子 → 根，理解整个模块)                            │
│     - Phase 5: 逆向还原 (还原代码 + 编译验证)                                │
│                                                                             │
│  3. Ralph 任务单一化：每个阶段只做一件事                                     │
│     - Phase 3: 拓扑发现（发现所有节点）                                      │
│     - Phase 4: 业务梳理（分析业务 + 生成文档）                               │
│     - Phase 5: 逆向还原（还原代码 + 编译验证）                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 五阶段概览

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Phase 1    │    │   Phase 2    │    │   Phase 3    │    │   Phase 4    │    │   Phase 5    │
│    初始化    │ ─→ │   数据导入   │ ─→ │   拓扑发现   │ ─→ │   业务梳理   │ ─→ │   逆向还原   │
│              │    │              │    │              │    │              │    │              │
│  询问路径    │    │  JEB导出     │    │  Ralph循环   │    │  Ralph循环   │    │  Ralph循环   │
│  创建目录    │    │  导入SQLite  │    │  双Agent     │    │  叶子→根     │    │  编译验证    │
│              │    │              │    │  只写DB      │    │  写MD+标签   │    │  生成Java    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
      │                   │                   │                   │                   │
   5分钟               10分钟             小时/天              小时/天             天/周


业务理解优先的原因:

  叶子类 (基础组件)
      ↓
  中间层 (组合基础组件)
      ↓
  根节点 (业务入口)

  只有从叶子开始分析，才能理解上层类的业务逻辑
  业务梳理完成后，还原代码时才能有的放矢
```

---

## Phase 1: 初始化

### 1.1 交互式询问

**必须使用 `AskUserQuestion` 询问工作区路径**：

```json
{
  "questions": [{
    "question": "请选择工作区存储位置：",
    "header": "知识库路径",
    "options": [
      {"label": "文档目录 (推荐)", "description": "C:\\Users\\{用户名}\\Documents\\gms-knowledge"},
      {"label": "用户目录", "description": "C:\\Users\\{用户名}\\gms-knowledge"},
      {"label": "自定义路径", "description": "手动输入完整路径"}
    ]
  }]
}
```

### 1.2 创建目录结构

```
gms-knowledge/                     # 工作区 (Phase 1 创建)
├── gms-rename.db                  # SQLite 数据库 (核心)
│   ├── classes                    # 类信息表
│   ├── dependencies               # 依赖关系表
│   ├── analysis_status            # 分析状态表
│   └── renames                    # 重命名映射表
│
├── notes/                         # (Phase 4 生成) 分析笔记
├── reports/                       # 模块报告
├── imports/                       # 导入数据
│   └── jeb-deps.json
├── logs/                          # 运行日志
└── .ralph/                        # Ralph 循环状态
```

**注意**：Android 项目路径在 Phase 4 开始前询问用户，不预设目录结构。

---

## Phase 2: 数据导入

### 2.1 导出 JEB 类依赖

用户在 JEB 中手动执行：
1. `File → Scripts → Run Script...`
2. 选择 `ExportDeps.py`
3. 输出到 `{knowledge_dir}/imports/jeb-deps.json`

### 2.2 导入到 SQLite

```
jeb-deps.json ──→ import_from_jeb_json() ──→ SQLite

导入内容:
  • 类签名 (混淆名)
  • 父类/接口关系
  • 字段类型
  • 方法签名
  • 初始依赖关系

注意: 此阶段不生成 MD 文件
```

---

## Phase 3: 拓扑发现 (Ralph 循环)

### 3.1 目标

**以根节点为基础，向外做拓扑，发现所有依赖节点**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  拓扑发现任务                                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  输入: 种子类 (根节点，如 Lfvxn;)                                           │
│  输出: 完整的依赖图 (存储在 SQLite)                                         │
│                                                                             │
│  策略: BFS (广度优先) 从根节点向外探索                                       │
│                                                                             │
│  存储规则:                                                                   │
│    • 只写数据库 (dependencies 表)                                           │
│    • 不生成 MD 文件                                                         │
│    • 不做深入分析，只发现依赖                                               │
│                                                                             │
│  过滤规则:                                                                   │
│    • 系统类 (java.*, android.*, kotlin.*, etc.) 不入队                     │
│    • 已发现的类不重复入队                                                   │
│                                                                             │
│  完成条件: 队列为空 (所有节点都已发现)                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Ralph 循环命令

```bash
/ralph-loop "
  拓扑发现任务

  种子类: Lfvxn; (根节点，首先入队)

  目标: BFS 探索，发现所有依赖的混淆类

  一轮流程:
  1. 从队列取出一个类
  2. Agent A: 探索它的依赖 (父类、接口、字段、方法体)
  3. Agent B: 审查是否遗漏
     - 通过: 依赖入库，新发现的混淆类追加到队尾
     - 不通过: Agent A 补充，重新审查
  4. 本轮完成，继续下一轮

  完成条件: 队列清空 (没有待处理的类了)
  完成时输出: <promise>TOPOLOGY_COMPLETE</promise>
" --completion-promise "TOPOLOGY_COMPLETE" --max-iterations 1000
```

### 3.3 数据库设计

```sql
-- 依赖关系表
CREATE TABLE dependencies (
    id INTEGER PRIMARY KEY,
    from_class TEXT NOT NULL,    -- 依赖方 (混淆名)
    to_class TEXT NOT NULL,      -- 被依赖方 (混淆名)
    dep_type TEXT,               -- dependency type: extends, implements, field, method_body
    discovered_at TIMESTAMP,
    UNIQUE(from_class, to_class, dep_type)
);

-- 分析状态表
CREATE TABLE analysis_status (
    class_sig TEXT PRIMARY KEY,  -- 类签名 (混淆名)
    discovered BOOLEAN DEFAULT 0,-- 是否已发现
    analyzed BOOLEAN DEFAULT 0,  -- 是否已分析 (Phase 3)
    restored BOOLEAN DEFAULT 0,  -- 是否已还原 (Phase 4)
    documented BOOLEAN DEFAULT 0,-- 是否已生成文档 (Phase 4)
    in_degree INTEGER DEFAULT 0, -- 入度 (被多少类依赖)
    out_degree INTEGER DEFAULT 0 -- 出度 (依赖多少类)
);
```

### 3.4 双 Agent 协作

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Agent A: 依赖发现者                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  输入: 类签名 (混淆名)                                                       │
│                                                                             │
│  操作:                                                                       │
│    1. get_class_decompiled_code() - 获取反编译代码                          │
│    2. get_class_superclass() - 获取父类                                     │
│    3. get_class_interfaces() - 获取接口                                     │
│    4. get_class_fields() - 获取字段类型                                     │
│    5. 从方法体中提取:                                                        │
│       - new 语句中的类型                                                     │
│       - 静态方法调用                                                         │
│       - 类型转换                                                             │
│       - Lambda/匿名类                                                        │
│                                                                             │
│  输出: 依赖列表 [Lxxx;, Lyyy;, ...]                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Agent B: 审查者                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  审查内容 (只审查方法体依赖):                                                 │
│    □ new 语句是否全部提取?                                                   │
│    □ 静态方法调用是否全部提取?                                               │
│    □ 类型转换是否全部提取?                                                   │
│    □ Lambda/匿名类是否全部提取?                                              │
│                                                                             │
│  审查结果:                                                                   │
│    ✓ 通过 → 依赖写入数据库，更新队列                                         │
│    ✗ 不通过 → 说明遗漏项，Agent A 补充                                       │
│                                                                             │
│  一轮完成: 审查通过且没有新的混淆类发现                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.5 一轮的定义

```
┌─────────────────────────────────────────────────────────────────┐
│  "一轮" 的定义                                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  一轮 = 处理一个类的完整流程                                     │
│                                                                 │
│  流程:                                                          │
│    1. 从队列取出一个类                                          │
│    2. Agent A 探索它的依赖                                      │
│    3. Agent B 审查                                              │
│       ├─→ 通过: 依赖入库，新发现的类追加到队尾                  │
│       └─→ 不通过: Agent A 补充，重新审查                        │
│    4. 审查通过 = 本轮完成                                       │
│                                                                 │
│  整体完成条件:                                                   │
│    队列清空 (没有待处理的类了)                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.6 队列模型 (BFS)

```
待处理队列:

初始: [Lfvxn;]  ← 种子类入队

第1轮:
  取出: Lfvxn;
  Agent A: 探索依赖 → [Labc;, Ldef;, Lghi;]
  Agent B: 审查通过 ✓
  新类入队: [Labc;, Ldef;, Lghi;]
  队列: [Labc;, Ldef;, Lghi;]

第2轮:
  取出: Labc;
  Agent A: 探索依赖 → [Ljkl;]
  Agent B: 审查通过 ✓
  新类入队: [Ljkl;]
  队列: [Ldef;, Lghi;, Ljkl;]

第3轮:
  取出: Ldef;
  Agent A: 探索依赖 → [] (叶子节点，无混淆类依赖)
  Agent B: 审查通过 ✓
  新类入队: []
  队列: [Lghi;, Ljkl;]

... 继续处理 ...

第N轮:
  取出: Lpqr; (最后一个)
  Agent A: 探索依赖 → []
  Agent B: 审查通过 ✓
  新类入队: []
  队列: []  ← 空!

完成: 队列清空，所有可达节点已发现
```

### 3.7 检查点输出

```
[拓扑发现] 第 47 轮 | 队列: 23 | 已处理: 46 | 已发现: 156
[Agent A] 分析 Labc; 发现 8 个依赖
[Agent B] 审查通过 ✓
[过滤] 系统类: 5 | 已发现: 2 | 新入队: 1
[数据库] 写入 8 条依赖关系
[本轮完成] Labc; → 1 个新类入队
```

### 3.8 Ralph 状态文件

```yaml
# .ralph/topology-discovery.md
---
active: true
iteration: 47
max_iterations: 1000
completion_promise: "TOPOLOGY_COMPLETE"
seed_class: "Lfvxn;"
started_at: "2026-03-01T10:00:00Z"
---

# 拓扑发现任务

## 种子类
Lfvxn;

## 当前进度
- 已处理: 46
- 队列中: 23
- 已发现总计: 156

## 队列内容 (待处理)
[Ldef;, Lghi;, Ljkl;, ...]

## 完成条件
队列清空 (没有待处理的类了)

## 规则
- 一轮 = 取出一个类 → Agent A 探索 → Agent B 审查通过
- 只写数据库，不生成 MD 文件
- 系统类不入队
```

---

## Phase 4: 业务梳理 (Ralph 循环)

### 4.1 目标

**基于叶子节点到根节点的依赖图，梳理整个模块的业务逻辑**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  业务梳理任务                                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  输入: 完整的依赖图 (Phase 3 产出，在 SQLite)                               │
│  输出: 每个类的 MD 文档 (含业务分析 + 标签)                                  │
│                                                                             │
│  策略: 拓扑逆序 (从叶子到根)                                                 │
│                                                                             │
│  核心原则:                                                                   │
│    当一个类的所有依赖都已梳理完成 → 才能梳理这个类                           │
│    依赖已梳理 = 下游类的业务功能已知 → 可以引用来解释当前类                  │
│                                                                             │
│  单类处理流程:                                                               │
│    1. 选择: 依赖都已梳理的类 (叶子优先)                                      │
│    2. 分析: 理解业务功能 (依赖类已梳理，可引用上下文)                        │
│    3. 标签: 识别类型、模块、功能标签                                         │
│    4. 文档: 生成 MD，记录业务逻辑 + 引用依赖类的功能                         │
│    5. 标记: analyzed=1，可被上层类引用                                       │
│                                                                             │
│  完成条件: 所有类梳理完成 + 文档生成                                         │
│                                                                             │
│  注意: 此阶段不生成 Java 代码，只做业务理解和文档                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 为什么业务梳理要在还原之前

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  先理解业务，再还原代码                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  传统方式:                                                                   │
│    看代码 → 猜功能 → 写文档                                                 │
│    问题: 代码是混淆的，很难直接理解业务                                      │
│                                                                             │
│  改进方式:                                                                   │
│    梳理依赖 → 理解业务 → 生成文档 → 还原代码                                │
│    优势: 业务理解指导代码还原，更有针对性                                    │
│                                                                             │
│  具体好处:                                                                   │
│    1. 从叶子开始，逐步理解基础组件                                           │
│    2. 分析上层类时，可以引用下游类的业务说明                                 │
│    3. 业务逻辑链条完整，文档有价值                                           │
│    4. 还原代码时已经理解业务，命名更准确                                     │
│    5. 标签系统帮助分类和检索                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 拓扑逆序算法

```python
def get_topological_order(graph):
    """
    从叶子到根的拓扑排序

    叶子节点: out_degree == 0 (不依赖其他混淆类)
    """
    # 计算出度
    out_degree = {node: 0 for node in graph.nodes}
    for node in graph.nodes:
        out_degree[node] = len([d for d in graph.get_dependencies(node)
                                if not is_system_class(d)])

    # 从叶子开始
    queue = [n for n in graph.nodes if out_degree[n] == 0]
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)

        # 更新依赖此节点的类的出度
        for dependent in graph.get_dependents(node):
            out_degree[dependent] -= 1
            if out_degree[dependent] == 0:
                queue.append(dependent)

    return result  # 叶子 → 根
```

### 4.4 Ralph 循环命令

```bash
/ralph-loop "
  业务梳理任务

  输入: 依赖图 (SQLite)

  策略: 拓扑逆序 (叶子 → 根)

  核心原则: 当一个类的所有依赖都已梳理完成，才能梳理这个类

  单类处理流程:
  1. 选择: 依赖都已梳理的类 (叶子优先)
  2. 获取: 反编译代码 + 已重命名的符号
  3. 分析: 理解业务功能 (依赖类已梳理，可引用上下文)
  4. 标签: 识别类型、模块、功能标签
  5. 文档: 生成 MD，记录业务逻辑
  6. 标记: analyzed=1，可被上层类引用

  注意: 此阶段不生成 Java 代码，只做业务理解和文档

  完成条件: 所有类梳理完成 + 文档生成
  完成时输出: <promise>ANALYSIS_COMPLETE</promise>
" --completion-promise "ANALYSIS_COMPLETE" --max-iterations 2000
```

### 4.5 单类业务梳理流程

```
┌─────────────────────────────────────────────────────────────────┐
│  单类业务梳理流程                                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  前提: 当前类的所有依赖都已梳理完成                              │
│                                                                 │
│  1. 选择下一个可梳理的类                                         │
│     └─→ 查询 SQLite: WHERE analyzed=0 AND 依赖都已 analyzed     │
│     └─→ 优先选择叶子节点 (无依赖)                                │
│                                                                 │
│  2. 获取类信息                                                   │
│     └─→ get_class_decompiled_code()                             │
│     └─→ get_rename() (获取已重命名的符号)                       │
│     └─→ 读取依赖类的 MD 文档 (业务上下文)                        │
│                                                                 │
│  3. 业务分析                                                     │
│     └─→ 理解类的职责和业务逻辑                                   │
│     └─→ 分析与其他类的交互关系                                   │
│     └─→ 识别设计模式和架构角色                                   │
│     └─→ 引用依赖类的功能说明                                     │
│                                                                 │
│  4. 标签识别                                                     │
│     └─→ 识别类型标签 (proto, data_class, interface, etc.)       │
│     └─→ 识别模块标签 (location, fusion, auth, etc.)             │
│     └─→ 识别功能标签 (callback, handler, builder, etc.)         │
│                                                                 │
│  5. 生成 MD 文档                                                 │
│     └─→ frontmatter 包含标签                                     │
│     └─→ 记录业务功能                                             │
│     └─→ 引用依赖类的功能说明                                     │
│     └─→ 写入 notes/{ClassName}.md                               │
│                                                                 │
│  6. 更新状态                                                     │
│     └─→ SQLite: analyzed=1, documented=1                        │
│     └─→ SQLite: tags 字段更新                                    │
│     └─→ 此类现在可以被上层类引用                                 │
│                                                                 │
│  注意: 此阶段不生成 Java 代码                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.6 标签系统

**在逆向还原时，基于类的特征自动生成标签，用于后续检索和分类**：

```
┌─────────────────────────────────────────────────────────────────┐
│  标签分类                                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  类型标签 (type):                                                │
│    • proto        - Protobuf 消息类                             │
│    • data_class   - 纯数据类 (只有字段和 getter/setter)          │
│    • interface    - 接口                                        │
│    • abstract     - 抽象类                                      │
│    • enum         - 枚举                                        │
│    • exception    - 异常类                                      │
│    • util         - 工具类                                      │
│                                                                 │
│  模块标签 (module):                                              │
│    • location     - 位置相关                                    │
│    • fusion       - 融合引擎                                    │
│    • auth         - 认证授权                                    │
│    • network      - 网络通信                                    │
│    • storage      - 数据存储                                    │
│    • ...                                                        │
│                                                                 │
│  功能标签 (function):                                            │
│    • callback     - 回调接口                                    │
│    • handler      - 处理器                                      │
│    • builder      - 构建器模式                                  │
│    • factory      - 工厂模式                                    │
│    • singleton    - 单例模式                                    │
│    • listener     - 监听器                                      │
│    • manager      - 管理器                                      │
│    • ...                                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**标签识别规则**：

```python
def identify_tags(class_info):
    tags = []

    # 类型标签识别
    if is_protobuf_class(class_info):
        tags.append("proto")
    if is_data_class(class_info):  # 只有字段，无业务逻辑
        tags.append("data_class")
    if class_info.is_interface:
        tags.append("interface")
    if class_info.is_abstract:
        tags.append("abstract")
    if class_info.is_enum:
        tags.append("enum")
    if extends_exception(class_info):
        tags.append("exception")
    if is_utility_class(class_info):  # 静态方法为主
        tags.append("util")

    # 模块标签识别 (基于包路径、类名、依赖)
    module = infer_module(class_info)
    if module:
        tags.append(module)  # location, fusion, auth, etc.

    # 功能标签识别 (基于类名后缀、方法特征)
    if class_info.name.endswith("Callback"):
        tags.append("callback")
    if class_info.name.endswith("Handler"):
        tags.append("handler")
    if class_info.name.endswith("Builder"):
        tags.append("builder")
    if class_info.name.endswith("Factory"):
        tags.append("factory")
    if is_singleton(class_info):
        tags.append("singleton")
    if class_info.name.endswith("Listener"):
        tags.append("listener")
    if class_info.name.endswith("Manager"):
        tags.append("manager")

    return tags
```

### 4.7 MD 文档模板

```markdown
---
tags:
  - proto
  - location
  - data_class
created_at: 2026-03-01
dependencies_analyzed: true
---

# {ClassName}

## 业务概述

**职责**: {一句话描述这个类的业务职责}

**业务逻辑**:
{详细描述这个类的业务功能，引用依赖类的功能说明}

例如:
  "FusionEngine 负责协调位置融合流程。
   它从 LocationProvider 获取原始位置数据，
   通过 DataProcessor 进行过滤和平滑处理，
   最终输出高精度的融合位置信息。"

**设计模式**: {如果识别出设计模式，说明}

## 基本信息

| 属性 | 值 |
|------|-----|
| 混淆名 | {obfuscated_name} |
| 还原名 | {restored_name} |
| 父类 | {superclass} |
| 接口 | {interfaces} |
| 标签 | {tags} |

## 依赖关系

### 直接依赖 (已分析)
| 类 | 业务功能 |
|----|----------|
| {dep1} | {dep1的业务概述，来自其 MD 文档} |
| {dep2} | {dep2的业务概述，来自其 MD 文档} |

### 方法体依赖 (已分析)
| 类 | 使用方式 |
|----|----------|
| {method_dep1} | {如何使用这个依赖} |

## 字段

| 混淆名 | 还原名 | 类型 | 业务含义 |
|--------|--------|------|----------|
| {field_a} | {field_renamed} | {type} | {字段用途} |

## 方法

| 混淆名 | 还原名 | 签名 | 业务功能 |
|--------|--------|------|----------|
| {method_a} | {method_renamed} | {signature} | {方法职责} |

## 源码

​```java
// 生成的 Java 源码
{generated_source}
```

## 分析状态

- [x] 拓扑发现 (Phase 3)
- [x] 业务梳理 (Phase 4)
- [x] 依赖已分析 (可引用上下文)
- [x] 标签生成
- [x] 文档生成
- [ ] Java 还原 (Phase 5)
- [ ] 编译通过 (Phase 5)
```

### 4.8 Ralph 状态文件

​```yaml
# .ralph/business-analysis.md
---
active: true
iteration: 47
max_iterations: 2000
completion_promise: "ANALYSIS_COMPLETE"
total_classes: 156
started_at: "2026-03-01T15:00:00Z"
---

# 业务梳理任务

## 进度
- 已梳理: 47
- 待梳理: 109

## 当前任务
正在梳理: Labc; → LocationManager

## 完成条件
所有类梳理完成 + 文档生成

## 规则
- 拓扑逆序 (叶子 → 根)
- 不生成 Java 代码
```

---

## Phase 5: 逆向还原 (Ralph 循环)

### 5.0 交互式询问 Android 项目路径

**在 Phase 5 开始前，必须使用 `AskUserQuestion` 询问 Android 项目路径**：

```json
{
  "questions": [{
    "question": "逆向还原需要一个 Android 项目用于编译验证，请选择项目路径：",
    "header": "Android项目",
    "options": [
      {
        "label": "使用现有项目",
        "description": "选择已有的 Android 项目目录"
      },
      {
        "label": "创建新项目",
        "description": "在指定位置创建新的 Android 项目"
      },
      {
        "label": "跳过编译验证",
        "description": "只生成源码，不进行编译验证"
      }
    ]
  }]
}
```

**后续根据用户选择处理**，不预设具体目录结构。

### 5.1 目标

**基于业务梳理的结果，还原 Java 源码并编译验证**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  逆向还原任务                                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  输入: 业务梳理结果 (Phase 4 产出，每个类都有 MD 文档)                       │
│  输出: 可编译的 Java 源码                                                    │
│                                                                             │
│  策略: 拓扑逆序 (从叶子到根) - 与业务梳理顺序相同                            │
│                                                                             │
│  核心原则:                                                                   │
│    业务已经梳理完成 → 还原代码时理解业务逻辑 → 命名更准确                    │
│                                                                             │
│  单类处理流程:                                                               │
│    1. 选择: 依赖都已还原的类 (叶子优先)                                      │
│    2. 还原: 获取反编译代码 → 应用重命名 → 生成 Java 源码                    │
│    3. 编译: 验证代码可编译                                                   │
│    4. 修复: 如果编译失败，分析错误并修复                                     │
│    5. 标记: restored=1, compiled=1                                          │
│                                                                             │
│  完成条件: 所有类还原完成 + 编译通过                                         │
│                                                                             │
│  注意: 此阶段不生成 MD 文档，文档在 Phase 4 已完成                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 为什么业务梳理后再还原

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  业务理解指导代码还原                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Phase 4 (业务梳理) 已经完成:                                                │
│    ✓ 每个类都有业务分析文档                                                  │
│    ✓ 每个类都有标签 (类型、模块、功能)                                       │
│    ✓ 依赖关系已梳理，业务逻辑链条清晰                                        │
│                                                                             │
│  Phase 5 (逆向还原) 的优势:                                                  │
│    • 还原代码时已经理解业务，命名更准确                                      │
│    • 可以引用 MD 文档中的业务说明                                            │
│    • 标签帮助选择合适的还原策略                                              │
│    • 编译错误更容易理解和修复                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Ralph 循环命令

```bash
/ralph-loop "
  逆向还原任务

  输入: 业务梳理结果 (每个类都有 MD 文档)

  策略: 拓扑逆序 (叶子 → 根)

  单类处理流程:
  1. 选择: 依赖都已还原的类 (叶子优先)
  2. 参考: 读取该类的 MD 文档 (业务已梳理)
  3. 还原: 生成 Java 源码
  4. 编译: 验证可编译
  5. 修复: 如果失败，分析错误并修复
  6. 标记: restored=1, compiled=1

  完成条件: 所有类还原完成 + 编译通过
  完成时输出: <promise>RESTORE_COMPLETE</promise>
" --completion-promise "RESTORE_COMPLETE" --max-iterations 2000
```

### 5.4 单类还原流程

```
┌─────────────────────────────────────────────────────────────────┐
│  单类还原流程                                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  前提: 当前类的所有依赖都已还原                                  │
│       当前类的业务已梳理 (Phase 4)                               │
│                                                                 │
│  1. 选择下一个可还原的类                                         │
│     └─→ 查询 SQLite: WHERE restored=0 AND 依赖都已 restored     │
│                                                                 │
│  2. 读取业务文档                                                 │
│     └─→ 读取 notes/{ClassName}.md                               │
│     └─→ 获取业务逻辑、标签、依赖关系                            │
│                                                                 │
│  3. 生成 Java 源码                                               │
│     └─→ get_class_decompiled_code()                             │
│     └─→ get_rename() (获取已重命名的符号)                       │
│     └─→ 应用重命名，修复语法问题                                 │
│     └─→ 写入 Android 项目源码目录                               │
│                                                                 │
│  4. 编译验证                                                     │
│     └─→ 根据用户项目类型执行编译命令                             │
│                                                                 │
│  5. 处理编译结果                                                  │
│     ├─→ 通过:                                                    │
│     │     • 更新 SQLite: restored=1, compiled=1                 │
│     │     • 继续下一个类                                         │
│     │                                                           │
│     └─→ 失败:                                                    │
│           • 分析编译错误                                         │
│           • 参考业务文档理解意图                                 │
│           • 修复源码                                             │
│           • 重新编译                                             │
│                                                                 │
│  注意: 不生成 MD 文档，文档在 Phase 4 已完成                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.5 Ralph 状态文件

​```yaml
# .ralph/reverse-restore.md
---
active: true
iteration: 1
max_iterations: 2000
completion_promise: "RESTORE_COMPLETE"
total_classes: 156
started_at: "2026-03-01T15:00:00Z"
---

# 逆向还原任务

## 进度
- 已还原: 47
- 待还原: 109
- 编译通过: 45
- 编译失败: 2 (修复中)

## 当前任务
正在还原: Labc; → LocationManager

## 完成条件
所有类还原完成且编译通过

## 规则
- 拓扑逆序还原
- 每个类必须编译通过
- 不生成 MD 文档 (Phase 4 已完成)
```

---

## 数据库表结构完整版

```sql
-- 类信息表
CREATE TABLE classes (
    class_sig TEXT PRIMARY KEY,      -- 类签名 (混淆名)
    superclass TEXT,                 -- 父类
    interfaces TEXT,                 -- 接口列表 (JSON)
    fields TEXT,                     -- 字段列表 (JSON)
    methods TEXT,                    -- 方法列表 (JSON)
    renamed TEXT,                    -- 还原后的类名
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 依赖关系表
CREATE TABLE dependencies (
    id INTEGER PRIMARY KEY,
    from_class TEXT NOT NULL,        -- 依赖方
    to_class TEXT NOT NULL,          -- 被依赖方
    dep_type TEXT NOT NULL,          -- extends, implements, field, method_body
    discovered_at TIMESTAMP,
    UNIQUE(from_class, to_class, dep_type)
);

-- 分析状态表
CREATE TABLE analysis_status (
    class_sig TEXT PRIMARY KEY,
    discovered BOOLEAN DEFAULT 0,    -- Phase 3: 已发现
    analyzed BOOLEAN DEFAULT 0,      -- Phase 4: 已梳理业务
    documented BOOLEAN DEFAULT 0,    -- Phase 4: 已生成文档
    restored BOOLEAN DEFAULT 0,      -- Phase 5: 已还原代码
    compiled BOOLEAN DEFAULT 0,      -- Phase 5: 编译通过
    in_degree INTEGER DEFAULT 0,     -- 入度
    out_degree INTEGER DEFAULT 0,    -- 出度
    leaf_node BOOLEAN DEFAULT 0,     -- 是否叶子节点
    tags TEXT,                       -- 标签列表 (JSON 数组)
    module TEXT,                     -- 所属模块
    UNIQUE(class_sig)
);

-- 重命名表
CREATE TABLE renames (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,              -- class, method, field
    obfuscated TEXT NOT NULL,        -- 混淆名
    renamed TEXT NOT NULL,           -- 还原名
    note TEXT,                       -- 备注
    created_at TIMESTAMP,
    UNIQUE(type, obfuscated)
);

-- 创建索引
CREATE INDEX idx_deps_from ON dependencies(from_class);
CREATE INDEX idx_deps_to ON dependencies(to_class);
CREATE INDEX idx_status_restored ON analysis_status(restored);
CREATE INDEX idx_status_leaf ON analysis_status(leaf_node);
```

---

## 查询示例

```sql
-- 获取下一个可分析的类 (所有依赖已分析)
SELECT a.class_sig
FROM analysis_status a
WHERE a.analyzed = 0
  AND NOT EXISTS (
    SELECT 1 FROM dependencies d
    JOIN analysis_status dep ON d.to_class = dep.class_sig
    WHERE d.from_class = a.class_sig
      AND dep.analyzed = 0
      AND NOT is_system_class(d.to_class)
  )
ORDER BY a.out_degree ASC;  -- 优先分析叶子节点

-- 获取所有叶子节点
SELECT class_sig FROM analysis_status
WHERE leaf_node = 1 AND analyzed = 0;

-- 获取分析进度
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN analyzed THEN 1 ELSE 0 END) as analyzed,
    SUM(CASE WHEN documented THEN 1 ELSE 0 END) as documented,
    SUM(CASE WHEN compiled THEN 1 ELSE 0 END) as compiled
FROM analysis_status;

-- ===== 标签相关查询 =====

-- 按标签检索类
SELECT class_sig, tags FROM analysis_status
WHERE tags LIKE '%proto%';

-- 按模块检索类
SELECT class_sig, module FROM analysis_status
WHERE module = 'location';

-- 获取所有 proto 类
SELECT class_sig, module FROM analysis_status
WHERE tags LIKE '%proto%';

-- 获取某个模块下的所有数据类
SELECT class_sig FROM analysis_status
WHERE module = 'fusion' AND tags LIKE '%data_class%';

-- 统计各标签数量
SELECT tags, COUNT(*) as count
FROM analysis_status
WHERE tags IS NOT NULL
GROUP BY tags;

-- 统计各模块类数量
SELECT module, COUNT(*) as count
FROM analysis_status
WHERE module IS NOT NULL
GROUP BY module;
```

---

## 完整命令序列

```bash
# ===== Phase 1: 初始化 =====
# AI 使用 AskUserQuestion 询问工作区路径
# 调用 init_knowledge_base()

# ===== Phase 2: 数据导入 =====
# 用户在 JEB 中运行 ExportDeps.py
# 调用 import_from_jeb_json()

# ===== Phase 3: 拓扑发现 =====
/ralph-loop "
  拓扑发现任务

  种子类: Lfvxn;
  目标: BFS 探索所有依赖节点
  存储: 只写数据库，不生成 MD

  完成条件: 队列为空
  完成时输出: <promise>TOPOLOGY_COMPLETE</promise>
" --completion-promise "TOPOLOGY_COMPLETE" --max-iterations 1000

# ===== Phase 4: 业务梳理 =====
/ralph-loop "
  业务梳理任务

  输入: 依赖图 (SQLite)
  策略: 拓扑逆序 (叶子 → 根)

  单类流程:
    1. 分析业务功能 (引用依赖类的功能说明)
    2. 识别标签 (类型、模块、功能)
    3. 生成 MD 文档

  注意: 不生成 Java 代码

  完成条件: 所有类梳理完成 + 文档生成
  完成时输出: <promise>ANALYSIS_COMPLETE</promise>
" --completion-promise "ANALYSIS_COMPLETE" --max-iterations 2000

# ===== Phase 5: 逆向还原 =====
# 先询问 Android 项目路径
# AI 使用 AskUserQuestion 询问 Android 项目路径

/ralph-loop "
  逆向还原任务

  输入: 业务梳理结果 (每个类都有 MD 文档)
  策略: 拓扑逆序 (叶子 → 根)

  单类流程:
    1. 读取业务文档 (Phase 4 产出)
    2. 生成 Java 源码
    3. 编译验证

  完成条件: 所有类还原完成 + 编译通过
  完成时输出: <promise>RESTORE_COMPLETE</promise>
" --completion-promise "RESTORE_COMPLETE" --max-iterations 2000
```

---

## 总结：v2 改进点

| 方面 | v1 设计 | v2 设计 |
|-----|--------|--------|
| 阶段数 | 4 阶段 | **5 阶段** |
| MD 文件 | 拓扑阶段就写 | **业务梳理阶段才写** |
| 数据存储 | 文件 + 数据库 | **数据库优先** |
| Phase 3 目标 | 发现 + 分析 | **只发现依赖** |
| Phase 4 目标 | 还原 + 分析 | **业务梳理 + 文档** |
| Phase 5 目标 | - | **逆向还原 + 编译** |
| 业务理解 | 还原时分析 | **梳理时理解，还原时应用** |
| Android 项目 | 初始化时预设 | **Phase 5 询问用户** |

## 核心优势

1. **先理解业务，再还原代码** - 业务梳理指导代码还原
2. **数据一致性** - 数据库是唯一真相来源
3. **文档质量** - 依赖梳理后生成，可引用上下文
4. **任务清晰** - 每个阶段职责单一
5. **标签系统** - 便于检索和分类
6. **灵活适配** - Android 项目路径和结构由用户指定
