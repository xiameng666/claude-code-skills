# 依赖关系分析技术文档

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
JEB 打开 APK
    ↓
遍历所有 DEX 单元
    ↓
遍历每个类
    ↓
提取结构性依赖 (父类、接口、字段、方法签名)
    ↓
提取方法体依赖 (分析 Dalvik 字节码指令)
    ↓
导出为 JSON
    ↓
导入到 SQLite
```

#### 时间成本

- 导出速度：约 100-200 类/秒
- 总耗时：几分钟（取决于 APK 大小）
- 一次性完成：无需后续补充

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
1. 获取方法的字节码指令序列
2. 遍历每条指令，检查操作码（opcode）
3. 根据操作码类型，提取指令参数中的索引值
4. 通过索引值从 DEX 常量池解析出类签名

**示例**：
```
指令: invoke-virtual v0, Landroid/location/Location;->getLatitude()D
      ↓
操作码: invoke-virtual
      ↓
参数: TYPE_IDX = 1234 (方法索引)
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
- **准确**：直接从 DEX 常量池解析，无需正则匹配
- **数量多**：通常占总依赖的 60-70%

---

### 2.3 两种依赖的对比

| 维度 | 结构性依赖 | 方法体依赖 |
|-----|-----------|-----------|
| **定义位置** | 类声明 | 方法实现 |
| **获取方式** | 读取 DEX 元数据 | 分析 Dalvik 字节码 |
| **获取速度** | 极快 | 较快 |
| **数据来源** | JEB API (类/字段/方法对象) | JEB API (字节码指令) |
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

### 2.1 核心表结构

#### `class_dependencies` - 类依赖关系表

```sql
CREATE TABLE class_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_class TEXT NOT NULL,           -- 源类 (依赖方)
    target_class TEXT NOT NULL,           -- 目标类 (被依赖方)
    dependency_type TEXT NOT NULL,        -- 依赖类型
    dependency_source TEXT NOT NULL,      -- 依赖来源 (structural/method_body)
    context TEXT,                         -- 上下文信息 (字段名/方法名)
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_class, target_class, dependency_type, context)
);

CREATE INDEX idx_source ON class_dependencies(source_class);
CREATE INDEX idx_target ON class_dependencies(target_class);
CREATE INDEX idx_type ON class_dependencies(dependency_type);
CREATE INDEX idx_source_dep ON class_dependencies(dependency_source);
```

**字段说明**：

| 字段 | 类型 | 说明 | 示例 |
|-----|------|------|------|
| `source_class` | TEXT | 依赖方类签名 | `Lfvxn;` |
| `target_class` | TEXT | 被依赖方类签名 | `Landroid/location/Location;` |
| `dependency_type` | TEXT | 依赖类型 | `superclass`, `interface`, `field`, `method_param`, `method_return`, `method_body` |
| `dependency_source` | TEXT | 依赖来源 | `structural` (Phase 2), `method_body` (Phase 3) |
| `context` | TEXT | 上下文 | 字段名 `mLocation`, 方法名 `onLocationChanged` |

#### `analysis_status` - 分析状态表

```sql
CREATE TABLE analysis_status (
    class_sig TEXT PRIMARY KEY,

    -- Phase 3: 拓扑发现
    discovered BOOLEAN DEFAULT 0,
    discovery_depth INTEGER DEFAULT 0,    -- BFS 深度

    -- Phase 4: 业务梳理
    analyzed BOOLEAN DEFAULT 0,
    documented BOOLEAN DEFAULT 0,
    tags TEXT,                            -- JSON 数组: ["proto", "location"]
    module TEXT,                          -- 模块名: "gms/location"
    business_summary TEXT,                -- 业务摘要

    -- Phase 5: 逆向还原
    restored BOOLEAN DEFAULT 0,
    compiled BOOLEAN DEFAULT 0,
    java_source_path TEXT,                -- 生成的 Java 源码路径

    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_discovered ON analysis_status(discovered);
CREATE INDEX idx_analyzed ON analysis_status(analyzed);
CREATE INDEX idx_module ON analysis_status(module);
```

#### `class_rename_index` - 重命名索引表

```sql
CREATE TABLE class_rename_index (
    obfuscated TEXT PRIMARY KEY,          -- 混淆名 (简短格式)
    renamed TEXT NOT NULL,                -- 重命名后的名称
    note TEXT,                            -- 备注说明
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE method_rename_index (
    class_obfuscated TEXT NOT NULL,
    method_sig TEXT NOT NULL,             -- 方法签名 (含参数)
    renamed TEXT NOT NULL,
    note TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (class_obfuscated, method_sig)
);

CREATE TABLE field_rename_index (
    class_obfuscated TEXT NOT NULL,
    field_name TEXT NOT NULL,
    renamed TEXT NOT NULL,
    note TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (class_obfuscated, field_name)
);
```

