# 拓扑排序脚本使用说明

## 概述

`build_topology.py` 脚本用于从指定的根节点类构建依赖子图，并进行拓扑排序，生成分层还原顺序。

---

## 前置条件

1. **数据库已初始化**：Phase 1 已完成，SQLite 数据库已创建
2. **依赖已导入**：Phase 2 已完成，JEB 导出的依赖关系已导入数据库
3. **Python 环境**：Python 3.6+

---

## 使用方法

### 基本用法

```bash
cd C:\Users\24151\.claude\skills\gms-ai-workflow\scripts

python build_topology.py \
    --root "Lfvxn;" \
    --db "C:\Users\24151\Documents\gms-knowledge\gms-rename.db"
```

### 参数说明

| 参数 | 必需 | 说明 | 示例 |
|-----|------|------|------|
| `--root` | 是 | 根节点类签名 | `Lfvxn;` |
| `--db` | 是 | SQLite 数据库路径 | `path/to/gms-rename.db` |
| `--max-depth` | 否 | 最大深度限制（-1 不限制） | `5` |
| `--output-dir` | 否 | 输出目录（默认当前目录） | `./output` |

### 示例

#### 示例 1: 不限制深度

```bash
python build_topology.py \
    --root "Lfvxn;" \
    --db "C:\Users\24151\Documents\gms-knowledge\gms-rename.db" \
    --output-dir "./output"
```

#### 示例 2: 限制深度为 5 层

```bash
python build_topology.py \
    --root "Lfvxn;" \
    --db "C:\Users\24151\Documents\gms-knowledge\gms-rename.db" \
    --max-depth 5 \
    --output-dir "./output"
```

---

## 输出文件

脚本会生成 3 个文件：

### 1. `subgraph.json` - 依赖子图

```json
{
  "root": "Lfvxn;",
  "nodes": ["Lfvxn;", "Lfvxo;", "Lfvxp;", ...],
  "edges": [
    {"from": "Lfvxn;", "to": "Lfvxo;"},
    {"from": "Lfvxn;", "to": "Lfvxp;"},
    ...
  ],
  "node_depths": {
    "Lfvxn;": 0,
    "Lfvxo;": 1,
    "Lfvxp;": 1,
    ...
  },
  "stats": {
    "total_nodes": 156,
    "total_edges": 423,
    "max_depth": 8,
    "filtered_system_classes": 89
  }
}
```

### 2. `topology_layers.json` - 拓扑层次

```json
[
  {
    "index": 0,
    "classes": ["Lfvxo;", "Lfvxp;"],
    "count": 2,
    "description": "Layer 0 (叶子节点)"
  },
  {
    "index": 1,
    "classes": ["Lfvxq;", "Lfvxr;"],
    "count": 2,
    "description": "Layer 1"
  },
  ...
  {
    "index": 8,
    "classes": ["Lfvxn;"],
    "count": 1,
    "description": "Layer 8 (根节点)"
  }
]
```

### 3. `topology_report.md` - 可视化报告

Markdown 格式的报告，包含：
- 概览统计
- 每层的类列表
- 统计表格
- Mermaid 依赖图（如果节点数 ≤ 50）

---

## 输出解读

### 控制台输出

```
============================================================
依赖图拓扑分析工具
============================================================
[*] 开始构建子图，根节点: Lfvxn;
[+] 已发现 10 个类，当前深度: 1
[+] 已发现 20 个类，当前深度: 2
[+] 已发现 30 个类，当前深度: 3
...
[+] 子图构建完成:
    - 节点数: 156
    - 边数: 423
    - 最大深度: 8
    - 过滤系统类: 89
[+] 子图已保存: ./output/subgraph.json

[*] 开始拓扑排序...
[+] 初始叶子节点: 23 个
[+] Layer 0: 23 个类
[+] Layer 1: 45 个类
[+] Layer 2: 38 个类
[+] Layer 3: 27 个类
[+] Layer 4: 15 个类
[+] Layer 5: 6 个类
[+] Layer 6: 1 个类
[+] Layer 7: 1 个类
[+] 拓扑排序完成，共 8 层
[+] 拓扑层次已保存: ./output/topology_layers.json
[+] 报告已生成: ./output/topology_report.md

============================================================
分析完成！
============================================================

输出文件:
  - ./output/subgraph.json
  - ./output/topology_layers.json
  - ./output/topology_report.md
```

