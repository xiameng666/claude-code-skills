# -*- coding: utf-8 -*-
"""
AI 工作流模块

此模块提供 AI 辅助逆向分析的工作流功能：
1. 从数据库读取类信息
2. 按需创建 MD 分析文件
3. 准备模块分析上下文
4. 生成分析报告

依赖：
- rename_sync.py (RenameSync 类)

使用场景：
- AI 调用 MCP 工具进行逆向分析
- CLI 手动执行分析任务
"""

import os
import re
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

# 导入独立的重命名同步工具（同一目录下直接导入）
from .rename_sync import RenameSync


class AIWorkflow:
    """AI 辅助逆向分析工作流"""

    def __init__(self, knowledge_dir: str):
        """
        @param knowledge_dir: 知识库目录
        """
        self.knowledge_dir = knowledge_dir
        self.notes_dir = os.path.join(knowledge_dir, "notes")
        self.reports_dir = os.path.join(knowledge_dir, "reports")
        self._rename_sync = RenameSync(knowledge_dir)

    # ==================== 类查询（按需创建 MD）====================

    def get_class_info(self, obfuscated: str) -> Optional[Dict]:
        """
        获取类的完整信息（按需创建 MD 文件）

        这是 AI 工作流的核心方法：
        1. 从数据库查询类信息
        2. 如果 MD 文件不存在，自动创建
        3. 返回完整信息供 AI 分析

        @param obfuscated: 类的混淆名（支持多种格式）
        @return: 类信息字典，包含 obfuscated, renamed, md_path 等
        """
        return self._rename_sync.get_class_info(obfuscated)

    def list_classes(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        列出数据库中的类（支持分页）

        @param limit: 返回数量限制
        @param offset: 偏移量
        @return: 类列表
        """
        with sqlite3.connect(self._rename_sync.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT obfuscated, renamed, md_created, note
                FROM class_renames
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            rows = cursor.fetchall()

        return [
            {
                "obfuscated": row[0],
                "renamed": row[1],
                "md_created": bool(row[2]),
                "note": row[3]
            }
            for row in rows
        ]

    def search_classes(self, keyword: str, limit: int = 50) -> List[Dict]:
        """
        搜索类（按混淆名或重命名）

        @param keyword: 搜索关键词
        @param limit: 最大返回数量
        """
        pattern = f"%{keyword}%"
        with sqlite3.connect(self._rename_sync.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT obfuscated, renamed, md_created
                FROM class_renames
                WHERE obfuscated LIKE ? OR renamed LIKE ?
                LIMIT ?
            ''', (pattern, pattern, limit))
            rows = cursor.fetchall()

        return [
            {
                "obfuscated": row[0],
                "renamed": row[1],
                "md_created": bool(row[2])
            }
            for row in rows
        ]

    # ==================== MD 文件读取 ====================

    def get_class_md_content(self, obfuscated: str) -> Optional[str]:
        """
        获取类的 MD 分析内容（按需创建）

        @param obfuscated: 类的混淆名
        @return: MD 文件内容，如果不存在返回 None
        """
        info = self.get_class_info(obfuscated)
        if not info:
            return None

        md_path = info.get("md_path")
        if not md_path or not os.path.exists(md_path):
            return None

        with open(md_path, 'r', encoding='utf-8') as f:
            return f.read()

    def update_class_md(self, obfuscated: str, content: str) -> bool:
        """
        更新类的 MD 文件内容

        @param obfuscated: 类的混淆名
        @param content: 新的 MD 内容
        @return: 是否成功
        """
        info = self.get_class_info(obfuscated)
        if not info:
            return False

        md_path = info.get("md_path")
        if not md_path:
            return False

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    # ==================== 统计分析 ====================

    def get_stats(self) -> Dict:
        """获取分析统计"""
        with sqlite3.connect(self._rename_sync.db_path) as conn:
            cursor = conn.cursor()

            # 总类数
            cursor.execute("SELECT COUNT(*) FROM class_renames")
            total = cursor.fetchone()[0]

            # 已创建 MD 的类数
            cursor.execute("SELECT COUNT(*) FROM class_renames WHERE md_created = 1")
            analyzed = cursor.fetchone()[0]

            # 已重命名的类数
            cursor.execute("SELECT COUNT(*) FROM class_renames WHERE renamed IS NOT NULL")
            renamed_count = cursor.fetchone()[0]

            # 方法/字段重命名数
            cursor.execute("SELECT COUNT(*) FROM method_renames")
            method_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM field_renames")
            field_count = cursor.fetchone()[0]

        return {
            "total_classes": total,
            "analyzed_classes": analyzed,
            "pending_classes": total - analyzed,
            "renamed_classes": renamed_count,
            "renamed_methods": method_count,
            "renamed_fields": field_count
        }

    # ==================== 模块分析（AI 辅助）====================

    def prepare_module_context(self, seed_classes: List[str]) -> str:
        """
        准备模块分析的上下文

        @param seed_classes: 种子类列表（混淆名）
        @return: 供 AI 分析的上下文字符串
        """
        context_parts = ["# 模块分析上下文\n"]

        # 1. 统计摘要
        stats = self.get_stats()
        context_parts.append(f"""
## 统计摘要

- 总类数: {stats['total_classes']:,}
- 已分析: {stats['analyzed_classes']:,}
- 已重命名: {stats['renamed_classes']:,}
- 方法重命名: {stats['renamed_methods']:,}
- 字段重命名: {stats['renamed_fields']:,}

""")

        # 2. 种子类的详细信息
        context_parts.append("## 种子类详细分析\n")

        for seed in seed_classes:
            info = self.get_class_info(seed)
            if not info:
                context_parts.append(f"\n### {seed}\n\n> 未在数据库中找到\n")
                continue

            context_parts.append(f"\n### {seed}\n")

            if info.get("renamed"):
                context_parts.append(f"\n> 重命名: `{info['renamed']}`\n")

            # 读取 MD 内容
            md_content = self.get_class_md_content(seed)
            if md_content:
                # 提取关键部分（限制长度）
                context_parts.append("\n```\n")
                context_parts.append(md_content[:2000])
                context_parts.append("\n```\n")

        return "".join(context_parts)

    # ==================== 报告生成 ====================

    def create_session_report(self, seed_class: str, analyzed_classes: List[Dict],
                              findings: List[str], renames: List[Dict],
                              issues: List[str], next_steps: List[str]) -> str:
        """
        创建分析会话报告

        @param seed_class: 种子类
        @param analyzed_classes: 分析过的类列表
        @param findings: 发现列表
        @param renames: 重命名列表
        @param issues: 问题列表
        @param next_steps: 下一步计划
        @return: 报告文件路径
        """
        os.makedirs(self.reports_dir, exist_ok=True)
        date_str = datetime.now().strftime('%Y-%m-%d')
        report_path = os.path.join(self.reports_dir, f"session_{date_str}.md")

        content = f"""# 分析会话 {date_str}

> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 种子类

- {seed_class}

---

## 分析范围

| 类 | 状态 | 置信度 |
|----|------|--------|
"""
        for cls in analyzed_classes:
            content += f"| {cls.get('name', '-')} | {cls.get('status', '-')} | {cls.get('confidence', '-')} |\n"

        content += """
---

## 发现

"""
        for f in findings:
            content += f"- {f}\n"

        content += """
---

## 重命名

| 原名 | 重命名 | 置信度 |
|------|--------|--------|
"""
        for r in renames:
            content += f"| {r.get('old', '-')} | {r.get('new', '-')} | {r.get('confidence', '-')} |\n"

        content += """
---

## 问题

"""
        if issues:
            for i in issues:
                content += f"- {i}\n"
        else:
            content += "_无_\n"

        content += """
---

## 下一步

"""
        for step in next_steps:
            content += f"- {step}\n"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return report_path

    def generate_module_report(self, module_name: str, classes: List[Dict],
                               structure: str = "") -> str:
        """
        生成模块报告

        @param module_name: 模块名称（如 gms/location）
        @param classes: 模块包含的类列表
        @param structure: mermaid 类图（AI 生成）
        @return: 报告文件路径
        """
        report_path = os.path.join(self.notes_dir, f"module_{module_name.replace('/', '_')}.md")

        lines = [f"""---
module: "{module_name}"
status: active
tags: [module, {module_name}]
---

# {module_name} 模块

> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
> 类数量: {len(classes)}

---

## 模块概述

<!-- AI 填写：模块的整体功能描述 -->

---

## 类结构

{structure if structure else '<!-- AI 填写：mermaid 类图，展示类之间的关系 -->'}

---

## 类列表

| 类 | 功能 | 状态 | 置信度 |
|----|------|------|--------|
"""]

        for cls in classes:
            obf = cls.get("obfuscated", "")
            renamed = cls.get("renamed", "-")
            status = cls.get("status", "pending")
            confidence = cls.get("confidence", "pending")
            short = obf.replace("L", "").replace(";", "").split("/")[-1]
            display_name = renamed.split(".")[-1] if renamed != "-" else short
            lines.append(f"| [[{short}_{display_name}\\|{display_name}]] | - | {status} | {confidence} |\n")

        lines.append("""
---

## 分析进度

<!-- AI 填写：当前模块的分析进度和下一步计划 -->

---

## 历史

| 时间 | 操作 | 发现 |
|------|------|------|
| """ + datetime.now().strftime('%Y-%m-%d') + """ | 初始化 | 创建模块文件 |
""")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        return report_path


# CLI 接口
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 3:
        print("""
AIWorkflow - AI 辅助逆向分析工作流

用法:
  python ai_workflow.py <knowledge_dir> <command> [args...]

命令:
  stats                         统计信息
  list [limit]                 列出类
  search <keyword>              搜索类
  get <obfuscated>             获取类信息（按需创建 MD）
  md <obfuscated>              获取 MD 内容
  context <class1> <class2>... 准备模块分析上下文

示例:
  python ai_workflow.py ./knowledge stats
  python ai_workflow.py ./knowledge get "Lfvxn;"
  python ai_workflow.py ./knowledge context "Lfvxn;" "Lcmue;"
""")
        sys.exit(0)

    knowledge_dir = sys.argv[1]
    cmd = sys.argv[2]

    workflow = AIWorkflow(knowledge_dir)

    if cmd == "stats":
        stats = workflow.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif cmd == "list":
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        classes = workflow.list_classes(limit)
        for cls in classes:
            status = "[MD]" if cls["md_created"] else "[--]"
            renamed = f" -> {cls['renamed']}" if cls["renamed"] else ""
            print(f"{status} {cls['obfuscated']}{renamed}")

    elif cmd == "search":
        keyword = sys.argv[3]
        results = workflow.search_classes(keyword)
        for r in results:
            print(f"{r['obfuscated']} -> {r['renamed']}")

    elif cmd == "get":
        obf = sys.argv[3]
        info = workflow.get_class_info(obf)
        if info:
            print(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            print("(未找到)")

    elif cmd == "md":
        obf = sys.argv[3]
        content = workflow.get_class_md_content(obf)
        print(content or "(未找到)")

    elif cmd == "context":
        seed_classes = sys.argv[3:]
        context = workflow.prepare_module_context(seed_classes)
        print(context)