---

## 三、依赖类型详解

### 3.1 结构性依赖 (Structural Dependencies)

**定义**：在类声明中显式定义的依赖关系，可以通过静态分析获取。

#### 类型列表

| 依赖类型 | 说明 | 示例 |
|---------|------|------|
| `superclass` | 父类继承 | `class Foo extends Bar` → `Foo` 依赖 `Bar` |
| `interface` | 接口实现 | `class Foo implements IBar` → `Foo` 依赖 `IBar` |
| `field` | 字段类型 | `private Location mLocation;` → `Foo` 依赖 `Location` |
| `method_param` | 方法参数类型 | `void foo(Location loc)` → `Foo` 依赖 `Location` |
| `method_return` | 方法返回类型 | `Location getLocation()` → `Foo` 依赖 `Location` |

#### 获取方式

**Phase 2 (JEB 导出)**：
```python
# JEB Python API
dex_class.getSupertype()              # 父类
dex_class.getImplementedInterfaces()  # 接口
field.getFieldType()                  # 字段类型
method.getReturnType()                # 返回类型
method.getParameterTypes()            # 参数类型
```

**Phase 3 (JEB MCP)**：
```python
# MCP 工具调用
get_class_superclass(class_sig)       # 父类
get_class_interfaces(class_sig)       # 接口
get_class_fields(class_sig)           # 字段列表
get_class_methods(class_sig)          # 方法列表
```

#### 数据库存储

```sql
INSERT INTO class_dependencies (
    source_class,
    target_class,
    dependency_type,
    dependency_source,
    context
) VALUES (
    'Lfvxn;',                          -- 源类
    'Landroid/location/Location;',     -- 目标类
    'field',                           -- 依赖类型
    'structural',                      -- 依赖来源
    'mLocation'                        -- 字段名
);
```

---

### 3.2 方法体依赖 (Method Body Dependencies)

**定义**：在方法实现代码中使用的类引用，需要通过反编译代码分析获取。

#### 类型列表

| 依赖类型 | 说明 | 示例 |
|---------|------|------|
| `method_body` | 方法体内的类引用 | `new Location()`, `Location.parse()`, `instanceof Location` |
| `local_var` | 局部变量类型 | `Location loc = ...;` |
| `cast` | 类型转换 | `(Location) obj` |
| `static_call` | 静态方法调用 | `LocationUtils.parse()` |
| `instance_call` | 实例方法调用 | `location.getLatitude()` |

#### 获取方式

**Phase 3 (反编译代码分析)**：

```python
def parse_method_body_dependencies(decompiled_code):
    """
    解析反编译代码中的类引用
    """
    dependencies = set()

    # 1. 正则匹配 new 关键字
    # new Location()
    new_pattern = r'new\s+([A-Za-z0-9_$.]+)\s*\('
    dependencies.update(re.findall(new_pattern, decompiled_code))

    # 2. 正则匹配静态方法调用
    # LocationUtils.parse()
    static_pattern = r'([A-Za-z0-9_$.]+)\.[a-z][A-Za-z0-9_]*\s*\('
    dependencies.update(re.findall(static_pattern, decompiled_code))

    # 3. 正则匹配类型转换
    # (Location) obj
    cast_pattern = r'\(\s*([A-Za-z0-9_$.]+)\s*\)'
    dependencies.update(re.findall(cast_pattern, decompiled_code))

    # 4. 正则匹配 instanceof
    # obj instanceof Location
    instanceof_pattern = r'instanceof\s+([A-Za-z0-9_$.]+)'
    dependencies.update(re.findall(instanceof_pattern, decompiled_code))

    # 5. 正则匹配静态字段访问
    # Location.PROVIDER
    static_field_pattern = r'([A-Z][A-Za-z0-9_$.]+)\.[A-Z_]+'
    dependencies.update(re.findall(static_field_pattern, decompiled_code))

    return dependencies
```

#### 示例代码分析

**反编译代码**：
```java
public class fvxn {
    private Location mLocation;  // 结构性依赖: field

    public Location getLocation() {  // 结构性依赖: method_return
        return this.mLocation;
    }

    public void updateLocation(Location loc) {  // 结构性依赖: method_param
        // 方法体依赖开始
        if (loc instanceof Location) {           // 方法体依赖: instanceof
            Location newLoc = new Location(loc); // 方法体依赖: new, local_var
            LocationUtils.validate(newLoc);      // 方法体依赖: static_call (LocationUtils)
            this.mLocation = newLoc;
        }
    }
}
```

