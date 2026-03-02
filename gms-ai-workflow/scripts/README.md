# Scripts 目录说明

本目录包含 GMS 逆向分析工作流的辅助脚本。

## 脚本列表

| 脚本 | 用途 |
|-----|------|
| `exportDepsFromJeb.py` | 在 JEB 中运行，导出所有类的依赖关系（结构性 + 方法体）到 JSON |
| `depsJson2db.py` | 将 JEB 导出的 JSON 文件导入到 SQLite 数据库 |
| `extract_class_list.py` | 从数据库中提取已发现的类列表，保存到 class_list.txt |
| `exportDecompiledFromJeb.py` | 在 JEB 中运行，根据 class_list.txt 导出反编译的 Java 代码 |
| `build_topology.py` | 从根节点构建依赖子图并进行拓扑排序，生成分层还原顺序 |
| `dbCheckStatus.py` | 检查数据库状态，显示各阶段的进度统计 |
| `queryExamples.py` | 提供常用的 SQL 查询示例，用于分析依赖关系 |
| `testMethodBodyDeps.py` | 测试方法体依赖提取功能，验证字节码分析的准确性 |

## 使用顺序

```
Phase 2: 数据导入
  1. exportDepsFromJeb.py (在 JEB 中运行)
  2. depsJson2db.py (导入到数据库)

Phase 3: 拓扑发现
  - (已简化，直接查询数据库)

Phase 4: 业务梳理
  - (Ralph 循环)

导出反编译代码 (Phase 4 完成后):
  3. extract_class_list.py --db "path/to/db" --output "class_list.txt"
  4. exportDecompiledFromJeb.py (在 JEB 中运行，读取 class_list.txt)

Phase 5: 逆向还原
  5. build_topology.py (构建子图 + 拓扑排序)
  - (Ralph 循环按层次还原，参考导出的代码)

辅助工具:
  - dbCheckStatus.py (随时检查进度)
  - queryExamples.py (学习 SQL 查询)
  - testMethodBodyDeps.py (调试依赖提取)
```

## 详细文档

- `exportDepsFromJeb.py`: 参见 JEB 脚本注释
- `build_topology.py`: 参见 `../docs/topology-script-usage.md`
- 其他脚本: 参见各脚本内的注释
