# 依赖关系分析工作流文档

## 概述

本文档说明 GMS 逆向分析工作流中的依赖关系获取机制、数据库结构设计，以及结构性依赖与方法体依赖的区别。

---

## 一、依赖关系获取机制

### 1.1 核心思路

**所有依赖关系都在 Phase 2 通过 JEB 脚本一次性导出**，包括：
- 结构性依赖（类声明中的依赖）
- 方法体依赖（方法实现中的依赖）

**关键点**：方法体依赖通过**静态分析 Dalvik 字节码指令**获取，而非反编译代码解析。

### 1.2 Phase 2: JEB 批量导出

#### 导出流程

```
用户在 JEB 中运行 exportDepsFromJeb.py
    ↓
遍历所有 DEX 单元
    ↓
遍历每个类（排除 SDK 类）
    ↓
提取结构性依赖
  - 父类 (getSupertype)
  - 接口 (getInterfaceSignatures)
  - 字段类型 (getFieldTypeSignature)
  - 方法签名 (getReturnType, getParameterTypes)
    ↓
提取方法体依赖
  - 遍历方法的 Dalvik 字节码指令
  - 识别特定操作码 (invoke-*, new-instance, check-cast, etc.)
  - 从 DEX 常量池解析类引用
    ↓
导出为 JSON (jeb-deps-enhanced.json)
    ↓
AI 调用 import_from_jeb_json 导入到 SQLite
```

#### 时间成本

- 导出速度：约 100-200 类/秒
- 总耗时：几分钟（取决于 APK 大小）
- 一次性完成：无需后续补充

#### Phase 3 不再获取依赖

**重要变更**：Phase 3 拓扑发现阶段**不再动态获取依赖**，所有依赖已在 Phase 2 导入数据库。

Phase 3 的任务变为：
- 从种子类开始 BFS 遍历
- 从数据库查询依赖关系
- 标记已发现的类
- 将新发现的类加入队列

---

## 二、依赖类型详解

### 2.1 结构性依赖 (Structural Dependencies)

**定义**：在类声明中显式定义的依赖关系。

#### 包含内容

| 依赖类型 | 说明 | 示例 |
|---------|------|------|
| 父类 | 继承关系 | `class Foo extends Bar` |
| 接口 | 实现关系 | `class Foo implements IBar` |
| 字段类型 | 字段声明的类型 | `private Location mLocation;` |
| 方法参数 | 方法签名中的参数类型 | `void foo(Location loc)` |
| 方法返回值 | 方法签名中的返回类型 | `Location getLocation()` |

#### 获取方式

通过 JEB API 直接读取类的元数据：
- `cls.getSupertypeSignature()` - 父类
- `cls.getInterfaceSignatures()` - 接口列表
- `field.getFieldTypeSignature()` - 字段类型
- `method.getReturnType()` - 返回类型
- `method.getParameterTypes()` - 参数类型列表

#### 特点

- **快速**：直接读取 DEX 元数据，无需解析字节码
- **准确**：100% 准确，无误报
- **必须依赖**：这些依赖是编译时必需的

---

### 2.2 方法体依赖 (Method Body Dependencies)

**定义**：在方法实现代码中使用的类引用。

#### 包含内容

| 依赖类型 | Dalvik 指令 | 说明 | 示例 |
|---------|------------|------|------|
| 方法调用 | `invoke-*` | 调用其他类的方法 | `LocationUtils.parse()` |
| 对象创建 | `new-instance` | 实例化对象 | `new Location()` |
| 类字面量 | `const-class` | 获取 Class 对象 | `Location.class` |
| 类型转换 | `check-cast` | 强制类型转换 | `(Location) obj` |
| 类型检查 | `instance-of` | 类型判断 | `obj instanceof Location` |
| 字段访问 | `iget/iput/sget/sput` | 访问其他类的字段 | `obj.field` |

#### 获取方式

**核心思路**：遍历方法的 Dalvik 字节码指令，识别特定操作码，解析指令参数中的类引用。

