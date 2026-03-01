# 命名规范

## 命名置信度

| 置信度 | 条件 | 示例 |
|--------|------|------|
| **high** | toString()、注解、字符串明确 | `FusionEngine` (toString 返回) |
| **medium** | 基于接口/依赖推断 | `LocationEngine` (实现 LocationListener) |
| **low** | 纯粹猜测 | `Manager` (无明确线索) |

## 类命名规范

- 完整包名：`com.google.android.location.fused.FusionEngine`
- 简短名称：`FusionEngine`

## 字段命名规范

| 类型 | 命名风格 | 示例 |
|------|----------|------|
| 成员变量 | mPrefix + 描述 | mLocationCache |
| 静态常量 | UPPER_CASE | FLUSH_INTERVAL_MS |
| 布尔标志 | is/has 前缀 | isRunning, hasRequest |
| 回调 | Callback 后缀 | locationCallback |
| 监听器 | Listener 后缀 | locationListener |
| 处理器 | Handler 后缀 | locationHandler |
| 管理器 | Manager 后缀 | flushAlarmManager |

## 方法命名规范

| 类型 | 命名风格 | 示例 |
|------|----------|------|
| 回调方法 | on 前缀 | onLocationUpdate, onProviderChanged |
| 获取方法 | get 前缀 | getFusedLocation, getLocation |
| 设置方法 | set 前缀 | setUpdateInterval |
| 状态检查 | is/has 前缀 | hasActiveRequest, isRunning |
| 处理方法 | handle/process 前缀 | handleLocation, processData |
| 刷新方法 | flush 前缀 | flushPendingLocations |