**依赖提取结果**：

| 源类 | 目标类 | 依赖类型 | 依赖来源 | 上下文 |
|-----|-------|---------|---------|--------|
| `fvxn` | `Location` | `field` | `structural` | `mLocation` |
| `fvxn` | `Location` | `method_return` | `structural` | `getLocation` |
| `fvxn` | `Location` | `method_param` | `structural` | `updateLocation` |
| `fvxn` | `Location` | `method_body` | `method_body` | `updateLocation:instanceof` |
| `fvxn` | `Location` | `method_body` | `method_body` | `updateLocation:new` |
| `fvxn` | `LocationUtils` | `method_body` | `method_body` | `updateLocation:static_call` |

#### 数据库存储

```sql
-- 方法体依赖: new Location()
INSERT INTO class_dependencies (
    source_class,
    target_class,
    dependency_type,
    dependency_source,
    context
) VALUES (
    'Lfvxn;',
    'Landroid/location/Location;',
    'method_body',
    'method_body',
    'updateLocation:new'
);

-- 方法体依赖: LocationUtils.validate()
INSERT INTO class_dependencies (
    source_class,
    target_class,
    dependency_type,
    dependency_source,
    context
) VALUES (
    'Lfvxn;',
    'Lcom/google/android/gms/location/LocationUtils;',
    'method_body',
    'method_body',
    'updateLocation:static_call'
);
```

---

## 四、依赖统计查询

### 4.1 基础统计查询

#### 统计每个类的依赖数量

```sql
-- 按依赖来源分组统计
SELECT
    source_class,
    dependency_source,
    COUNT(*) as dep_count
FROM class_dependencies
GROUP BY source_class, dependency_source
ORDER BY source_class, dependency_source;
```

**结果示例**：
```
source_class | dependency_source | dep_count
-------------|-------------------|----------
Lfvxn;       | structural        | 5
Lfvxn;       | method_body       | 12
Lfvxo;       | structural        | 3
Lfvxo;       | method_body       | 8
```

#### 统计每个类的被依赖数量 (入度)

```sql
SELECT
    target_class,
    COUNT(DISTINCT source_class) as dependent_count
FROM class_dependencies
GROUP BY target_class
ORDER BY dependent_count DESC
LIMIT 20;
```

**结果示例**：
```
target_class                              | dependent_count
------------------------------------------|----------------
Landroid/location/Location;               | 45
Lcom/google/android/gms/common/api/Api;   | 32
Ljava/lang/String;                        | 156
```

---

### 4.2 结构性依赖 vs 方法体依赖统计

#### 全局统计

```sql
SELECT
    dependency_source,
    COUNT(*) as total_deps,
    COUNT(DISTINCT source_class) as class_count,
    COUNT(DISTINCT target_class) as target_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM class_dependencies), 2) as percentage
FROM class_dependencies
GROUP BY dependency_source;
```

**结果示例**：
```
dependency_source | total_deps | class_count | target_count | percentage
------------------|------------|-------------|--------------|------------
structural        | 1,234      | 456         | 234          | 35.67%
method_body       | 2,345      | 456         | 567          | 64.33%
```

**解读**：
- 结构性依赖占 35.67%，但覆盖的目标类较少（234 个）
- 方法体依赖占 64.33%，覆盖的目标类更多（567 个）
- 说明方法体中引用了大量结构声明中未出现的类

#### 按依赖类型统计

```sql
SELECT
    dependency_type,
    dependency_source,
    COUNT(*) as count
FROM class_dependencies
GROUP BY dependency_type, dependency_source
ORDER BY dependency_type, dependency_source;
```

**结果示例**：
```
dependency_type | dependency_source | count
----------------|-------------------|-------
field           | structural        | 345
interface       | structural        | 89
method_body     | method_body       | 2,345
method_param    | structural        | 234
method_return   | structural        | 156
superclass      | structural        | 410
```

---

### 4.3 拓扑排序查询

#### 查找叶子节点 (无依赖的类)

```sql
-- 只有结构性依赖的叶子节点
SELECT DISTINCT source_class
FROM analysis_status
WHERE discovered = 1
  AND source_class NOT IN (
      SELECT DISTINCT source_class
      FROM class_dependencies
      WHERE dependency_source = 'structural'
  );
```

#### 查找可分析的类 (依赖都已分析)