**流程**：
1. 获取方法的字节码指令序列 (`method.getData().getCodeItem().getInstructions()`)
2. 遍历每条指令，检查操作码 (`insn.getMnemonic()`)
3. 根据操作码类型，提取指令参数中的索引值 (`param.getValue()`)
4. 通过索引值从 DEX 常量池解析出类签名 (`dex.getMethod(idx)`, `dex.getType(idx)`, `dex.getField(idx)`)

**示例**：
```
Dalvik 指令: invoke-virtual v0, Landroid/location/Location;->getLatitude()D
      ↓
操作码: invoke-virtual
      ↓
参数类型: TYPE_IDX (索引类型)
      ↓
参数值: 1234 (方法索引)
      ↓
解析: dex.getMethod(1234) → 获取方法对象
      ↓
提取: method.getClassType() → Landroid/location/Location;
      ↓
结果: 方法体依赖 Location 类
```

#### 特点

- **完整**：覆盖方法体内所有类引用
- **静态分析**：基于字节码，不需要运行代码
- **准确**：直接从 DEX 常量池解析，无需正则匹配反编译代码
- **数量多**：通常占总依赖的 60-70%

---

### 2.3 两种依赖的对比

| 维度 | 结构性依赖 | 方法体依赖 |
|-----|-----------|-----------|
| **定义位置** | 类声明 | 方法实现 |
| **获取方式** | 读取 DEX 元数据 | 分析 Dalvik 字节码指令 |
| **获取速度** | 极快 | 较快 |
| **数据来源** | JEB API (类/字段/方法对象) | JEB API (字节码指令 + 常量池) |
| **数量占比** | ~30-40% | ~60-70% |
| **编译依赖** | 必须 | 可选（运行时依赖） |
| **重要性** | 高（决定编译顺序） | 高（理解业务逻辑） |

---

### 2.4 为什么需要区分？

#### 编译顺序

结构性依赖决定了类的编译顺序：
- 必须先编译父类，才能编译子类
- 必须先编译字段类型，才能编译包含该字段的类

方法体依赖不影响编译顺序：
- 只要类声明存在，方法体可以引用任何已声明的类
- 编译时只需要类签名，不需要实现

#### 业务理解

结构性依赖反映类的**结构关系**：
- 继承层次
- 接口实现
- 数据模型

方法体依赖反映类的**行为关系**：
- 调用了哪些工具类
- 创建了哪些对象
- 使用了哪些服务

#### 拓扑排序

**Phase 4 业务梳理**需要按拓扑逆序（叶子→根）分析：
- 结构性依赖构成拓扑图的骨架
- 方法体依赖补充完整的依赖关系
- 两者结合才能准确计算拓扑顺序

---

## 三、数据库结构设计

### 3.1 核心表结构

#### `class_dependencies` - 类依赖关系表

存储所有依赖关系（结构性 + 方法体）。

**字段说明**：

| 字段 | 类型 | 说明 | 示例 |
|-----|------|------|------|
| `source_class` | TEXT | 依赖方类签名 | `Lfvxn;` |
| `target_class` | TEXT | 被依赖方类签名 | `Landroid/location/Location;` |
| `dependency_type` | TEXT | 依赖类型 | `superclass`, `interface`, `field`, `method_param`, `method_return`, `method_body` |
| `dependency_source` | TEXT | 依赖来源 | `structural`, `method_body` |
| `context` | TEXT | 上下文 | 字段名 `mLocation`, 方法名 `onLocationChanged` |

**索引**：
- `source_class` - 查询某个类的所有依赖
- `target_class` - 查询哪些类依赖某个类（入度）
- `dependency_type` - 按类型过滤
- `dependency_source` - 区分结构性/方法体依赖

#### `analysis_status` - 分析状态表

跟踪每个类在各阶段的处理状态。

**字段说明**：

