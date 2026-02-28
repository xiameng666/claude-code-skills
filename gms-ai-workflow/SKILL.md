---
name: gms-ai-workflow
description: 当用户要求 "分析类" "逆向分析GMS" "JEB分析" "使用JEBMCP分析" 时使用此 skill
---

# GMS 逆向分析 AI Workflow Skill

## 触发条件

当用户要求分析 GMS/APK 中的类、模块、功能时使用此 skill。
典型场景：类身份识别、字段重命名、方法重命名、模块分析、报告生成。

---

## 一键安装

### Windows

```powershell
cd C:\Users\你的用户名\.claude\skills\gms-ai-workflow
.\install.ps1
```

### macOS / Linux

```bash
cd ~/.claude/skills/gms-ai-workflow
chmod +x install.sh
./install.sh
```

### 跨平台 (Python)

```bash
python install.py
```

### 卸载

```bash
python install.py --uninstall
```

### 手动配置

如果自动脚本失败，手动添加到 Claude 配置文件：

**配置文件位置**:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**添加内容**:
```json
{
  "mcpServers": {
    "jeb-mcp": {
      "command": "python",
      "args": ["C:\\path\\to\\jebmcp\\src\\server.py"],
      "env": {
        "JEB_HOST": "127.0.0.1",
        "JEB_PORT": "16161",
        "JEB_PATH": "/mcp"
      }
    }
  }
}
```

---

## 前置条件

- JEB Pro 已打开目标 APK/DEX 文件
- JEB MCP Server 已启动（Edit -> Scripts -> MCP，快捷键 Ctrl+Alt+M）
- Claude Desktop 已重启（安装后）

---

## 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│  AI Workflow (本 Skill)                                     │
│  - 定义分析流程、最佳实践                                    │
│  - 指导 AI 如何组合使用 MCP 工具                             │
└─────────────────────────────────────────────────────────────┘
                           ↓ 调用
┌─────────────────────────────────────────────────────────────┐
│  MCP Tools (原子操作)                                       │
│  - get_class_decompiled_code: 获取反编译代码                │
│  - rename_class_with_sync: 重命名类并同步                   │
│  - create_session_report: 生成报告                          │
│  - ...                                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 可用工具映射

### 1. 信息获取工具

| 需求 | MCP 工具 | 说明 |
|------|----------|------|
| 获取反编译代码 | `get_class_decompiled_code` | 获取 Java 伪代码 |
| 获取方法列表 | `get_class_methods` | 所有方法签名 |
| 获取字段列表 | `get_class_fields` | 所有字段信息 |
| 获取接口列表 | `get_class_interfaces` | 实现的接口 |
| 获取类型树 | `get_class_type_tree` | 继承关系 |
| 获取方法调用者 | `get_method_callers` | 谁调用了此方法 |
| 获取字段调用者 | `get_field_callers` | 谁引用了此字段 |

### 2. 重命名工具

| 需求 | MCP 工具 | 说明 |
|------|----------|------|
| 重命名类 | `rename_class_with_sync` | JEB + SQLite + MD 同步 |
| 重命名方法 | `rename_method` | JEB + SQLite 同步 |
| 重命名字段 | `rename_field` | JEB + SQLite 同步 |
| 批量重命名 | `rename_batch_with_sync` | 批量操作 |

### 3. 知识库工具

| 需求 | MCP 工具 | 说明 |
|------|----------|------|
| 初始化知识库 | `init_knowledge_base` | 创建目录结构 |
| 设置知识库路径 | `set_knowledge_dir` | 切换知识库 |
| 导入 JEB 数据 | `import_from_jeb_json` | 批量导入类信息 |
| 获取统计信息 | `get_analysis_stats` | 分析进度 |

### 4. 分析报告工具

| 需求 | MCP 工具 | 说明 |
|------|----------|------|
| 准备模块上下文 | `prepare_module_context` | 获取已分析信息 |
| 生成模块报告 | `generate_module_report` | 模块级报告 |
| 生成会话报告 | `create_session_report` | 会话总结 |

