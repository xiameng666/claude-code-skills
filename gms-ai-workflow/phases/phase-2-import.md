# Phase 2: 数据导入

## 目标

将 JEB 导出的类依赖 JSON 导入到 SQLite 数据库。

## 前提条件

- Phase 1 已完成 (工作区已初始化)
- JEB 项目已加载

## 用户操作

**在 JEB 中手动执行**：

1. `File → Scripts → Run Script...`
2. 选择：`{skill_dir}/scripts/ExportDeps.py`
3. 输出路径：`{knowledge_dir}/imports/jeb-deps.json`

## AI 执行

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: 数据导入流程                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 检查 JSON 文件存在                                          │
│     └─→ {knowledge_dir}/imports/jeb-deps.json                  │
│                                                                 │
│  2. 导入到 SQLite                                                │
│     └─→ 调用 mcp__jeb-mcp__import_from_jeb_json()              │
│                                                                 │
│  3. 验证导入成功                                                 │
│     └─→ 调用 mcp__jeb-mcp__get_analysis_stats()                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 导入内容

| 数据 | 存储位置 |
|------|---------|
| 类签名 | classes 表 |
| 父类/接口 | classes 表 |
| 字段信息 | classes 表 (JSON) |
| 方法签名 | classes 表 (JSON) |
| 依赖关系 | dependencies 表 |
| 分析状态 | analysis_status 表 |

## 输出

```
✓ JSON 文件: jeb-deps.json
✓ 导入类数: {class_count}
✓ 导入依赖: {dep_count}
✓ 创建 MD 模板: {template_count}

下一步: Phase 3 - 拓扑发现
```

## 注意事项

- 此阶段**不**生成 MD 分析文件，只创建模板
- 详细的 MD 文档在 Phase 4 (业务梳理) 时生成
- 如果导入失败，检查 JSON 格式是否正确
