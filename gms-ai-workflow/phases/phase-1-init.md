# Phase 1: 初始化

## 目标

创建工作区目录结构，初始化 SQLite 数据库。

## 询问路径

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
  }]
}]
}
```

## 执行步骤

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: 初始化流程                                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 检查 JEB MCP 连接                                           │
│     └─→ 调用 mcp__jeb-mcp__ping()                               │
│                                                                 │
│  2. 检查 JEB 项目已加载                                         │
│     └─→ 调用 mcp__jeb-mcp__has_projects()                      │
│                                                                 │
│  3. 创建目录结构                                                 │
│     └─→ 调用 mcp__jeb-mcp__init_knowledge_base()               │
│                                                                 │
│  4. 验证创建成功                                                 │
│     └─→ 检查 gms-rename.db 文件存在                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 创建的目录结构

```
gms-knowledge/
├── gms-rename.db          # SQLite 数据库 (核心)
│   ├── classes            # 类信息表
│   ├── dependencies       # 依赖关系表
│   ├── analysis_status    # 分析状态表
│   └── renames            # 重命名映射表
│
├── notes/                 # (Phase 4 生成) 分析笔记
├── reports/               # 模块报告
├── imports/               # 导入数据
│   └── jeb-deps.json      # (Phase 2 导入)
├── logs/                  # 运行日志
└── .ralph/                # Ralph 循环状态
```

## 环境检查清单

```
□ JEB 已启动
□ JEB MCP 服务已启动 (Edit → Scripts → MCP)
□ APK/DEX 项目已加载
□ 工作区路径可写
```

## 输出

```
✓ JEB MCP 连接成功
✓ 项目已加载: {apk_name}
✓ 工作区创建: {knowledge_dir}
✓ 数据库初始化: gms-rename.db

下一步: Phase 2 - 数据导入
```
