# -*- coding: utf-8 -*-
"""
重命名同步系统

功能：
1. 管理类/方法/字段重命名索引 (SQLite)
2. 同步 MD 文件名 (混淆名_重命名.md)
3. 提供 MCP 工具接口

数据库结构：
- class_renames: 类重命名
- method_renames: 方法重命名（以类为基准）
- field_renames: 字段重命名（以类为基准）
"""

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path


class RenameSync:
    """重命名同步管理器"""

    def __init__(self, knowledge_dir: str):
        """
        @param knowledge_dir: 知识库目录，包含 gms-rename.db 和 notes/
        """
        self.knowledge_dir = knowledge_dir
        self.db_path = os.path.join(knowledge_dir, "gms-rename.db")
        self.notes_dir = os.path.join(knowledge_dir, "notes")

        self._ensure_dirs()
        self._init_db()

    @classmethod
    def init_knowledge_base(cls, knowledge_dir: str, project_name: str = "GMS"):
        """
        初始化知识库目录结构

        @param knowledge_dir: 知识库目录路径
        @param project_name: 项目名称
        @return: 初始化结果
        """
        # 创建目录结构
        dirs = [
            knowledge_dir,
            os.path.join(knowledge_dir, "notes"),
            os.path.join(knowledge_dir, "reports"),
            os.path.join(knowledge_dir, "logs"),
            os.path.join(knowledge_dir, "logs", "conflicts"),
            os.path.join(knowledge_dir, "logs", "failed"),
            os.path.join(knowledge_dir, "imports"),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

        # 初始化数据库
        sync = cls(knowledge_dir)

        # 创建 README
        readme_path = os.path.join(knowledge_dir, "notes", "README.md")
        if not os.path.exists(readme_path):
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"""# {project_name} 逆向知识库

## 目录结构

```
{project_name.lower()}-knowledge/
├── gms-rename.db          # 重命名索引
├── jeb-renames.txt        # 导出给 JEB
├── notes/                 # 类文件 + 模块文件
├── reports/               # 分析会话报告
├── logs/                  # 错误、冲突、失败记录
└── imports/               # 导入的原始数据
```

## 快速开始

1. 在 JEB 中运行 ExportDeps.py 导出 JSON
2. import_from_jeb_json("~/jeb-deps.json")
3. rename_class_with_sync("Labc;", "com.example.RealName")

## 模块列表

<!-- AI 自动维护 -->

## 统计

<!-- 调用 get_analysis_stats 更新 -->
""")

        # 创建错误日志文件
        error_log = os.path.join(knowledge_dir, "logs", "errors.log")
        if not os.path.exists(error_log):
            with open(error_log, 'w', encoding='utf-8') as f:
                f.write(f"# Error Log - {project_name}\n\n")

        return {
            "success": True,
            "knowledge_dir": knowledge_dir,
            "db_path": sync.db_path,
            "notes_dir": os.path.join(knowledge_dir, "notes"),
            "reports_dir": os.path.join(knowledge_dir, "reports"),
            "logs_dir": os.path.join(knowledge_dir, "logs"),
            "imports_dir": os.path.join(knowledge_dir, "imports"),
            "readme": readme_path,
            "message": f"知识库已初始化: {knowledge_dir}"
        }

    def _ensure_dirs(self):
        os.makedirs(self.knowledge_dir, exist_ok=True)
        os.makedirs(self.notes_dir, exist_ok=True)

    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 类重命名
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS class_renames (
                    obfuscated TEXT PRIMARY KEY,
                    renamed TEXT UNIQUE,
                    note TEXT,
                    md_created INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')

            # 方法重命名（以类为基准）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS method_renames (
                    class_obf TEXT NOT NULL,
                    method_sig TEXT NOT NULL,
                    renamed TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (class_obf, method_sig)
                )
            ''')

            # 字段重命名（以类为基准）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS field_renames (
                    class_obf TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    renamed TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (class_obf, field_name)
                )
            ''')

            # 历史记录
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rename_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rename_type TEXT NOT NULL,
                    class_obf TEXT,
                    old_name TEXT,
                    new_name TEXT,
                    extra TEXT,
                    note TEXT,
                    timestamp TEXT
                )
            ''')

            # 索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_method_class ON method_renames(class_obf)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_field_class ON field_renames(class_obf)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_class_renamed ON class_renames(renamed)')

            conn.commit()

    # ==================== 类重命名 ====================

    def rename_class(self, obfuscated: str, new_name: str, note: str = ""):
        """
        重命名类

        @return: {"success": bool, "old_name": str, "new_name": str, "md_file": str}
        """
        obfuscated = self._normalize_obfuscated(obfuscated)
        short_obf = self._get_short_name(obfuscated)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 检查冲突
            cursor.execute(
                "SELECT obfuscated FROM class_renames WHERE renamed = ? AND obfuscated != ?",
                (new_name, obfuscated)
            )
            if cursor.fetchone():
                return {"success": False, "error": f"命名冲突: '{new_name}' 已被使用"}

            # 获取旧名称
            cursor.execute("SELECT renamed FROM class_renames WHERE obfuscated = ?", (obfuscated,))
            row = cursor.fetchone()
            old_name = row[0] if row else None

            # 更新数据库
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO class_renames (obfuscated, renamed, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(obfuscated) DO UPDATE SET
                    renamed = excluded.renamed,
                    note = excluded.note,
                    updated_at = excluded.updated_at
            ''', (obfuscated, new_name, note, now, now))

            # 记录历史
            cursor.execute('''
                INSERT INTO rename_history (rename_type, class_obf, old_name, new_name, note, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('class', obfuscated, old_name, new_name, note, now))

            conn.commit()

        # 同步 MD 文件
        old_md = self._find_md_file(short_obf, old_name)
        new_md = self._get_md_filename(short_obf, new_name)

        if old_md and old_md != new_md:
            self._rename_md_file(old_md, new_md, obfuscated, new_name)
        elif not old_md:
            self._create_md_file(new_md, obfuscated, new_name)
        else:
            # 文件已存在，更新 frontmatter
            self._sync_frontmatter(obfuscated)

        return {
            "success": True,
            "old_name": old_name,
            "new_name": new_name,
            "md_file": os.path.basename(new_md)
        }

    def get_class_rename(self, obfuscated: str):
        """查询类重命名"""
        obfuscated = self._normalize_obfuscated(obfuscated)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT renamed FROM class_renames WHERE obfuscated = ?", (obfuscated,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_class_info(self, obfuscated: str):
        """
        获取类的完整信息（包括 MD 文件状态）

        如果 MD 文件不存在，会自动创建

        @param obfuscated: 类的混淆名
        @return: dict 包含 obfuscated, renamed, md_created, md_path 等
        """
        obfuscated = self._normalize_obfuscated(obfuscated)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT obfuscated, renamed, note, md_created
                FROM class_renames WHERE obfuscated = ?
            ''', (obfuscated,))
            row = cursor.fetchone()

        if not row:
            return None

        result = {
            'obfuscated': row[0],
            'renamed': row[1],
            'note': row[2],
            'md_created': bool(row[3]) if row[3] else False
        }

        # 检查/创建 MD 文件
        md_path = self._get_md_filename(obfuscated, result['renamed'])
        result['md_path'] = md_path

        if not result['md_created'] or not os.path.exists(md_path):
            # 按需创建 MD 文件
            self._create_md_file(md_path, obfuscated, result['renamed'] or obfuscated)
            result['md_created'] = True

            # 更新数据库标志
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE class_renames SET md_created = 1, updated_at = ?
                    WHERE obfuscated = ?
                ''', (datetime.now().isoformat(), obfuscated))
                conn.commit()

        return result

    # ==================== 方法重命名 ====================

    def rename_method(self, class_obf: str, method_sig: str, new_name: str, note: str = ""):
        """
        重命名方法

        @param class_obf: 类混淆名 (Lfvxn;)
        @param method_sig: 方法签名 (a(Landroid/location/Location;)V) 或简单方法名
        @param new_name: 新方法名
        @param note: 备注
        """
        class_obf = self._normalize_obfuscated(class_obf)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 获取旧名称
            cursor.execute('''
                SELECT renamed FROM method_renames
                WHERE class_obf = ? AND method_sig = ?
            ''', (class_obf, method_sig))
            row = cursor.fetchone()
            old_name = row[0] if row else None

            # 更新数据库
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO method_renames (class_obf, method_sig, renamed, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(class_obf, method_sig) DO UPDATE SET
                    renamed = excluded.renamed,
                    note = excluded.note,
                    updated_at = excluded.updated_at
            ''', (class_obf, method_sig, new_name, note, now, now))

            # 记录历史
            cursor.execute('''
                INSERT INTO rename_history (rename_type, class_obf, old_name, new_name, extra, note, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('method', class_obf, old_name, new_name, method_sig, note, now))

            conn.commit()

        # 同步更新 MD 文件的 frontmatter
        self._sync_frontmatter(class_obf)

        return {
            "success": True,
            "class": class_obf,
            "method_sig": method_sig,
            "old_name": old_name,
            "new_name": new_name
        }

    def get_method_rename(self, class_obf: str, method_sig: str):
        """查询方法重命名"""
        class_obf = self._normalize_obfuscated(class_obf)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT renamed FROM method_renames
                WHERE class_obf = ? AND method_sig = ?
            ''', (class_obf, method_sig))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_all_method_renames(self, class_obf: str):
        """获取某个类的所有方法重命名"""
        class_obf = self._normalize_obfuscated(class_obf)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT method_sig, renamed, note FROM method_renames
                WHERE class_obf = ?
            ''', (class_obf,))
            return [
                {"method_sig": r[0], "renamed": r[1], "note": r[2]}
                for r in cursor.fetchall()
            ]

    # ==================== 字段重命名 ====================

    def rename_field(self, class_obf: str, field_name: str, new_name: str, note: str = ""):
        """
        重命名字段

        @param class_obf: 类混淆名 (Lfvxn;)
        @param field_name: 字段名
        @param new_name: 新字段名 (mLocationCache)
        @param note: 备注
        """
        class_obf = self._normalize_obfuscated(class_obf)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 获取旧名称
            cursor.execute('''
                SELECT renamed FROM field_renames
                WHERE class_obf = ? AND field_name = ?
            ''', (class_obf, field_name))
            row = cursor.fetchone()
            old_name = row[0] if row else None

            # 更新数据库
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO field_renames (class_obf, field_name, renamed, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(class_obf, field_name) DO UPDATE SET
                    renamed = excluded.renamed,
                    note = excluded.note,
                    updated_at = excluded.updated_at
            ''', (class_obf, field_name, new_name, note, now, now))

            # 记录历史
            cursor.execute('''
                INSERT INTO rename_history (rename_type, class_obf, old_name, new_name, extra, note, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('field', class_obf, old_name, new_name, field_name, note, now))

            conn.commit()

        # 同步更新 MD 文件的 frontmatter
        self._sync_frontmatter(class_obf)

        return {
            "success": True,
            "class": class_obf,
            "field_name": field_name,
            "old_name": old_name,
            "new_name": new_name
        }

    def get_field_rename(self, class_obf: str, field_name: str):
        """查询字段重命名"""
        class_obf = self._normalize_obfuscated(class_obf)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT renamed FROM field_renames
                WHERE class_obf = ? AND field_name = ?
            ''', (class_obf, field_name))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_all_field_renames(self, class_obf: str):
        """获取某个类的所有字段重命名"""
        class_obf = self._normalize_obfuscated(class_obf)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT field_name, renamed, note FROM field_renames
                WHERE class_obf = ?
            ''', (class_obf,))
            return [
                {"field_name": r[0], "renamed": r[1], "note": r[2]}
                for r in cursor.fetchall()
            ]

    # ==================== 批量操作 ====================

    def get_all_renames(self, class_obf: str):
        """获取某个类的所有重命名（类+方法+字段）"""
        class_obf = self._normalize_obfuscated(class_obf)
        return {
            "class": self.get_class_rename(class_obf),
            "methods": self.get_all_method_renames(class_obf),
            "fields": self.get_all_field_renames(class_obf)
        }

    # ==================== 搜索与统计 ====================

    def search(self, keyword: str, limit: int = 50):
        """搜索所有重命名"""
        keyword = f"%{keyword}%"
        results = {"classes": [], "methods": [], "fields": []}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 搜索类
            cursor.execute('''
                SELECT obfuscated, renamed, note FROM class_renames
                WHERE obfuscated LIKE ? OR renamed LIKE ?
                LIMIT ?
            ''', (keyword, keyword, limit))
            results["classes"] = [
                {"obfuscated": r[0], "renamed": r[1], "note": r[2]}
                for r in cursor.fetchall()
            ]

            # 搜索方法
            cursor.execute('''
                SELECT class_obf, method_sig, renamed, note FROM method_renames
                WHERE method_sig LIKE ? OR renamed LIKE ?
                LIMIT ?
            ''', (keyword, keyword, limit))
            results["methods"] = [
                {"class": r[0], "method_sig": r[1], "renamed": r[2], "note": r[3]}
                for r in cursor.fetchall()
            ]

            # 搜索字段
            cursor.execute('''
                SELECT class_obf, field_name, renamed, note FROM field_renames
                WHERE field_name LIKE ? OR renamed LIKE ?
                LIMIT ?
            ''', (keyword, keyword, limit))
            results["fields"] = [
                {"class": r[0], "field_name": r[1], "renamed": r[2], "note": r[3]}
                for r in cursor.fetchall()
            ]

        return results

    def get_stats(self):
        """统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM class_renames")
            class_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM method_renames")
            method_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM field_renames")
            field_count = cursor.fetchone()[0]

            cursor.execute("SELECT MAX(updated_at) FROM class_renames")
            last_updated = cursor.fetchone()[0]

        return {
            "class_count": class_count,
            "method_count": method_count,
            "field_count": field_count,
            "total_count": class_count + method_count + field_count,
            "last_updated": last_updated,
            "db_path": self.db_path
        }

    # ==================== 导出 ====================

    def export_to_jeb(self, output_path: str = None):
        """导出为 JEB 格式"""
        if output_path is None:
            output_path = os.path.join(self.knowledge_dir, "jeb-renames.txt")

        lines = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 类重命名
            cursor.execute("SELECT obfuscated, renamed FROM class_renames")
            for row in cursor.fetchall():
                lines.append(f"class\t{row[0]}\t{row[1]}")

            # 方法重命名
            cursor.execute("SELECT class_obf, method_sig, renamed FROM method_renames")
            for row in cursor.fetchall():
                lines.append(f"method\t{row[0]}\t{row[1]}\t{row[2]}")

            # 字段重命名
            cursor.execute("SELECT class_obf, field_name, renamed FROM field_renames")
            for row in cursor.fetchall():
                lines.append(f"field\t{row[0]}\t{row[1]}\t{row[2]}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return output_path

    # ==================== 名称规范化 ====================

    def _normalize_obfuscated(self, obfuscated: str) -> str:
        """
        将各种格式的类名规范化为 JNI 签名格式

        支持输入格式：
        - "abc" → "Labc;"
        - "com.example.Foo" → "Lcom/example/Foo;"
        - "Lcom/example/Foo;" → "Lcom/example/Foo;" (不变)

        @param obfuscated: 类名（任意格式）
        @return: JNI 签名格式
        """
        if not obfuscated:
            return obfuscated

        # 已经是 JNI 格式
        if obfuscated.startswith("L") and obfuscated.endswith(";"):
            return obfuscated

        # Java 格式 (com.example.Foo) 转换为 JNI 格式
        if "." in obfuscated:
            return "L" + obfuscated.replace(".", "/") + ";"

        # 简短名称 (abc) 转换为 JNI 格式
        return "L" + obfuscated + ";"

    # ==================== MD 文件操作 ====================

    def _get_short_name(self, obfuscated: str):
        """从混淆名提取短名：Lcom/abc/Xyz; → Xyz"""
        name = obfuscated.replace("L", "").replace(";", "")
        return name.split("/")[-1]

    def _get_path_name(self, obfuscated: str):
        """
        从混淆名提取完整路径名（用于唯一文件名）
        Lcom/abc/Xyz; → com_abc_Xyz
        """
        name = obfuscated.replace("L", "").replace(";", "")
        return name.replace("/", "_")

    def _get_md_filename(self, obfuscated: str, renamed: str or None):
        """
        生成唯一的 MD 文件名（使用完整路径避免冲突）

        例如：
        - Lcom/abc/Xyz; → com_abc_Xyz.md
        - 重命名后 → com_abc_Xyz_RenamedClass.md
        """
        path_name = self._get_path_name(obfuscated)
        if renamed:
            short_renamed = renamed.split(".")[-1]
            return os.path.join(self.notes_dir, f"{path_name}_{short_renamed}.md")
        else:
            return os.path.join(self.notes_dir, f"{path_name}.md")

    def _find_md_file(self, obfuscated: str, current_name: str or None):
        """查找现有的 MD 文件"""
        import glob
        path_name = self._get_path_name(obfuscated)
        pattern = os.path.join(self.notes_dir, f"{path_name}*.md")
        files = glob.glob(pattern)
        return files[0] if files else None

    def _rename_md_file(self, old_path: str, new_path: str, obfuscated: str, renamed: str):
        """重命名 MD 文件"""
        if os.path.exists(old_path):
            with open(old_path, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = ""

        content = self._update_md_header(content, obfuscated, renamed)

        with open(new_path, 'w', encoding='utf-8') as f:
            f.write(content)

        if old_path != new_path and os.path.exists(old_path):
            os.remove(old_path)

    def _create_md_file(self, path: str, obfuscated: str, renamed: str):
        """创建新的 MD 文件（精简版）"""
        short_obf = self._get_short_name(obfuscated)
        short_renamed = renamed.split(".")[-1]

        content = f"""---
obfuscated: "{obfuscated}"
renamed: "{renamed}"
confidence: pending
tags: [status/pending]
---

## 业务功能

<!-- AI 填写：一句话描述这个类的用途 -->

## 关联

<!-- AI 填写：使用 [[混淆名_重命名]] 格式 -->

## 笔记

<!-- AI 填写：关键发现、特殊逻辑、注意事项 -->

## 历史

| 时间 | 操作 | 发现 |
|------|------|------|
| {datetime.now().strftime('%Y-%m-%d')} | 初始化 | 创建类文件 |
"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _update_md_header(self, content: str, obfuscated: str, renamed: str):
        """更新 MD 文件头部"""
        new_header = f"""```rename
混淆名: {obfuscated}
重命名: {renamed}
```"""

        pattern = r'```rename\n[\s\S]*?\n```'
        if re.search(pattern, content):
            content = re.sub(pattern, new_header, content)
        else:
            title_pattern = r'^(# .+\n)'
            if re.search(title_pattern, content):
                content = re.sub(title_pattern, r'\1\n' + new_header + '\n', content)

        return content

    def _sync_frontmatter(self, class_obf: str):
        """
        同步更新 MD 文件的 frontmatter（精简版，只更新类名）
        """
        short_obf = self._get_short_name(class_obf)
        renamed = self.get_class_rename(class_obf)

        if not renamed:
            return

        md_path = self._find_md_file(short_obf, renamed)
        if not md_path:
            # 如果文件不存在，创建它
            new_md = self._get_md_filename(short_obf, renamed)
            self._create_md_file(new_md, class_obf, renamed)
            return

        # 读取现有内容
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 构建新的 frontmatter（精简版）
        new_frontmatter = f"""---
obfuscated: "{class_obf}"
renamed: "{renamed}"
tags: [gms/reverse, status/pending]
---"""

        # 替换现有的 frontmatter
        pattern = r'^---\n[\s\S]*?\n---\n'
        if re.search(pattern, content):
            new_content = re.sub(pattern, new_frontmatter + "\n", content)
        else:
            new_content = new_frontmatter + "\n\n" + content

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

    def import_from_jeb_json(self, json_path: str, batch_size: int = 20000):
        """
        从 JEB 导出的 JSON 文件批量导入类信息到数据库

        注意：此方法只导入数据库记录，不创建 MD 文件。
        MD 文件会在 AI 分析时按需创建（调用 get_class_info 方法）。

        @param json_path: JEB 导出的 JSON 文件路径
        @param batch_size: 批量插入的批次大小
        @return: 导入统计
        """
        # 优先用 orjson（快 5-10x），fallback 到标准 json
        try:
            import orjson
            print("[导入] 使用 orjson 加速读取")
            with open(json_path, 'rb') as f:
                data = orjson.loads(f.read())
        except ImportError:
            import json
            print("[导入] 使用标准 json 读取")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

        classes = data.get('classes', [])
        total = len(classes)
        print(f"[导入] 共 {total} 个类")

        # 单连接 + WAL 模式，避免反复开关连接
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        cursor = conn.cursor()

        try:
            # 1. 查询已存在的记录
            cursor.execute("SELECT obfuscated FROM class_renames")
            existing_sigs = {row[0] for row in cursor.fetchall()}
            print(f"[导入] 已存在 {len(existing_sigs)} 条记录")

            # 2. 过滤新记录
            new_sigs = [cls['signature'] for cls in classes
                        if cls.get('signature') and cls['signature'] not in existing_sigs]
            skipped = total - len(new_sigs)
            print(f"[导入] 新记录 {len(new_sigs)} 条，跳过 {skipped} 条")

            if not new_sigs:
                return {'total': total, 'imported': 0, 'skipped': skipped}

            # 3. 单事务批量插入
            now = datetime.now().isoformat()
            imported = 0
            for i in range(0, len(new_sigs), batch_size):
                batch = [(sig, 'imported from JEB', now, now)
                         for sig in new_sigs[i:i + batch_size]]
                cursor.executemany(
                    "INSERT OR IGNORE INTO class_renames "
                    "(obfuscated, renamed, note, md_created, created_at, updated_at) "
                    "VALUES (?, NULL, ?, 0, ?, ?)", batch)
                imported += cursor.rowcount
                print(f"[导入] {min(i + batch_size, len(new_sigs))}/{len(new_sigs)}")

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

        print(f"[导入] 完成! 插入 {imported} 条")
        return {'total': total, 'imported': imported, 'skipped': skipped}


# CLI
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 3:
        print("""
RenameSync - 重命名同步系统

用法:
  python rename_sync.py <knowledge_dir> <command> [args...]

命令:
  class <obfuscated> <new_name> [note]    重命名类
  method <class_obf> <method_sig> <new_name> [note]  重命名方法
  field <class_obf> <field_name> <new_name> [note]   重命名字段
  get-class <obfuscated>                   查询类重命名
  get-method <class_obf> <method_sig>      查询方法重命名
  get-field <class_obf> <field_name>       查询字段重命名
  get-all <class_obf>                      获取类的所有重命名
  search <keyword>                         搜索
  stats                                    统计
  export                                   导出 JEB 格式

示例:
  python rename_sync.py ./gms-knowledge class "Lfvxn;" "com.google.location.LocationClient"
  python rename_sync.py ./gms-knowledge method "Lfvxn;" "a" "requestLocation"
  python rename_sync.py ./gms-knowledge field "Lfvxn;" "a" "mLocationCache"
""")
        sys.exit(0)

    knowledge_dir = sys.argv[1]
    cmd = sys.argv[2]

    sync = RenameSync(knowledge_dir)

    if cmd == "class":
        result = sync.rename_class(sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else "")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "method":
        result = sync.rename_method(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6] if len(sys.argv) > 6 else "")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "field":
        result = sync.rename_field(sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6] if len(sys.argv) > 6 else "")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "get-class":
        result = sync.get_class_rename(sys.argv[3])
        print(result or "(未重命名)")

    elif cmd == "get-method":
        result = sync.get_method_rename(sys.argv[3], sys.argv[4])
        print(result or "(未重命名)")

    elif cmd == "get-field":
        result = sync.get_field_rename(sys.argv[3], sys.argv[4])
        print(result or "(未重命名)")

    elif cmd == "get-all":
        result = sync.get_all_renames(sys.argv[3])
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "search":
        results = sync.search(sys.argv[3])
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif cmd == "stats":
        print(json.dumps(sync.get_stats(), indent=2, ensure_ascii=False))

    elif cmd == "export":
        path = sync.export_to_jeb()
        print(f"Exported to: {path}")