```sql
-- Phase 4: 查找依赖都已梳理的类
SELECT a.class_sig
FROM analysis_status a
WHERE a.discovered = 1
  AND a.analyzed = 0
  AND NOT EXISTS (
      -- 检查是否有未分析的依赖
      SELECT 1
      FROM class_dependencies cd
      JOIN analysis_status dep ON cd.target_class = dep.class_sig
      WHERE cd.source_class = a.class_sig
        AND dep.analyzed = 0
  )
ORDER BY a.discovery_depth ASC  -- 优先处理浅层节点
LIMIT 10;
```

---

### 4.4 依赖路径查询

#### 查找两个类之间的依赖路径

```sql
-- 使用递归 CTE 查找依赖路径
WITH RECURSIVE dep_path AS (
    -- 起点
    SELECT
        source_class,
        target_class,
        dependency_type,
        source_class || ' -> ' || target_class as path,
        1 as depth
    FROM class_dependencies
    WHERE source_class = 'Lfvxn;'

    UNION ALL

    -- 递归
    SELECT
        cd.source_class,
        cd.target_class,
        cd.dependency_type,
        dp.path || ' -> ' || cd.target_class,
        dp.depth + 1
    FROM class_dependencies cd
    JOIN dep_path dp ON cd.source_class = dp.target_class
    WHERE dp.depth < 5  -- 限制深度
)
SELECT * FROM dep_path
WHERE target_class = 'Landroid/location/Location;'
ORDER BY depth
LIMIT 10;
```

**结果示例**：
```
path                                          | depth
----------------------------------------------|-------
Lfvxn; -> Location                            | 1
Lfvxn; -> LocationCallback -> Location        | 2
Lfvxn; -> FusedApi -> LocationRequest -> Location | 3
```

---

## 五、依赖获取工具对比

### 5.1 JEB Python API (Phase 2)

**优点**：
- 快速：批量导出所有类（几分钟）
- 完整：覆盖所有 DEX 类
- 离线：不需要 MCP 服务

**缺点**：
- 只能获取结构性依赖
- 无法分析方法体内的类引用
- 需要手动运行脚本

**适用场景**：
- Phase 2: 初始数据导入
- 快速建立依赖图骨架

---

### 5.2 JEB MCP 工具 (Phase 3)

**优点**：
- 精确：通过反编译代码分析
- 深度：包含方法体依赖
- 动态：按需获取，支持 BFS

**缺点**：
- 慢：每个类需要单独调用
- 依赖 MCP 服务：需要 JEB 运行
- 需要解析反编译代码

**适用场景**：
- Phase 3: 拓扑发现
- 深度依赖分析

---

## 六、实际应用示例

### 6.1 Phase 3: 拓扑发现流程

```python
def topology_discovery_iteration():
    """
    单次 BFS 迭代
    """
    # 1. 从队列取出一个类
    current_class = queue.pop(0)

    # 2. 获取反编译代码
    decompiled = get_class_decompiled_code(current_class)

    # 3. 解析结构性依赖
    structural_deps = {
        'superclass': get_class_superclass(current_class),
        'interfaces': get_class_interfaces(current_class),
        'fields': [f['type'] for f in get_class_fields(current_class)],
        'methods': extract_method_signature_types(get_class_methods(current_class))
    }

    # 4. 解析方法体依赖
    method_body_deps = parse_method_body_dependencies(decompiled)

    # 5. 存储到数据库
    for dep_type, targets in structural_deps.items():
        for target in targets:
            insert_dependency(
                source=current_class,
                target=target,
                dep_type=dep_type,
                dep_source='structural'
            )

    for target in method_body_deps:
        insert_dependency(
            source=current_class,
            target=target,
            dep_type='method_body',
            dep_source='method_body'
        )

    # 6. 新类入队
    all_deps = flatten(structural_deps.values()) + list(method_body_deps)
    for dep in all_deps:
        if not is_discovered(dep) and not is_system_class(dep):
            queue.append(dep)
            mark_discovered(dep)

    # 7. 更新状态
    mark_analyzed(current_class)
```

---

### 6.2 Phase 4: 业务梳理流程