| 字段 | 类型 | 说明 |
|-----|------|------|
| `class_sig` | TEXT | 类签名（主键） |
| `discovered` | BOOLEAN | Phase 3: 是否已发现 |
| `discovery_depth` | INTEGER | BFS 深度 |
| `analyzed` | BOOLEAN | Phase 4: 是否已分析业务 |
| `documented` | BOOLEAN | Phase 4: 是否已生成 MD 文档 |
| `tags` | TEXT | Phase 4: 标签（JSON 数组） |
| `module` | TEXT | Phase 4: 所属模块 |
| `business_summary` | TEXT | Phase 4: 业务摘要 |
| `restored` | BOOLEAN | Phase 5: 是否已还原代码 |
| `compiled` | BOOLEAN | Phase 5: 是否编译通过 |
| `java_source_path` | TEXT | Phase 5: Java 源码路径 |

#### `class_rename_index` - 重命名索引表

存储类/方法/字段的重命名映射。

**三个表**：
- `class_rename_index` - 类重命名
- `method_rename_index` - 方法重命名
- `field_rename_index` - 字段重命名

---

## 四、工作流各阶段的依赖使用

### 4.1 Phase 2: 数据导入

**任务**：将 JEB 导出的 JSON 导入数据库

**依赖处理**：
- 解析 JSON 中的结构性依赖（父类、接口、字段、方法签名）
- 解析 JSON 中的方法体依赖（`method_body_deps` 字段）
- 插入到 `class_dependencies` 表
- 初始化 `analysis_status` 表（所有类标记为未发现）

**SQL 操作**：
```
INSERT INTO class_dependencies (source_class, target_class, dependency_type, dependency_source)
INSERT INTO analysis_status (class_sig, discovered)
```

---

### 4.2 Phase 3: 拓扑发现

**任务**：从种子类开始 BFS 遍历，发现所有依赖节点

**依赖处理**：
- 从数据库查询当前类的所有依赖
- 过滤系统类（java.*, android.*, etc.）
- 标记新发现的类
- 将新类加入队列

**SQL 查询**：
```
-- 查询某个类的所有依赖
SELECT DISTINCT target_class
FROM class_dependencies
WHERE source_class = ?

-- 标记已发现
UPDATE analysis_status
SET discovered = 1, discovery_depth = ?
WHERE class_sig = ?
```

**不再需要**：
- ❌ 调用 JEB MCP 获取反编译代码
- ❌ 解析反编译代码提取依赖
- ❌ 双 Agent 审查依赖完整性

**优势**：
- 速度快：只查询数据库，无需调用 JEB
- 准确：依赖已在 Phase 2 完整导出
- 简单：纯 BFS 算法，无需复杂解析

---

### 4.3 Phase 4: 业务梳理

**任务**：按拓扑逆序（叶子→根）分析业务，生成 MD 文档

**依赖处理**：
- 查询当前类的所有依赖
- 读取依赖类的业务摘要（已分析的类）
- 结合依赖类的功能理解当前类的业务
- 生成 MD 文档 + 标签

**SQL 查询**：
```
-- 查找可分析的类（依赖都已分析）
SELECT a.class_sig
FROM analysis_status a
WHERE a.discovered = 1
  AND a.analyzed = 0
  AND NOT EXISTS (
      SELECT 1
      FROM class_dependencies cd
      JOIN analysis_status dep ON cd.target_class = dep.class_sig
      WHERE cd.source_class = a.class_sig
        AND dep.analyzed = 0
  )
ORDER BY a.discovery_depth ASC
LIMIT 10;

-- 查询依赖类的业务摘要
SELECT cd.target_class, cd.dependency_type, a.business_summary
FROM class_dependencies cd
JOIN analysis_status a ON cd.target_class = a.class_sig
WHERE cd.source_class = ?
  AND a.business_summary IS NOT NULL;
```

**依赖的作用**：
- 结构性依赖：理解类的结构（继承、组合）
- 方法体依赖：理解类的行为（调用、创建）

---

### 4.4 Phase 5: 逆向还原

**任务**：按拓扑逆序还原 Java 源码，编译验证

**依赖处理**：
- 查询当前类的所有依赖
- 确保依赖类都已还原
- 生成 Java 源码（引用依赖类）
- 编译验证

**SQL 查询**：
```
-- 查找可还原的类（依赖都已还原）
SELECT a.class_sig
FROM analysis_status a
WHERE a.analyzed = 1
  AND a.restored = 0
  AND NOT EXISTS (
      SELECT 1
      FROM class_dependencies cd
      JOIN analysis_status dep ON cd.target_class = dep.class_sig
      WHERE cd.source_class = a.class_sig
        AND dep.restored = 0
  )
ORDER BY a.discovery_depth ASC
LIMIT 10;
```