---

## 完整分析流程

### Phase 0: 初始化（首次使用）

**目标**：确保知识库已正确初始化。

```
1. 检查知识库状态
   → get_analysis_stats()
   → 如果 total_classes == 0，需要初始化

2. 初始化知识库（如果需要）
   → init_knowledge_base(knowledge_dir, project_name)

3. 导入 JEB 类信息（如果需要）
   → 在 JEB 中运行 ExportDeps.py 导出 JSON
   → import_from_jeb_json(json_path)
```

### Phase 1: 类身份识别

**目标**：确定类的真实名称和用途。

```
1. 获取反编译代码
   → get_class_decompiled_code(class_signature)

2. 身份识别线索（按优先级）：
   a. toString() 返回值 → "FusionEngine"
   b. 类注解 → @Deprecated, @hide
   c. 字符串常量 → "LocationProvider", "fused"
   d. 实现的接口 → LocationListener, Callback
   e. 依赖的类 → 已知的 GMS 类

3. 获取更多上下文
   → get_class_interfaces(class_signature)
   → get_class_methods(class_signature)
   → get_class_fields(class_signature)
```

**命名规范**：
- 完整包名：`com.google.android.location.fused.FusionEngine`
- 简短名称：`FusionEngine`

### Phase 2: 类重命名

**目标**：将混淆名重命名为真实名称。

```
→ rename_class_with_sync(class_name, new_name, note)

注意：
- note 参数记录重命名原因/证据
- 会自动同步到 SQLite 数据库
- 会自动创建/更新 MD 文件
```

**类名格式支持**：
| 输入格式 | 示例 | 自动转换 |
|----------|------|----------|
| JNI | `Lfvxn;` | 直接使用 |
| Java | `com.example.Foo` | → `Lcom/example/Foo;` |
| 简短 | `fvxn` | → `Lfvxn;` |

### Phase 3: 字段分析

**目标**：识别关键字段并重命名。

```
1. 获取字段列表
   → get_class_fields(class_signature)

2. 分析字段类型和用途：
   - Location 类型 → 可能是位置缓存
   - Context 类型 → 应用上下文
   - Handler/Looper 类型 → 线程相关
   - boolean 类型 → 状态标志

3. 命名风格：
   - 成员变量：mPrefix + 描述 (mLocationCache)
   - 静态常量：UPPER_CASE (FLUSH_INTERVAL_MS)
   - 布尔标志：is/has 前缀 (isRunning, hasRequest)

4. 批量重命名字段
   → rename_field(class_name, field_name, new_name, note)
```

### Phase 4: 方法分析

**目标**：识别关键方法并重命名。

```
1. 获取方法列表
   → get_class_methods(class_signature)

2. 分析方法特征：
   - 参数类型 → Location, Bundle, Callback
   - 返回值 → void, boolean, Location
   - 调用者 → get_method_callers() 了解用途

3. 命名推断：
   - 回调方法：on 前缀 (onLocationUpdate, onProviderChanged)
   - 获取方法：get 前缀 (getFusedLocation)
   - 设置方法：set 前缀 (setUpdateInterval)
   - 状态检查：is/has 前缀 (hasActiveRequest)

4. 重命名方法
   → rename_method(class_name, method_sig, new_name, note)

注意：method_sig 需要完整签名，如：
   - "a(J)V" → 单参数
   - "a(JLgpvs;)V" → 多参数
```

### Phase 5: 接口分析

**目标**：分析类实现的接口。

```
1. 获取接口列表
   → get_class_interfaces(class_signature)

2. 分析每个接口：
   - 获取接口的方法定义
   - 推断接口用途
   - 重命名接口

3. 常见 GMS 接口模式：
   | 接口后缀 | 用途 |
   |----------|------|
   | Listener | 事件回调 |
   | Callback | 异步回调 |
   | Handler | 消息处理 |
   | Provider | 服务提供者 |
   | Manager | 资源管理 |
```

### Phase 6: 关联分析

**目标**：分析与当前类相关的其他类。

