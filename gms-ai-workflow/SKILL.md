---
name: gms-ai-workflow
description: 当用户要求 "分析类" "逆向分析GMS" "JEB分析" "使用JEBMCP分析" 时使用此 skill
---

# GMS 逆向分析 AI Workflow

## 概述

此 skill 提供完整的 GMS 逆向分析工作流，包含 5 个阶段 + 知识库管理。**调用此 skill 时，首先询问用户想要执行哪个阶段**。

## 统一入口

**当用户调用此 skill 时，必须首先使用 `AskUserQuestion` 询问用户想要执行哪个阶段**：

```json
{
  "questions": [{
    "question": "请选择要执行的操作：",
    "header": "工作流",
    "options": [
      {
        "label": "Phase 1: 初始化",
        "description": "创建工作区目录，初始化 SQLite 数据库"
      },
      {
        "label": "Phase 2: 数据导入",
        "description": "导入 JEB 导出的类依赖 JSON 到 SQLite"
      },
      {
        "label": "Phase 3: 拓扑发现",
        "description": "Ralph 循环 - BFS 探索所有依赖节点"
      },
      {
        "label": "Phase 4: 业务梳理",
        "description": "Ralph 循环 - 叶子到根，分析业务，生成 MD 文档"
      },
      {
        "label": "Phase 5: 逆向还原",
        "description": "Ralph 循环 - 还原 Java 源码，编译验证"
      },
      {
        "label": "知识库管理",
        "description": "查看当前知识库统计信息、进度、阶段状态"
      }
    ]
  }]
}
```

---

## 知识库管理

**独立于 5 个阶段之外，用于查看当前知识库状态**

### 显示内容

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           知识库状态                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  工作区路径: C:\Users\xxx\gms-knowledge                                     │
│  当前阶段:   Phase 4 (业务梳理)                                              │
│  上次更新:   2026-03-01 15:30:00                                            │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  进度统计                                                                   │
│                                                                             │
│  ┌─────────────────┬────────┬────────┬───────────────────────────────────┐ │
│  │ 阶段            │ 状态   │ 数量   │ 进度                              │ │
│  ├─────────────────┼────────┼────────┼───────────────────────────────────┤ │
│  │ Phase 3: 发现   │ ✓ 完成 │ 156    │ ████████████████████ 100%         │ │
│  │ Phase 4: 梳理   │ ◐ 进行 │ 47/156 │ ██████░░░░░░░░░░░░░░  30%         │ │
│  │ Phase 5: 还原   │ ○ 待办 │ 0/156  │ ░░░░░░░░░░░░░░░░░░░░   0%         │ │
│  └─────────────────┴────────┴────────┴───────────────────────────────────┘ │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  标签统计                                                                   │
│                                                                             │
│  类型标签: proto: 23, data_class: 15, interface: 8, enum: 3                │
│  模块标签: location: 18, fusion: 12, auth: 5                               │
│  功能标签: callback: 10, handler: 8, builder: 5                            │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Ralph 循环状态                                                             │
│                                                                             │
│  Phase 4 循环: 活跃                                                         │
│  当前迭代:   47                                                             │
│  最大迭代:   2000                                                           │
│  开始时间:   2026-03-01 10:00:00                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 实现方式

```python
# 调用 get_analysis_stats() 获取统计
# 读取 .ralph/ 目录下的状态文件
# 查询 SQLite 获取标签统计

def show_knowledge_status():
    # 1. 工作区路径 (从配置或环境变量)
    knowledge_dir = get_knowledge_dir()

    # 2. 当前阶段 (检查 Ralph 状态文件)
    current_phase = detect_current_phase()

    # 3. 进度统计 (查询 SQLite)
    stats = get_analysis_stats()

    # 3.1 Phase 3: 已发现
    discovered = stats['discovered']

    # 3.2 Phase 4: 已梳理 + 已文档
    analyzed = stats['analyzed']
    documented = stats['documented']

    # 3.3 Phase 5: 已还原 + 已编译
    restored = stats['restored']
    compiled = stats['compiled']

    # 4. 标签统计 (查询 SQLite)
    tag_stats = query_tag_statistics()

    # 5. Ralph 循环状态 (读取 .ralph/ 目录)
    ralph_status = get_ralph_status()

    return format_status_report(...)
```

### SQL 查询