**依赖的作用**：
- 结构性依赖：决定编译顺序
- 方法体依赖：生成正确的方法实现

---

## 五、依赖统计查询

### 5.1 全局统计

**统计依赖来源分布**：
```
查询: 按 dependency_source 分组统计
结果: structural: 35%, method_body: 65%
```

**统计依赖类型分布**：
```
查询: 按 dependency_type 分组统计
结果:
  - superclass: 10%
  - interface: 5%
  - field: 15%
  - method_param: 5%
  - method_return: 5%
  - method_body: 60%
```

### 5.2 拓扑分析

**查找叶子节点**（无依赖的类）：
```
查询: 在 analysis_status 中查找不在 class_dependencies.source_class 中的类
用途: Phase 4 的起点
```

**查找可分析的类**（依赖都已分析）：
```
查询: 使用 NOT EXISTS 子查询检查是否有未分析的依赖
用途: Phase 4 每轮迭代选择下一个类
```

**计算入度/出度**：
```
入度: 被多少类依赖 (COUNT DISTINCT source_class WHERE target_class = ?)
出度: 依赖多少类 (COUNT DISTINCT target_class WHERE source_class = ?)
用途: 识别核心类、工具类
```

---

## 六、总结

### 6.1 核心要点

**依赖获取**：
- 所有依赖在 Phase 2 一次性导出（JEB 脚本）
- 方法体依赖通过静态分析 Dalvik 字节码获取
- Phase 3 不再动态获取依赖，只查询数据库

**依赖类型**：
- 结构性依赖：类声明中的依赖（30-40%）
- 方法体依赖：方法实现中的依赖（60-70%）
- 两者结合才能完整理解类的功能

**数据库设计**：
- `class_dependencies`：存储所有依赖关系
- `analysis_status`：跟踪各阶段处理状态
- `*_rename_index`：存储重命名映射

### 6.2 工作流优势

**Phase 2 批量导出**：
- 快速：几分钟完成所有类
- 完整：覆盖所有依赖类型
- 准确：基于字节码，无需正则匹配

**Phase 3 简化**：
- 纯 BFS 遍历，无需调用 JEB
- 只查询数据库，速度快
- 无需双 Agent 审查

**Phase 4/5 高效**：
- 拓扑排序基于完整依赖图
- 依赖类的分析结果可复用
- 编译顺序准确

### 6.3 关键 SQL 查询

```sql
-- 1. 统计依赖来源分布
SELECT dependency_source, COUNT(*)
FROM class_dependencies
GROUP BY dependency_source;

-- 2. 查找叶子节点
SELECT class_sig
FROM analysis_status
WHERE discovered = 1
  AND class_sig NOT IN (SELECT DISTINCT source_class FROM class_dependencies);

-- 3. 查找可分析的类
SELECT class_sig
FROM analysis_status
WHERE discovered = 1 AND analyzed = 0
  AND NOT EXISTS (
      SELECT 1 FROM class_dependencies cd
      JOIN analysis_status dep ON cd.target_class = dep.class_sig
      WHERE cd.source_class = analysis_status.class_sig AND dep.analyzed = 0
  );

-- 4. 统计模块分布
SELECT module, COUNT(*)
FROM analysis_status
WHERE module IS NOT NULL
GROUP BY module;
```

---

## 附录

### A. JEB 导出脚本

位置：`scripts/exportDepsFromJeb.py`

核心功能：
- 遍历 DEX 类
- 提取结构性依赖（JEB API）
- 提取方法体依赖（字节码分析）
- 导出 JSON

### B. 数据库初始化脚本

位置：`scripts/init_database.sql`

包含：
- 表结构定义
- 索引创建
- 初始数据

### C. JSON 导入脚本

位置：`scripts/depsJson2db.py`

功能：
- 解析 JEB 导出的 JSON
- 插入到 SQLite
- 初始化分析状态
