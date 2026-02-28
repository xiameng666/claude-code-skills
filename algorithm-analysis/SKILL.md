---
name: algorithm-analysis
description: 当用户要求 "算法分析” “trace分析” “unidbg补环境" 时使用此 skill
---

# Native SO 算法逆向分析 Skill

## 触发条件
当用户要求分析 Android native SO 库中的算法实现时使用此 skill。
典型场景：签名算法还原、加密算法分析、token 生成逻辑逆向。

## 前置条件
- IDA Pro 已打开目标 SO 文件，且 IDA MCP Server 已连接
- unidbg Java 文件可用，包含目标函数调用代码
- （可选）trace 日志文件可用

## 可用工具映射

| 分析需求 | IDA MCP 工具 | 说明 |
|---------|-------------|------|
| 反编译函数 | `decompile` | 获取伪代码，理解函数逻辑 |
| 反汇编指令 | `disasm` | 查看具体汇编指令序列 |
| 基本块分析 | `basic_blocks` | 理解控制流 |
| 调用关系 | `callees` / `callgraph` | 追踪函数调用链 |
| 交叉引用 | `xrefs_to` | 查看谁引用了某地址/函数 |
| 搜索常量 | `find_bytes` / `find_regex` | 搜索算法特征常量 |
| 读取数据 | `get_bytes` / `get_string` / `get_int` | 读取内存/数据段内容 |
| 函数列表 | `list_funcs` / `lookup_funcs` | 查找目标函数 |
| 导入表 | `imports` | 查看外部函数引用 |
| 类型推断 | `infer_types` | AI辅助类型分析 |
| 重命名标注 | `rename` / `set_comments` / `set_type` | 标注分析结果 |
| 结构体 | `read_struct` / `search_structs` / `stack_frame` | 分析数据结构 |

---

## 完整分析流程

### Phase 1: 侦察（Reconnaissance）

**目标**：理解分析目标，建立初始上下文。

1. **读取 unidbg Java 代码**
   - 识别目标 SO 文件名
   - 识别入口函数地址或符号（如 `module.callFunction(emulator, 0x41680, ...)`）
   - 提取调用参数格式（JNI 参数、命令号、业务参数等）
   - 记录 JNI 补环境中的关键返回值

2. **IDA 初始分析**
   - `lookup_funcs`: 搜索入口函数名/地址
   - `decompile`: 反编译入口函数
   - `callees`: 获取入口函数的调用目标
   - `callgraph`: 绘制调用图全貌

3. **识别调度模式**
   - 根据命令号（如 10412、10418）定位实际处理函数
   - 对分发函数进行 `decompile`，找到目标 case 分支

### Phase 2: 输出定位与 Trace 分析

**目标**：确定最终输出数据的内存位置，开始反向追踪。

1. **确定输出格式**
   - 从 unidbg 运行结果获取最终输出
   - 将输出转换为字节序列用于搜索

2. **Trace 日志格式**
   ```
   [时间戳] Memory WRITE at 0x地址, data size = N, data value = 0x值, PC=RX@0x偏移[模块名]0x模块偏移, LR=RX@0x偏移[模块名]0x模块偏移
   ```
   关键字段：
   - `Memory WRITE at`: 数据写入目标地址
   - `data value`: 写入的值
   - `PC=...模块偏移`: 执行写入的指令地址（相对SO基址）
   - `LR=...模块偏移`: 调用者返回地址

3. **搜索策略**
   - 在 trace 中搜索目标字节值的写入记录
   - 对找到的 PC 地址，用 IDA `disasm` 查看具体指令

4. **字节序陷阱（关键）**

   ARM64 是小端序（Little-Endian），trace 日志中有两种视角，必须区分：

   | 场景 | 显示方式 | 说明 |
   |------|---------|------|
   | traceWrite `data value` | 寄存器原值 | `data value = 0x6767F6DB` 是寄存器里的值 |
   | 实际内存字节 | 小端存储 | 内存中是 `DB F6 67 67`（低字节在前）|
   | 最终 token 输出 | 逐字节顺序读取 | 读内存得到 `dbf66767` |
   | strb (1字节写入) | 无字节序问题 | 单字节不受端序影响 |
   | str/stp (4/8字节写入) | 需要反转 | `data value` 与内存字节顺序相反 |

   **转换规则**：
   - 看到 `data size = 1`（strb）：`data value` 直接就是写入的字节，无需转换
   - 看到 `data size = 2`（strh）：`data value = 0x3433` → 内存是 `33 34`（反转）
   - 看到 `data size = 4`（str）：`data value = 0x6767F6DB` → 内存是 `DB F6 67 67`（反转）
   - 看到 `data size = 8`（str x）：同理，8字节反转

   **实战示例**：
   ```
   trace: data value = 0x6767F6DB, data size = 4
   内存字节: DB F6 67 67
   token中: dbf66767

   trace: data value = 0x3433, data size = 2
   内存字节: 33 34
   即 ASCII "34"
   ```

   **核心原则**：traceWrite 的 `data value` 是寄存器视角（大端阅读序），内存实际存储是小端序。
   当你在 token 输出中看到 `dbf66767`，要反过来在 trace 中搜索 `0x6767F6DB`。

