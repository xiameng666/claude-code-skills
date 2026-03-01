---
name: gms-ai-workflow
description: 当用户要求 "分析类" "逆向分析GMS" "JEB分析" "使用JEBMCP分析" 时使用此 skill
---

# GMS 逆向分析 AI Workflow

## 概述

此 skill 提供完整的 GMS 逆向分析工作流，包括初始化知识库和分析类。

## 快速开始

### 1. 初始化知识库

当用户请求初始化时，AI **必须**使用 `AskUserQuestion` 工具询问知识库目录：

```
AI: 请选择知识库存储位置
    选项1: C:\Users\{用户名}\Documents\gms-knowledge (推荐)
    选项2: C:\Users\{用户名}\gms-knowledge
    选项3: 自定义路径 (用户输入)
```

AI 将执行：
1. 检查 JEB MCP 连接
2. 创建知识库目录结构
3. 初始化 SQLite 数据库

### 2. 手动导出 JEB 类依赖

在 JEB 中运行：
1. `File → Scripts → Run Script...`
2. 选择：`{skill_dir}/scripts/ExportDeps.py`
3. 输出路径设置为：`{knowledge_dir}/imports/jeb-deps.json`

### 3. 导入到知识库

```
用户: 导入 JSON 到知识库
```

### 4. 分析类

```
用户: 分析类 Lfvxn;
```

## 目录结构

```
gms-knowledge/
├── gms-rename.db      # SQLite 数据库
├── notes/             # 分析笔记 (MD 文件)
├── reports/           # 分析报告
├── imports/           # 导入数据 (jeb-deps.json)
└── logs/              # 日志文件
```

## 初始化流程

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 交互式询问                                            │
│  - 使用 AskUserQuestion 询问知识库目录                          │
│  - 提供推荐选项和自定义输入                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: 检查环境                                              │
│  - ping JEB MCP 服务                                            │
│  - 检查是否有已加载的项目                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: 创建知识库                                            │
│  - 调用 init_knowledge_base() 创建目录结构                      │
│  - 创建 SQLite 数据库                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 4: 手动导出 (用户操作)                                   │
│  - 在 JEB 中运行 ExportDeps.py                                  │
│  - 将 JSON 放到 imports/ 目录                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase 5: 导入知识库                                            │
│  - 调用 import_from_jeb_json() 导入到 SQLite                    │
│  - 创建 MD 分析文件                                             │
└─────────────────────────────────────────────────────────────────┘
```

### AskUserQuestion 示例

```json
{
  "questions": [{
    "question": "请选择知识库存储位置：",
    "header": "知识库路径",
    "options": [
      {"label": "文档目录 (推荐)", "description": "C:\\Users\\{用户名}\\Documents\\gms-knowledge"},
      {"label": "用户目录", "description": "C:\\Users\\{用户名}\\gms-knowledge"},
      {"label": "自定义路径", "description": "手动输入完整路径"}
    ]
  }]
}
```

## 自动化分析脚本

### 使用方法

```bash
python scripts/gms-analyze-loop.py --seed Lfvxn; --knowledge-dir C:\Users\xxx\gms-knowledge
```

### 审查通过判定标准

```
┌─────────────────────────────────────────────────────────────────┐
│  Agent B 审查通过条件                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✓ 通过：reported_deps ⊇ actual_deps                           │
│    - Agent A 报告的依赖 包含 代码中实际的所有依赖         │
│                                                                 │
│  ✗ 不通过：存在 missing = actual_deps - reported_deps           │
│    - 发现遗漏的依赖，需要补充                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 依赖去重机制

```python
class AnalysisQueue:
    pending: deque      # 待分析队列
    analyzed: Set[str]  # 已分析集合
    in_queue: Set[str]  # 已入队集合

    def add(self, class_sig):
        # 1. 跳过系统类 (Landroid/*, Ljava/*, etc.)
        if is_system_class(class_sig):
            return False

        # 2. 跳过已分析的类
        if class_sig in self.analyzed:
            return False

        # 3. 跳过已在队列中的类
        if class_sig in self.in_queue:
            return False

        # 4. 添加到队列
        self.pending.append(class_sig)
        self.in_queue.add(class_sig)
        return True
```

### 检查点输出

```
[进度] 迭代 1 | 分析: Lfvxn;
[统计] 待处理: 0 | 已分析: 0
[Agent A] 正在分析 Lfvxn;...
[Agent B] 正在审查分析结果...
[审查] ✓ 通过 - 审查通过，未发现遗漏
[依赖] 发现 90 个 | 新入队: 90
[保存] notes/fvxn.md
```

## 分析流程

### ⚠️ 强制规则 - 图论构造

