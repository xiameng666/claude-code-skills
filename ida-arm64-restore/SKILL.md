---
name: ida-arm64-restore
description: 使用IDA Pro MCP批量还原ARM64函数签名，自动识别参数类型、返回值和调用约定，按规范重命名函数
license: MIT
compatibility: opencode
metadata:
  domain: reverse-engineering
  arch: arm64
  tools: ida-pro-mcp
---

## 核心原则

**所有分析必须通过 ida-pro-mcp 获取真实反汇编数据，禁止猜测。**

## 工作流程

### 1. 获取函数列表
- 使用 ida-pro-mcp 获取目标地址范围内的函数
- 按调用关系排序，优先处理被依赖的函数

### 2. 逐函数分析
对每个函数执行以下分析：

#### 参数识别

| 检查项 | 判断依据 |
|--------|----------|
| 参数数量 | 函数序言 `str x0-x7, [sp, #offset]` 的数量 |
| 指针参数 | 寄存器被解引用 `ldr/str [xN]` |
| 整数/枚举 | 与立即数比较或位运算 |
| 浮点参数 | 使用 V0-V7 寄存器 |
| 类型推断 | 参数传递给已知函数时，参考目标函数签名 |

#### 返回值识别

| 模式 | 返回类型 |
|------|----------|
| 序言保存 X8 | 大结构体 (>16字节)，通过 X8 指针返回 |
| 尾部 `mov x0, xN` | 整数/指针 |
| 尾部 `fmov d0/s0` | 浮点数 (double/float) |
| 尾部设置 X0+X1 | 小结构体 (≤16字节) |
| 无显式返回 | void 或通过 X8 返回 |

### 3. 函数重命名

**命名格式**：`R_<语义名称>_<函数地址>`

示例：
- `R_initBuffer_0x1000` 
- `R_parseHeader_0x2048`
- `R_calculateChecksum_0x30A0`

### 4. 批量处理