### Phase 3: 反向数据流追踪（Backward Data Flow Tracing）

**目标**：从输出字节开始，逐步追踪每个字节的来源。

**核心方法**：每条赋值指令都有操作数，追踪每个操作数的来源，形成树状追踪路径。

1. **指令级追踪模式**

   | 指令类型 | 示例 | 追踪方向 |
   |---------|------|----------|
   | 存储 | `strb w11, [x8, x10]` | 追踪 w11 的来源 |
   | 异或 | `eor w11, w11, w12` | 分别追踪两个操作数 |
   | 加载 | `ldrb w8, [x9, #0x94]` | 追踪内存地址内容 |
   | 移位 | `lsr w8, w8, #1` | 追踪 w8 的来源 |
   | 条件取反 | `cneg w9, w9, hi` | 追踪原始值和条件 |
   | 位或 | `orr w8, w8, w9, lsl #24` | 追踪两个操作数 |

2. **追踪分叉管理**
   当遇到二元操作（XOR、OR、ADD），产生两条追踪分支：
   ```
   eor w11, w11, w12
   +-- 分支A: w11 来源
   +-- 分支B: w12 来源
   ```
   用栈/队列管理待追踪分支。

3. **循环模式识别**
   同一 PC 出现多次 -> 循环。提取每次迭代的操作数值，观察序列模式。

4. **内存来源分类**
   - `get_bytes`: 读取IDA中该地址的静态数据
   - `xrefs_to`: 查看谁引用了该地址
   - .rodata/.data 段 -> 可能是硬编码常量
   - 堆上 -> 需要继续 traceWrite 追踪

### Phase 4: 函数级分析

**目标**：追踪到函数边界时，进行函数语义分析。

1. **函数反编译与语义识别**
   - `decompile`: 获取伪代码
   - `infer_types`: AI辅助类型推断
   - `callees`: 查看子函数调用
   - `imports`: 检查标准库函数

2. **常见函数模式**

   | 模式特征 | 可能的函数 |
   |---------|----------|
   | malloc + 逐字节拷贝 + 双引号检测 | JSON 字符串解析器 |
   | memcpy + 结构体偏移赋值 | 数据结构构造 |
   | atoi/strtol 调用 | 字符串转整数 |
   | 固定buffer + 轮操作 | 加密/哈希算法 |
   | 查表 + XOR + 移位循环 | CRC/校验算法 |

3. **断点验证 unidbg 模板**
   ```java
   emulator.attach().addBreakPoint(module.base + OFFSET, (emu, addr) -> {
       RegisterContext ctx = emu.getContext();
       UnidbgPointer ptr = ctx.getPointerArg(0);
       System.out.println("arg0: " + ptr.getString(0));
       Inspector.inspect(ptr.getByteArray(0, len), "tag");
       return true; // true=继续, false=停在断点
   });
   ```

### Phase 5: 算法特征识别（Pattern Recognition）

**目标**：通过常量、结构、操作模式识别已知算法。

#### 密码学常量指纹

**CRC32**:
- 反式多项式: `0xEDB88320`
- 特征: `(val >>> 1) ^ 0xEDB88320` 或 256 项查表
- 搜索: `find_bytes("20 83 B8 ED")`

**MD5**:
- IV: `0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476`
- K表首值: `0xD76AA478`, 64轮

**SHA-1**:
- IV: 同MD5 + `0xC3D2E1F0`, 80轮

**SHA-256**:
- IV: `0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A`
- K首值: `0x428A2F98`, 64轮
- 搜索: `find_bytes("67 E6 09 6A")` (LE)