```
┌─────────────────────────────────────────────────────────────────┐
│  目标：构建以种子类为根的完整依赖图                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 遍历范围：无深度限制，必须到达所有叶子节点                   │
│                                                                 │
│  2. 叶子节点定义：不依赖任何其他混淆类（出度为0）                │
│                                                                 │
│  3. 完成标准：连续 2 轮遍历未发现新的混淆类                      │
│                                                                 │
│  4. 排除规则：java.*, android.* 等框架类不入图                  │
│                                                                 │
│  5. 循环处理：检测到循环依赖时记录，但不中断遍历                 │
│                                                                 │
│  6. 持久化：每处理一个类，必须立即写入 MD 文件                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 检查点（每处理 N 个类必须输出）

```
[进度] 已处理: X | 待处理: Y | 叶子节点: Z | 循环: C
```

### ⚠️ 双 Agent 协作模式（强制）

```
┌─────────────────────────────────────────────────────────────────┐
│  Agent A：分析者                                                 │
│  - 从任务队列获取待分析类                                        │
│  - 调用 JEB MCP 获取类信息                                       │
│  - 提取直接依赖（父类、接口、字段类型）← 不需要审查              │
│  - 提取方法体依赖 ← 需要重点审查！                               │
│  - 生成分析结果，提交给 Agent B 审阅                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Agent B：审查者                                                 │
│  - 重点审查方法体依赖是否遗漏                                    │
│  - 审阅通过 → Agent A 继续下一个类                               │
│  - 审阅不通过 → 说明遗漏项，Agent A 补充分析                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                      从队列取下一个类
```

### 依赖分类（审查重点）

```
┌─────────────────────────────────────────────────────────────────┐
│  直接依赖（不需要审查 - 工具自动获取）                           │
├─────────────────────────────────────────────────────────────────┤
│  ✓ 父类 (get_class_superclass)                                  │
│  ✓ 接口 (get_class_interfaces)                                  │
│  ✓ 字段类型 (get_class_fields)                                  │
│  ✓ 方法签名类型 (get_class_methods)                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  方法体依赖（需要审查 - 容易遗漏！）                             │
├─────────────────────────────────────────────────────────────────┤
│  ⭐ new 语句中的类型                                             │
│  ⭐ 静态方法调用 (Xxx.a(), Xxx.b())                              │
│  ⭐ 方法链调用中的类型                                           │
│  ⭐ 类型转换 (Lxxx;) obj                                        │
│  ⭐ Lambda/匿名类                                                │
│  ⭐ instanceof 检查                                              │
│  ⭐ 异常处理 (catch, throws)                                    │
│  ⭐ 泛型类型参数                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 审阅检查项（Agent B 重点）

```
Agent B 只需要审查方法体依赖是否遗漏：

  1. new 语句是否全部提取？
  2. 静态方法调用是否全部提取？
  3. 类型转换是否全部提取？
  4. Lambda/匿名类是否全部提取？
  5. instanceof 检查是否全部提取？

审阅结果：
  - ✓ 通过 → Agent A 继续下一个类
  - ✗ 不通过 → 说明遗漏的具体类型，Agent A 补充
```

## 可用工具

### 信息获取（必须全部调用）

| 优先级 | 工具 | 说明 | 依赖来源 |
|--------|------|------|----------|
| ⭐⭐⭐ | `get_class_decompiled_code` | **方法体分析（最重要！）** | method_body |
| ⭐⭐⭐ | `get_class_superclass` | 父类 | extends |
| ⭐⭐⭐ | `get_class_interfaces` | 接口列表 | implements |
| ⭐⭐ | `get_class_type_tree` | 完整继承链 | extends/implements |
| ⭐⭐ | `get_class_fields` | 所有字段类型 | field_type |
| ⭐⭐ | `get_class_methods` | 所有方法签名 | method_param/return |

### 重命名

| 工具 | 说明 |
|------|------|
| `rename_class_with_sync` | 重命名类 |
| `rename_method` | 重命名方法 |
| `rename_field` | 命名字段 |

### 知识库

| 工具 | 说明 |
|------|------|
| `init_knowledge_base` | 初始化知识库目录 |
| `set_knowledge_dir` | 设置知识库路径 |
| `import_from_jeb_json` | 导入 JSON 到知识库 |
| `get_analysis_stats` | 获取分析统计 |
| `get_class_md_content` | 获取类 MD 内容 |
| `create_session_report` | 创建分析报告 |

## 方法体分析（强制）

```
从 get_class_decompiled_code 结果中提取：

1. new 语句
   - new Lxxx;()
   - new Lxxx;() { ... }  // 匿名类

2. 方法调用
   - Lxxx;.method()
   - obj.method() 其中 obj 的类型

3. 类型转换
   - (Lxxx;) obj
   - (Lxxx;) method()

4. Lambda/函数式
   - () -> { ... }
   - Lxxx;::method

5. 异常处理
   - catch (Lxxx; e)
   - throws Lxxx;

禁止：
  - 跳过方法体分析
  - 只分析字段/方法签名
```

## 输出格式

```
## 图论分析完成

| 指标 | 值 |
|------|-----|
| 根节点 | Lfvxn; (FusionEngine) |
| 总类数 | N |
| 依赖边数 | M |
| 叶子节点 | K |

### 叶子节点列表
- Lxxx;
- Lyyy;

### 生成的 MD 文件
- notes/fvxn_FusionEngine.md
- notes/xxx.md
```

## 参考文件

- [rules/graph-theory.md](rules/graph-theory.md) - 图论规则定义
- [templates/class-md-template.md](templates/class-md-template.md) - MD 文件格式
- [templates/naming-conventions.md](templates/naming-conventions.md) - 命名规范

## 注意事项

1. **JEB 必须已启动 MCP 服务**：在 JEB 中执行 `Edit -> Scripts -> MCP`
2. **项目必须已加载**：确保 APK/DEX 已在 JEB 中打开
3. **路径使用绝对路径**：避免相对路径引起的混淆