```python
def business_analysis_iteration():
    """
    单次业务梳理迭代
    """
    # 1. 查找可分析的类 (依赖都已梳理)
    candidates = query_analyzable_classes()

    if not candidates:
        return "ANALYSIS_COMPLETE"

    current_class = candidates[0]

    # 2. 获取依赖类的业务摘要
    deps = query_dependencies(current_class)
    dep_summaries = []

    for dep in deps:
        summary = query_business_summary(dep['target_class'])
        if summary:
            dep_summaries.append({
                'class': dep['target_class'],
                'type': dep['dependency_type'],
                'summary': summary
            })

    # 3. 获取反编译代码
    decompiled = get_class_decompiled_code(current_class)

    # 4. AI 分析业务功能
    analysis_prompt = f"""
    分析类 {current_class} 的业务功能

    反编译代码:
    {decompiled}

    依赖类功能:
    {format_dep_summaries(dep_summaries)}

    请输出:
    1. 业务摘要 (1-2 句话)
    2. 标签 (类型/模块/功能)
    3. 详细分析 (Markdown)
    """

    result = ai_analyze(analysis_prompt)

    # 5. 存储分析结果
    update_analysis_status(
        class_sig=current_class,
        analyzed=True,
        business_summary=result['summary'],
        tags=result['tags'],
        module=result['module']
    )

    # 6. 生成 MD 文档
    create_class_md(current_class, result)

    return "CONTINUE"
```

---

## 七、总结

### 7.1 依赖类型对比

| 维度 | 结构性依赖 | 方法体依赖 |
|-----|-----------|-----------|
| **定义位置** | 类声明 | 方法实现 |
| **获取方式** | 静态分析 (JEB API) | 反编译代码分析 |
| **获取速度** | 快 (批量导出) | 慢 (逐个分析) |
| **覆盖范围** | 类签名中的类型 | 方法体中的所有类引用 |
| **数量占比** | ~35% | ~65% |
| **重要性** | 高 (必须依赖) | 中 (可能依赖) |
| **用途** | 拓扑排序、编译顺序 | 业务理解、完整性分析 |

### 7.2 数据流总结

```
Phase 2: JEB 导出
    ↓
[结构性依赖] → SQLite (class_dependencies)
    ↓
Phase 3: BFS 探索
    ↓
[方法体依赖] → SQLite (class_dependencies)
    ↓
Phase 4: 业务梳理
    ↓
查询依赖 → 分析业务 → 生成 MD
    ↓
Phase 5: 逆向还原
    ↓
查询依赖 → 生成 Java → 编译验证
```

### 7.3 关键 SQL 查询

```sql
-- 1. 统计依赖来源分布
SELECT dependency_source, COUNT(*) FROM class_dependencies GROUP BY dependency_source;

-- 2. 查找叶子节点
SELECT class_sig FROM analysis_status WHERE discovered = 1 AND class_sig NOT IN (SELECT DISTINCT source_class FROM class_dependencies);

-- 3. 查找可分析的类
SELECT class_sig FROM analysis_status WHERE discovered = 1 AND analyzed = 0 AND NOT EXISTS (SELECT 1 FROM class_dependencies cd JOIN analysis_status dep ON cd.target_class = dep.class_sig WHERE cd.source_class = analysis_status.class_sig AND dep.analyzed = 0);

-- 4. 统计模块分布
SELECT module, COUNT(*) FROM analysis_status WHERE module IS NOT NULL GROUP BY module;
```

---

## 八、常见问题

### Q1: 为什么需要区分结构性依赖和方法体依赖？

**A**:
- **编译顺序**：结构性依赖决定编译顺序（必须先编译被依赖类）
- **业务理解**：方法体依赖反映实际使用关系（更重要）
- **性能优化**：结构性依赖可批量获取，方法体依赖需逐个分析

### Q2: 如何处理循环依赖？

**A**:
- **检测**：使用 Tarjan 算法检测强连通分量
- **处理**：将强连通分量视为一个整体，同时分析
- **存储**：在数据库中标记循环依赖关系

```sql
-- 检测循环依赖
WITH RECURSIVE dep_cycle AS (
    SELECT source_class, target_class, source_class as root, 1 as depth
    FROM class_dependencies
    UNION ALL
    SELECT cd.source_class, cd.target_class, dc.root, dc.depth + 1
    FROM class_dependencies cd
    JOIN dep_cycle dc ON cd.source_class = dc.target_class
    WHERE dc.depth < 10
)
SELECT root, source_class, target_class
FROM dep_cycle
WHERE target_class = root AND depth > 1;
```

### Q3: 如何优化依赖查询性能？

**A**:
- **索引**：在 `source_class`, `target_class`, `dependency_source` 上建立索引
- **缓存**：缓存常用查询结果（如叶子节点列表）
- **分批查询**：使用 `LIMIT` 分批处理
- **物化视图**：预计算拓扑排序结果

---

## 附录

### A. 完整表结构 SQL

参见：`scripts/init_database.sql`

### B. JEB 导出脚本

参见：`scripts/ExportDeps.py`

### C. 依赖解析正则表达式

参见：`utils/dependency_parser.py`
