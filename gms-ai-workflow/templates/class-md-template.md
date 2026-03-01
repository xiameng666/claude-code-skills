# 类 MD 文件模板

```markdown
---
obfuscated: "Lxxx;"
renamed: "com.example.FullClassName"
confidence: high|medium|low
is_leaf: true|false
is_root: true|false
in_degree: N
out_degree: N
analysis_depth: N
tags: [tag1, tag2, tag3]
---

## 业务功能

<!-- 一句话描述这个类的用途 -->

## 依赖关系

### 依赖的类（出边，out_degree=N）

| 类 | 类型 | 重命名 | 说明 |
|----|------|--------|------|
| [[Lyyy;|RenamedName]] | field_type | ✓ | 字段依赖 |
| [[Lzzz;]] | implements | - | 实现的接口 |

### 被依赖（入边，in_degree=N）

| 类 | 类型 | 说明 |
|----|------|------|
| [[Laaa;|ClassName]] | field_type | 持有此类的实例 |

## 所属模块

[[module_xxx]]

## 分析笔记

<!-- AI 填写：关键发现、特殊逻辑、注意事项 -->

## 历史

| 时间 | 操作 | 发现 |
|------|------|------|
| YYYY-MM-DD | 初始化 | 创建类文件 |
| YYYY-MM-DD | 图论分析 | DFS 遍历发现 N 个依赖 |
```