```
1. 分析字段类型中的未知类
   → 如果字段类型是混淆名，分析该类

2. 分析方法参数/返回值中的未知类

3. 分析调用者
   → get_method_callers(class_name, method_name)
   → get_field_callers(class_name, field_name)

4. 构建类关系图
```

### Phase 7: 报告生成

**目标**：记录分析结果。

```
1. 创建会话报告
   → create_session_report(
       seed_class,           # 起始类
       analyzed_classes,     # 分析过的类 JSON 数组
       findings,             # 发现列表 JSON 数组
       renames,              # 重命名列表 JSON 数组
       issues,               # 问题列表 JSON 数组
       next_steps            # 下一步 JSON 数组
     )

2. 生成模块报告（如果分析了多个相关类）
   → generate_module_report(
       module_name,          # 如 "gms/location"
       classes,              # 类列表逗号分隔
       structure             # mermaid 类图（可选）
     )
```

---

## 分析决策树

```
开始分析类 X
    │
    ├─→ 知识库已初始化?
    │       │
    │       ├─→ 否 → init_knowledge_base()
    │       │        → import_from_jeb_json()
    │       │
    │       └─→ 是 ↓
    │
    ├─→ 获取类信息
    │       → get_class_decompiled_code()
    │       → get_class_methods()
    │       → get_class_fields()
    │       → get_class_interfaces()
    │
    ├─→ 身份识别
    │       │
    │       ├─→ toString() 有信息? → 使用作为类名
    │       │
    │       ├─→ 实现已知接口? → 推断功能
    │       │
    │       └─→ 依赖已知类? → 推断模块
    │
    ├─→ 重命名
    │       → rename_class_with_sync()
    │       → rename_field() x N
    │       → rename_method() x N
    │
    ├─→ 关联分析
    │       │
    │       ├─→ 字段类型是混淆类? → 添加到待分析列表
    │       │
    │       └─→ 方法调用者? → 理解使用场景
    │
    └─→ 生成报告
            → create_session_report()
```

---

## 最佳实践

### 1. 命名置信度

| 置信度 | 条件 | 示例 |
|--------|------|------|
| **high** | toString()、注解、字符串明确 | `FusionEngine` (toString 返回) |
| **medium** | 基于接口/依赖推断 | `LocationEngine` (实现 LocationListener) |
| **low** | 纯粹猜测 | `Manager` (无明确线索) |

### 2. MD 文件模板

```markdown
---
obfuscated: "Lfvxn;"
renamed: "com.google.android.location.fused.FusionEngine"
confidence: high
tags: [location, fused-provider, engine, gms]
---

## 业务功能

<!-- 一句话描述 -->

## 关键字段

| 混淆 | 重命名 | 说明 |
|------|--------|------|
| e | lastGpsLocation | 最后GPS位置 |

## 关联

- [[gpus_LocationEngine]] - 核心引擎
```

### 3. 避免重复分析

```
开始前检查：
→ prepare_module_context([class_name])
→ 查看已有分析信息
→ 避免重复工作
```

---

## 实战检查清单

- [ ] 知识库已初始化
- [ ] 已获取类反编译代码
- [ ] 已识别类真实名称（有证据支持）
- [ ] 已重命名类
- [ ] 已分析并重命名关键字段
- [ ] 已分析并重命名关键方法
- [ ] 已分析实现的接口
- [ ] 已识别关联类
- [ ] 已生成会话报告
- [ ] MD 文件已更新

---

## 常见问题

### Q: JEB 方法重命名失败？

A: 确保使用完整方法签名：
- 错误：`a`
- 正确：`a(J)V` 或 `a(Landroid/location/Location;)V`

### Q: 字段重命名格式错误？

A: 字段名不需要类前缀：
- 错误：`Lfvxn;.e`
- 正确：`e`

### Q: 知识库统计为 0？

A: 需要先导入 JEB 数据：
```
1. JEB 中运行 ExportDeps.py
2. import_from_jeb_json("~/jeb-deps.json")
```