```sql
-- 进度统计
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN discovered THEN 1 ELSE 0 END) as discovered,
    SUM(CASE WHEN analyzed THEN 1 ELSE 0 END) as analyzed,
    SUM(CASE WHEN documented THEN 1 ELSE 0 END) as documented,
    SUM(CASE WHEN restored THEN 1 ELSE 0 END) as restored,
    SUM(CASE WHEN compiled THEN 1 ELSE 0 END) as compiled
FROM analysis_status;

-- 标签统计
SELECT tags, COUNT(*) as count
FROM analysis_status
WHERE tags IS NOT NULL
GROUP BY tags;

-- 模块统计
SELECT module, COUNT(*) as count
FROM analysis_status
WHERE module IS NOT NULL
GROUP BY module;
```

### 阶段检测逻辑

```python
def detect_current_phase():
    """检测当前处于哪个阶段"""

    # 检查 Ralph 循环状态
    if has_active_ralph('topology-discovery'):
        return 'Phase 3 (拓扑发现)'
    if has_active_ralph('business-analysis'):
        return 'Phase 4 (业务梳理)'
    if has_active_ralph('reverse-restore'):
        return 'Phase 5 (逆向还原)'

    # 根据 SQLite 状态判断
    stats = get_analysis_stats()

    if stats['discovered'] == 0:
        return 'Phase 2 (数据导入) - 待执行'
    if stats['analyzed'] < stats['discovered']:
        return 'Phase 4 (业务梳理) - 待执行/进行中'
    if stats['restored'] < stats['analyzed']:
        return 'Phase 5 (逆向还原) - 待执行/进行中'

    return '已完成'
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
```

---

## Phase 1: 初始化

### 询问路径

**必须使用 `AskUserQuestion` 询问工作区路径**：

```json
{
  "questions": [{
    "question": "请选择工作区存储位置：",
    "header": "工作区路径",
    "options": [
      {"label": "文档目录 (推荐)", "description": "C:\\Users\\{用户名}\\Documents\\gms-knowledge"},
      {"label": "用户目录", "description": "C:\\Users\\{用户名}\\gms-knowledge"},
      {"label": "自定义路径", "description": "手动输入完整路径"}
    ]
  }]
}
```

### 执行步骤

1. 检查 JEB MCP 连接 (`ping`)
2. 创建目录结构
3. 初始化 SQLite 数据库 (`init_knowledge_base`)

### 目录结构

```
gms-knowledge/
├── gms-rename.db          # SQLite 数据库
├── notes/                 # (Phase 4) 分析笔记
├── reports/               # 模块报告
├── imports/               # 导入数据
├── logs/                  # 运行日志
└── .ralph/                # Ralph 循环状态
```

---

## Phase 2: 数据导入

### 用户操作

在 JEB 中运行：
1. `File → Scripts → Run Script...`
2. 选择：`{skill_dir}/scripts/ExportDeps.py`
3. 输出路径：`{knowledge_dir}/imports/jeb-deps.json`

### AI 执行

调用 `import_from_jeb_json` 将 JSON 导入 SQLite。

---

## Phase 3: 拓扑发现

### 目标

**BFS 探索所有依赖节点，只写数据库**

### 询问种子类

```json
{
  "questions": [{
    "question": "请输入种子类（根节点）：",
    "header": "种子类",
    "options": [
      {"label": "Lfvxn;", "description": "FusionEngine (推测)"},
      {"label": "自定义", "description": "手动输入类签名"}
    ]
  }]
}
```

### Ralph 循环

```bash
/ralph-loop "
  拓扑发现任务

  种子类: {seed_class}
  目标: BFS 探索所有依赖节点
  存储: 只写数据库，不生成 MD

  完成条件: 队列为空
  完成时输出: <promise>TOPOLOGY_COMPLETE</promise>
" --completion-promise "TOPOLOGY_COMPLETE" --max-iterations 1000
```

### 双 Agent 协作

```
Agent A: 探索依赖 (父类、接口、字段、方法体)
    ↓
Agent B: 审查是否遗漏 (重点审查方法体依赖)
    ↓
通过: 依赖入库，新类入队
```

---

## Phase 4: 业务梳理

### 目标

**叶子到根，分析业务，生成 MD 文档 + 标签**

### Ralph 循环

```bash
/ralph-loop "
  业务梳理任务

  输入: 依赖图 (SQLite)
  策略: 拓扑逆序 (叶子 → 根)

  单类流程:
  1. 选择: 依赖都已梳理的类 (叶子优先)
  2. 分析: 理解业务功能 (引用依赖类的功能说明)
  3. 标签: 识别类型、模块、功能标签
  4. 文档: 生成 MD

  注意: 此阶段不生成 Java 代码

  完成条件: 所有类梳理完成 + 文档生成
  完成时输出: <promise>ANALYSIS_COMPLETE</promise>
" --completion-promise "ANALYSIS_COMPLETE" --max-iterations 2000
```