**HMAC**:
- 结构: H((K xor opad) || H((K xor ipad) || message))
- ipad = 0x36 repeat, opad = 0x5C repeat
- 搜索: `find_bytes("36 36 36 36")` / `find_bytes("5C 5C 5C 5C")`

**AES**:
- S-box: `0x63, 0x7C, 0x77, 0x7B`
- Rcon: `0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36`
- 搜索: `find_bytes("63 7C 77 7B")`

**白盒AES (WBAES)**:
- 巨大查找表（数MB），无明显密钥
- T-box / Ty-box 结构, 16 个并行查表
- 表大小: 256x4字节(1KB)x16组

**RC4**:
- 256字节 S-box 初始化 (KSA)
- `j=(j+S[i]+key[i%keylen])%256`

**Base64**:
- 字符表: `ABCDEF...+/`
- 3字节转4字符

#### 非密码学特征

**时间戳处理模式（重要）**:

`gettimeofday64` 返回的时间戳在 SO 中的典型处理流程：

```
1. gettimeofday64 → 秒数（如 1735005915）
2. 转为32位十六进制: 0x6767F6DB
3. 小端存储到内存: DB F6 67 67
4. 取前N个字节作为 token 的一部分
```

**实战示例**：
```
时间戳: 1735005915 (十进制)
十六进制: 0x6767F6DB
小端字节: DB F6 67 67
token中: dbf66767 （取前4字节的hex字符串）
```

**验证方法**：
- 在 unidbg 中修改 `gettimeofday64` 返回值（固定时间戳）
- 如果 token 某段随之变化 → 确认为时间依赖
- 还原时：直接取当前时间戳，转hex，小端取字节

**注意**：
- 有时只取前 N 个字节（如取4字节 = 8个hex字符）
- 有时时间戳会作为随机数种子，而非直接嵌入
- 区分方式：改时间戳后，token该段是否等于时间戳的hex，还是完全不同的随机值
  - 等于hex → 直接嵌入
  - 不同但确定性变化 → 作为种子输入某算法
  - 完全随机 → 仅作为 PRNG 种子

- JSON解析: 双引号检测, 转义处理
- 字节累加: 逐字节求和作校验

### Phase 6: 输出分段与分类

| 类别 | 特征 | 还原方式 |
|------|------|----------|
| 硬编码常量 | 固定不变 | 直接使用固定值 |
| 输入派生 | 随输入变化 | 还原完整算法 |
| 时间依赖 | 改gettimeofday会变 | 使用时间或random |
| 随机数 | 每次不同 | random生成 |
| JSON字段 | 来自配置 | 从参数提取 |
| 校验值 | CRC/hash | 还原校验算法 |

**验证方法**：固定随机数种子，逐个改变输入参数，对比输出差异。

### Phase 7: 算法还原

1. 自底向上：从已识别基础算法开始，使用标准库
2. 白盒算法：提取查找表直接复用，或 DFA 提取密钥
3. 验证：用相同输入参数对比还原结果与 unidbg 输出

### Phase 8: 结果标注

在 IDA 中标注：
- `rename`: 重命名函数
- `set_comments`: 添加关键注释
- `set_type`: 设置参数/返回值类型
- `declare_type`: 声明自定义结构体

---

## 分析决策树

```
开始 -> 有trace? -> 是 -> 搜索目标数据写入点
                 -> 否 -> IDA静态分析入口

找到写入点? -> 是 -> 反向数据流追踪
            -> 否 -> 扩大搜索范围

追踪到指令? -> 简单赋值 -> 继续追踪来源
            -> 运算指令 -> 分叉追踪操作数
            -> 函数边界 -> 函数语义分析
            -> 硬编码加载 -> 记为常量,终止分支

识别到模式? -> 是 -> 确认算法,提取参数
            -> 否 -> 继续追踪/获取更多trace

所有分支完? -> 是 -> 分类,还原,验证
            -> 否 -> 处理剩余分支
```

---

## 实战检查清单

- [ ] 已读取unidbg代码，理解调用方式
- [ ] 已在IDA定位入口函数
- [ ] 已获取目标输出数据
- [ ] 已通过trace找到写入点
- [ ] 已完成所有追踪分支的反向分析
- [ ] 已识别所有子算法
- [ ] 已搜索密码学常量特征
- [ ] 输出各段已分类
- [ ] 已在IDA中标注结果
- [ ] 还原代码已验证