### 关键指标

| 指标 | 说明 |
|-----|------|
| **节点数** | 子图包含的类总数（不含系统类） |
| **边数** | 依赖关系总数 |
| **最大深度** | 从根节点到最远叶子的距离 |
| **过滤系统类** | 被过滤掉的系统类数量 |
| **拓扑层数** | 还原需要的层次数 |

---

## 常见问题

### Q1: 如何确定根节点类签名？

**A**: 根节点通常是模块的入口类，如：
- `Lfvxn;` - FusionEngine（推测）
- 可以通过 JEB 查看类名，或查询数据库：

```sql
SELECT class_sig, COUNT(*) as dep_count
FROM class_dependencies
GROUP BY class_sig
ORDER BY dep_count DESC
LIMIT 10;
```

入度高的类通常是核心类。

### Q2: 如果子图太大怎么办？

**A**: 使用 `--max-depth` 限制深度：

```bash
python build_topology.py --root "Lfvxn;" --db "..." --max-depth 5
```

这样只分析前 5 层依赖。

### Q3: 如果检测到循环依赖怎么办？

**A**: 脚本会输出警告：

```
[!] 警告: 检测到 3 个类存在循环依赖
```

这些类会被放在最后一层，需要手动处理。

### Q4: 输出的 JSON 文件有什么用？

**A**:
- `subgraph.json`: 可以用于可视化工具（如 Graphviz）
- `topology_layers.json`: 可以被 Ralph 循环读取，按层次还原

---

## 下一步

### 手动验证

1. 查看 `topology_report.md`，理解模块结构
2. 检查每层的类数量是否合理
3. 确认叶子层是否是基础类（如数据类、接口）

### 启动 Phase 5 还原

如果拓扑结构合理，可以启动 Ralph 循环进行还原：

```bash
# 读取 topology_layers.json
# 按层次还原
# 每层完成后生成模块 MD
```

---

## 脚本原理

### 1. 构建子图（BFS）

```
从根节点开始
    ↓
查询数据库获取依赖
    ↓
过滤系统类
    ↓
新类入队
    ↓
重复直到队列为空
```

### 2. 拓扑排序（Kahn 算法）

```
计算每个节点的入度
    ↓
找到所有入度为 0 的节点（叶子）
    ↓
将叶子节点作为 Layer 0
    ↓
移除叶子节点，更新入度
    ↓
重复直到所有节点都被处理
    ↓
反转层次（叶子在前，根在后）
```

### 3. 生成报告

```
统计每层的类数量
    ↓
生成 Markdown 表格
    ↓
（可选）生成 Mermaid 图
```

---

## 故障排查

### 错误: `no such table: class_dependencies`

**原因**: 数据库未初始化或表名错误

**解决**:
1. 检查数据库路径是否正确
2. 确认 Phase 2 已完成（依赖已导入）

### 错误: `no dependencies found for root class`

**原因**: 根节点类没有依赖，或类签名错误

**解决**:
1. 检查类签名格式（如 `Lfvxn;` 而非 `fvxn`）
2. 查询数据库确认类是否存在：

```sql
SELECT * FROM class_dependencies WHERE source_class = 'Lfvxn;' LIMIT 5;
```

### 输出: `子图包含 0 个类`

**原因**: 根节点类不存在或所有依赖都是系统类

**解决**:
1. 确认根节点类签名正确
2. 检查 `SYSTEM_PREFIXES` 是否过滤了太多类

---

## 扩展

### 自定义系统类过滤

编辑脚本中的 `SYSTEM_PREFIXES`：

```python
SYSTEM_PREFIXES = [
    'Ljava/', 'Ljavax/', 'Lkotlin/', 'Lkotlinx/',
    'Landroid/', 'Landroidx/', 'Ldalvik/',
    # 添加自定义过滤规则
    'Lcom/google/android/gms/internal/',
]
```

### 导出 Graphviz DOT 格式

可以扩展脚本，将 `subgraph.json` 转换为 DOT 格式：

```python
def export_dot(subgraph, output_path):
    with open(output_path, 'w') as f:
        f.write('digraph G {\n')
        for edge in subgraph['edges']:
            f.write(f'  "{edge["from"]}" -> "{edge["to"]}";\n')
        f.write('}\n')
```

然后使用 Graphviz 渲染：

```bash
dot -Tpng subgraph.dot -o subgraph.png
```