### 标签系统

| 类型 | 示例 |
|-----|------|
| 类型标签 | proto, data_class, interface, abstract, enum |
| 模块标签 | location, fusion, auth, network |
| 功能标签 | callback, handler, builder, factory, singleton |

---

## Phase 5: 逆向还原

### 询问 Android 项目路径

**必须使用 `AskUserQuestion` 询问**：

```json
{
  "questions": [{
    "question": "逆向还原需要一个 Android 项目用于编译验证，请选择项目路径：",
    "header": "Android项目",
    "options": [
      {"label": "使用现有项目", "description": "选择已有的 Android 项目目录"},
      {"label": "创建新项目", "description": "在指定位置创建新的 Android 项目"},
      {"label": "跳过编译验证", "description": "只生成源码，不进行编译验证"}
    ]
  }]
}
```

### Ralph 循环

```bash
/ralph-loop "
  逆向还原任务

  输入: 业务梳理结果 (每个类都有 MD 文档)
  策略: 拓扑逆序 (叶子 → 根)

  单类流程:
  1. 选择: 依赖都已还原的类 (叶子优先)
  2. 参考: 读取该类的 MD 文档 (业务已梳理)
  3. 还原: 生成 Java 源码
  4. 编译: 验证可编译
  5. 修复: 如果失败，分析错误并修复

  完成条件: 所有类还原完成 + 编译通过
  完成时输出: <promise>RESTORE_COMPLETE</promise>
" --completion-promise "RESTORE_COMPLETE" --max-iterations 2000
```

---

## 阶段详情

详细文档请参考 `phases/` 目录：

| 阶段 | 文件 | 说明 |
|-----|------|------|
| Phase 1 | [phases/phase-1-init.md](phases/phase-1-init.md) | 初始化 - 询问路径，创建目录 |
| Phase 2 | [phases/phase-2-import.md](phases/phase-2-import.md) | 数据导入 - JEB 导出 JSON |
| Phase 3 | [phases/phase-3-topology.md](phases/phase-3-topology.md) | 拓扑发现 - Ralph 循环， BFS |
| Phase 4 | [phases/phase-4-analysis.md](phases/phase-4-analysis.md) | 业务梳理 - Ralph 循环， 生成 MD |
| Phase 5 | [phases/phase-5-restore.md](phases/phase-5-restore.md) | 逆向还原 - Ralph 循环
 编译验证 |

---

## 数据库表结构

```sql
-- 分析状态表
CREATE TABLE analysis_status (
    class_sig TEXT PRIMARY KEY,
    discovered BOOLEAN DEFAULT 0,    -- Phase 3: 已发现
    analyzed BOOLEAN DEFAULT 0,      -- Phase 4: 已梳理业务
    documented BOOLEAN DEFAULT 0,    -- Phase 4: 已生成文档
    restored BOOLEAN DEFAULT 0,      -- Phase 5: 已还原代码
    compiled BOOLEAN DEFAULT 0,      -- Phase 5: 编译通过
    tags TEXT,                       -- 标签列表 (JSON)
    module TEXT,                     -- 所属模块
    ...
);
```

---

## 可用工具

### 信息获取

| 工具 | 说明 |
|------|------|
| `get_class_decompiled_code` | 获取反编译代码 (最重要) |
| `get_class_superclass` | 获取父类 |
| `get_class_interfaces` | 获取接口 |
| `get_class_fields` | 获取字段 |
| `get_class_methods` | 获取方法 |

### 重命名

| 工具 | 说明 |
|------|------|
| `rename_class_with_sync` | 重命名类 |
| `rename_method` | 重命名方法 |
| `rename_field` | 重命名字段 |

### 知识库

| 工具 | 说明 |
|------|------|
| `init_knowledge_base` | 初始化知识库 |
| `import_from_jeb_json` | 导入 JSON |
| `get_analysis_stats` | 获取统计 |

---

## 注意事项

1. **JEB 必须已启动 MCP 服务**：`Edit -> Scripts -> MCP`
2. **项目必须已加载**：APK/DEX 已在 JEB 中打开
3. **路径使用绝对路径**：避免相对路径混淆
4. **Ralph 循环**：Phase 3/4/5 使用 Ralph 机制确保行为持久化

## 参考文档

详细文档请参考：`docs/gms-reverse-workflow-v2.md`
