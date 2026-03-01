# 图论规则定义

## 核心概念

### 依赖方向

```
A → B  表示：A 依赖 B

依赖类型：
- extends:       A 继承 B
- implements:    A 实现 B
- field_type:    A 的字段类型是 B
- method_param:  A 的方法参数类型是 B
- method_return: A 的方法返回类型是 B
- method_body:   A 的方法体内部使用了 B（new、调用、cast等）
```

### 节点类型

```
叶子节点 = 出度为 0（不依赖任何其他混淆类）
根节点 = 入度为 0（不被任何混淆类依赖）
中间节点 = 入度 > 0 且 出度 > 0
```

---

## 依赖来源（必须全部扫描）

### 1. 类声明层面

| 来源 | MCP 工具 | 依赖类型 |
|------|----------|----------|
| 父类 | `get_class_superclass` | extends |
| 接口 | `get_class_interfaces` | implements |
| 类型树 | `get_class_type_tree` | extends/implements |

### 2. 成员变量层面

| 来源 | MCP 工具 | 依赖类型 |
|------|----------|----------|
| 字段类型 | `get_class_fields` | field_type |
| 泛型参数 | `get_class_fields` + 解析 | field_type |

### 3. 方法签名层面

| 来源 | MCP 工具 | 依赖类型 |
|------|----------|----------|
| 方法参数 | `get_class_methods` | method_param |
| 方法返回值 | `get_class_methods` | method_return |
| 异常类型 | `get_class_methods` | method_param |

### 4. 方法体层面（重要！）

| 来源 | MCP 工具 | 依赖类型 |
|------|----------|----------|
| 反编译代码 | `get_class_decompiled_code` | method_body |
| new 对象 | 解析反编译代码 | method_body |
| 方法调用 | 解析反编译代码 | method_body |
| 类型转换 | 解析反编译代码 | method_body |
| 匿名类 | 解析反编译代码 | method_body |
| Lambda | 解析反编译代码 | method_body |

### 5. 完整依赖提取流程

```
对每个类执行：

1. get_class_superclass(class_sig)      → 父类
2. get_class_interfaces(class_sig)      → 接口列表
3. get_class_type_tree(class_sig)       → 完整继承链
4. get_class_fields(class_sig)          → 所有字段类型
5. get_class_methods(class_sig)         → 所有方法签名
6. get_class_decompiled_code(class_sig) → 方法体分析

从反编译代码中提取：
  - new Xxx() 语句
  - Xxx.method() 调用
  - (Xxx) obj 类型转换
  - new Xxx() {} 匿名类
  - () -> {} Lambda 中的类型
  - try-catch 中的异常类型
```

---

## 强制规则

### 1. 遍历范围

```
必须遍历到：
  - 所有混淆类的依赖
  - 直到没有新的混淆类被发现

不遍历：
  - java.*
  - android.*
  - 其他已知的框架类
```

### 2. 完成标准

```
连续 2 轮遍历未发现新的混淆类
```

### 3. 持久化要求

```
每发现一个类，必须：
  1. 创建/更新对应的 MD 文件
  2. 记录依赖关系（区分来源类型）
  3. 计算入度/出度
```

### 4. 循环依赖

```
当发现 A → B → ... → A 时：
  - 记录循环路径
  - 不中断遍历
  - 在 MD 中标记
```

### 5. 同步审阅（强制）

```
每个类处理完后，必须：
  1. 调用审阅 Agent 验证完整性
  2. 等待审阅结果（同步）
  3. 通过 → 持久化 + 处理下一个类
  4. 不通过 → 补充探索，最多重试 3 次

审阅检查项：
  - 父类的父类是否遗漏？
  - 接口的父接口是否遗漏？
  - 泛型类型参数是否遗漏？
  - 方法返回类型是否遗漏？
  - 方法体内部依赖是否遗漏？

禁止：
  - 无审阅直接处理下一个类
  - 异步审阅（必须等待结果）
  - 跳过方法体分析
```

---

## 检查点

每处理 N 个类，输出：

```
[进度] 已处理: X | 待处理: Y | 叶子节点: Z | 循环: C
```

---

## 输出格式

### 类 MD 文件的 frontmatter

```yaml
---
obfuscated: "Lxxx;"
renamed: "com.example.ClassName"
confidence: high|medium|low
is_leaf: true|false
is_root: true|false
in_degree: N
out_degree: N
tags: [tag1, tag2]
---
```

### 依赖关系表

```markdown
## 依赖关系

### 依赖的类（出边）
| 类 | 类型 | 来源 | 说明 |
|----|------|------|------|
| [[Lyyy;]] | field_type | 字段 n | 字段依赖 |
| [[Lzzz;]] | method_body | 构造函数 | new Lzzz;() |

### 被依赖（入边）
| 类 | 类型 | 说明 |
|----|------|------|
| [[Laaa;]] | method_return | 返回此类型 |
```
