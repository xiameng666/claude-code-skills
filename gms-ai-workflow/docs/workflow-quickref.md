# GMS 逆向分析工作流 - 快速参考

## 四阶段概览

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Phase 1    │    │   Phase 2    │    │   Phase 3    │    │   Phase 4    │
│    初始化    │ ─→ │   数据导入   │ ─→ │   图论分析   │ ─→ │   逆向还原   │
│   (分钟)     │    │   (分钟)     │    │   (小时/天)  │    │   (天/周)    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
      │                   │                   │                   │
  AskUserQuestion     JEB导出           Ralph循环           Ralph循环
  创建目录结构        导入SQLite        双Agent协作         编译验证
                                        探索到叶子          倒推到根
```

## Phase 1: 初始化 (5分钟)

```bash
# AI 使用 AskUserQuestion 询问知识库路径
# 调用 init_knowledge_base() 创建目录结构
```

**产出**: `gms-knowledge/` 目录 + SQLite 数据库

---

## Phase 2: 数据导入 (10分钟)

```bash
# 用户在 JEB 中手动执行:
File → Scripts → Run Script → ExportDeps.py
# 输出到: {knowledge_dir}/imports/jeb-deps.json

# AI 调用:
import_from_jeb_json(json_path)
```

**产出**: SQLite 中填充类信息 + `notes/*.md` 模板

---

## Phase 3: 图论分析 (小时/天级)

```bash
/ralph-loop "
  种子类: Lfvxn;
  目标: 构建完整依赖图，到达所有叶子节点
  模式: 双 Agent (A分析 → B审查)
  完成: 连续2轮无新类 → <promise>GRAPH_COMPLETE</promise>
" --completion-promise "GRAPH_COMPLETE" --max-iterations 500
```

**关键规则**:
- 每个类必须分析方法体依赖 (new, 静态调用, 类型转换)
- 系统类 (java.*, android.*) 不入图
- 每处理一个类立即写 MD 文件

**产出**: 完整依赖图 + 所有类的分析文档

---

## Phase 4: 逆向还原 (天/周级)

```bash
/ralph-loop "
  策略: 从叶子节点开始，拓扑逆序还原
  验证: 每个类还原后必须编译通过
  完成: 所有类编译通过 → <promise>REVERSE_COMPLETE</promise>
" --completion-promise "REVERSE_COMPLETE" --max-iterations 1000
```

**还原顺序**: 叶子 → ... → 根

```
叶子节点 (无依赖)
    ↓
依赖叶子的类
    ↓
... 逐层向上 ...
    ↓
根节点 (种子类)
```

**产出**: `generated/` 目录下的可编译 Java 源码

---

## Ralph 机制原理

```bash
# 本质: while true 循环
while true; do
  claude-code "$PROMPT"
  # Stop hook 拦截退出
  # 检查 completion promise
  # 未完成 → 重新注入 $PROMPT
done
```

**为什么权重不降低?**
- 不依赖对话历史记忆
- 每次迭代都从文件读取完整指令
- 物理上不可能"忘记"

---

## 双 Agent 模式

```
Agent A (分析者)              Agent B (审查者)
      │                             │
      │  获取类信息                  │
      │  提取直接依赖                │
      │  提取方法体依赖              │
      │                             │
      └──────── 提交审阅 ──────────→│
                                    │
                                    │  审查方法体依赖:
                                    │  □ new 语句?
                                    │  □ 静态调用?
                                    │  □ 类型转换?
                                    │  □ Lambda?
                                    │
                   ←── 通过/不通过 ──┘
```

---

## 目录结构

```
gms-knowledge/
├── gms-rename.db          # SQLite (类信息+重命名+依赖)
├── notes/                 # 分析笔记 (*.md)
├── reports/               # 模块报告
├── generated/             # Java 源码 (Phase 4 产出)
├── imports/               # jeb-deps.json
├── logs/                  # 运行日志
├── .ralph/                # Ralph 循环状态
└── compiled/              # .class 文件
```

---

## 命令速查

| 阶段 | 命令/工具 |
|-----|----------|
| 初始化 | `AskUserQuestion` → `init_knowledge_base()` |
| 导入 | `import_from_jeb_json()` |
| 图论 | `/ralph-loop ... --completion-promise "GRAPH_COMPLETE"` |
| 还原 | `/ralph-loop ... --completion-promise "REVERSE_COMPLETE"` |
| 取消 | `/cancel-ralph` |
| 统计 | `get_analysis_stats()` |
| 查询 | `lookup_rename()`, `get_class_md_content()` |
