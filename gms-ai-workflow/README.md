# gms-ai-workflow Skill

GMS 逆向分析 AI 工作流 - 自包含的工具包

## 目录结构

```
gms-ai-workflow/
├── SKILL.md           # Skill 主文件（AI 工作流文档）
├── README.md          # 本文件
└── jebmcp/            # JEB MCP 源码（软链接或复制）
    ├── src/
    │   ├── server.py
    │   ├── ai_workflow/
    │   └── traditional/
    └── requirements.txt
```

## 快速开始

### 1. 安装

```bash
# Windows
claude mcp add -s user jeb-mcp -- python "path\.claude\skills\gms-ai-workflow\jebmcp"
```

### 2. 启动 JEB MCP Server

在 JEB Pro 中：
1. 打开目标 APK/DEX 文件
2. 菜单: Edit -> Scripts -> MCP
3. 快捷键: Ctrl+Alt+M (Windows/Linux) 或 Cmd+Option+M (macOS)

### 3. 重启 Claude Desktop

### 4. 开始使用

```
使用 /gms-ai-workflow
```

