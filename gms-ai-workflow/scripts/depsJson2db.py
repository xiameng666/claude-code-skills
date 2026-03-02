#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导入增强版 JSON 到 SQLite 数据库

用法:
    python import_enhanced_json.py <json_path> <db_path>

示例:
    python import_enhanced_json.py jeb-deps-enhanced.json gms-rename.db
"""

import json
import sqlite3
import sys
from pathlib import Path


# ============================================================================
# 表结构定义
# ============================================================================

CREATE_TABLES_SQL = """
-- 1. 类信息表（主表）
CREATE TABLE IF NOT EXISTS classes (
    signature TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    supertype TEXT,
    access_flags INTEGER,
    discovered BOOLEAN DEFAULT 0,
    analyzed BOOLEAN DEFAULT 0,
    documented BOOLEAN DEFAULT 0,
    restored BOOLEAN DEFAULT 0,
    compiled BOOLEAN DEFAULT 0,
    tags TEXT,
    module TEXT,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 接口实现表
CREATE TABLE IF NOT EXISTS class_interfaces (
    class_sig TEXT NOT NULL,
    interface_sig TEXT NOT NULL,
    PRIMARY KEY (class_sig, interface_sig),
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE
);

-- 3. 字段表
CREATE TABLE IF NOT EXISTS class_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_sig TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    access_flags INTEGER,
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE,
    UNIQUE(class_sig, name)
);

-- 4. 方法表
CREATE TABLE IF NOT EXISTS class_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_sig TEXT NOT NULL,
    name TEXT NOT NULL,
    return_type TEXT,
    access_flags INTEGER,
    signature TEXT,
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE,
    UNIQUE(class_sig, signature)
);

-- 5. 方法参数表
CREATE TABLE IF NOT EXISTS method_params (
    method_id INTEGER NOT NULL,
    param_index INTEGER NOT NULL,
    param_type TEXT NOT NULL,
    PRIMARY KEY (method_id, param_index),
    FOREIGN KEY (method_id) REFERENCES class_methods(id) ON DELETE CASCADE
);

-- 6. 方法体依赖表
CREATE TABLE IF NOT EXISTS method_body_deps (
    class_sig TEXT NOT NULL,
    dep_class_sig TEXT NOT NULL,
    PRIMARY KEY (class_sig, dep_class_sig),
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE
);

-- 7. 结构性依赖表
CREATE TABLE IF NOT EXISTS structural_deps (
    class_sig TEXT NOT NULL,
    dep_class_sig TEXT NOT NULL,
    dep_type TEXT NOT NULL,
    PRIMARY KEY (class_sig, dep_class_sig, dep_type),
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE
);

-- 8. 完整依赖图
CREATE TABLE IF NOT EXISTS dependencies (
    from_class TEXT NOT NULL,
    to_class TEXT NOT NULL,
    dep_source TEXT NOT NULL,
    PRIMARY KEY (from_class, to_class, dep_source),
    FOREIGN KEY (from_class) REFERENCES classes(signature) ON DELETE CASCADE
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(name);
CREATE INDEX IF NOT EXISTS idx_classes_supertype ON classes(supertype);
CREATE INDEX IF NOT EXISTS idx_classes_module ON classes(module);
CREATE INDEX IF NOT EXISTS idx_dependencies_from ON dependencies(from_class);
CREATE INDEX IF NOT EXISTS idx_dependencies_to ON dependencies(to_class);
CREATE INDEX IF NOT EXISTS idx_method_body_deps_class ON method_body_deps(class_sig);
CREATE INDEX IF NOT EXISTS idx_method_body_deps_dep ON method_body_deps(dep_class_sig);
CREATE INDEX IF NOT EXISTS idx_structural_deps_class ON structural_deps(class_sig);
CREATE INDEX IF NOT EXISTS idx_structural_deps_dep ON structural_deps(dep_class_sig);
CREATE INDEX IF NOT EXISTS idx_structural_deps_type ON structural_deps(dep_type);

-- 视图
CREATE VIEW IF NOT EXISTS v_class_stats AS
SELECT
    c.signature,
    c.name,
    c.module,
    COUNT(DISTINCT m.id) as method_count,
    COUNT(DISTINCT f.id) as field_count,
    COUNT(DISTINCT i.interface_sig) as interface_count,
    COUNT(DISTINCT mbd.dep_class_sig) as method_body_dep_count,
    COUNT(DISTINCT sd.dep_class_sig) as structural_dep_count
FROM classes c
LEFT JOIN class_methods m ON c.signature = m.class_sig
LEFT JOIN class_fields f ON c.signature = f.class_sig
LEFT JOIN class_interfaces i ON c.signature = i.class_sig
LEFT JOIN method_body_deps mbd ON c.signature = mbd.class_sig
LEFT JOIN structural_deps sd ON c.signature = sd.class_sig
GROUP BY c.signature;
"""


def create_tables(conn):
    """创建所有表"""
    cursor = conn.cursor()
    cursor.executescript(CREATE_TABLES_SQL)
    conn.commit()
    print('[+] Tables created successfully')


def import_enhanced_json(json_path: str, db_path: str):
    """
    导入增强版 JSON 到 SQLite 数据库

    Args:
        json_path: JSON 文件路径
        db_path: SQLite 数据库路径
    """

    # 检查文件
    json_file = Path(json_path)
    if not json_file.exists():
        print(f'[!] JSON file not found: {json_path}')
        sys.exit(1)

    print(f'[*] Loading JSON from: {json_path}')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    classes = data['classes']
    stats = data['stats']

    print(f'[*] JSON stats:')
    print(f'    Total classes: {stats["total"]}')
    print(f'    Skipped: {stats["skipped"]}')
    print(f'    Errors: {stats["errors"]}')
    print()

    # 连接数据库
    print(f'[*] Connecting to database: {db_path}')
    conn = sqlite3.connect(db_path)

    # 创建表
    print('[*] Creating tables...')
    create_tables(conn)
    print()

    # 开启事务
    cursor = conn.cursor()
    cursor.execute('BEGIN TRANSACTION')

    try:
        imported = 0

        print('[*] Importing classes...')

        for i, cls in enumerate(classes):
            class_sig = cls['signature']

            # 1. 插入类信息
            cursor.execute('''
                INSERT OR REPLACE INTO classes (signature, name, supertype, access_flags)
                VALUES (?, ?, ?, ?)
            ''', (
                class_sig,
                cls['name'],
                cls.get('supertype'),
                cls.get('accessFlags')
            ))

            # 2. 插入接口
            for interface in cls.get('interfaces', []):
                cursor.execute('''
                    INSERT OR IGNORE INTO class_interfaces (class_sig, interface_sig)
                    VALUES (?, ?)
                ''', (class_sig, interface))

                # 添加到结构性依赖
                cursor.execute('''
                    INSERT OR IGNORE INTO structural_deps (class_sig, dep_class_sig, dep_type)
                    VALUES (?, ?, 'interface')
                ''', (class_sig, interface))

            # 3. 插入父类依赖
            if cls.get('supertype'):
                cursor.execute('''
                    INSERT OR IGNORE INTO structural_deps (class_sig, dep_class_sig, dep_type)
                    VALUES (?, ?, 'supertype')
                ''', (class_sig, cls['supertype']))

            # 4. 插入字段
            for field in cls.get('fields', []):
                cursor.execute('''
                    INSERT OR IGNORE INTO class_fields (class_sig, name, type, access_flags)
                    VALUES (?, ?, ?, ?)
                ''', (
                    class_sig,
                    field['name'],
                    field['type'],
                    field.get('accessFlags')
                ))

                # 添加到结构性依赖
                cursor.execute('''
                    INSERT OR IGNORE INTO structural_deps (class_sig, dep_class_sig, dep_type)
                    VALUES (?, ?, 'field')
                ''', (class_sig, field['type']))

            # 5. 插入方法
            for method in cls.get('methods', []):
                # 构造方法签名
                method_sig = f"{class_sig}->{method['name']}"
                if method.get('paramTypes'):
                    param_str = ''.join(method['paramTypes'])
                    method_sig += f"({param_str})"
                else:
                    method_sig += "()"
                method_sig += method.get('returnType', 'V')

                cursor.execute('''
                    INSERT OR IGNORE INTO class_methods
                    (class_sig, name, return_type, access_flags, signature)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    class_sig,
                    method['name'],
                    method.get('returnType'),
                    method.get('accessFlags'),
                    method_sig
                ))

                method_id = cursor.lastrowid

                # 插入方法参数
                for idx, param_type in enumerate(method.get('paramTypes', [])):
                    cursor.execute('''
                        INSERT OR IGNORE INTO method_params (method_id, param_index, param_type)
                        VALUES (?, ?, ?)
                    ''', (method_id, idx, param_type))

                    # 添加到结构性依赖
                    cursor.execute('''
                        INSERT OR IGNORE INTO structural_deps (class_sig, dep_class_sig, dep_type)
                        VALUES (?, ?, 'method_param')
                    ''', (class_sig, param_type))

                # 返回类型依赖
                if method.get('returnType') and method['returnType'] != 'V':
                    cursor.execute('''
                        INSERT OR IGNORE INTO structural_deps (class_sig, dep_class_sig, dep_type)
                        VALUES (?, ?, 'method_return')
                    ''', (class_sig, method['returnType']))

            # 6. 插入方法体依赖
            for dep in cls.get('method_body_deps', []):
                cursor.execute('''
                    INSERT OR IGNORE INTO method_body_deps (class_sig, dep_class_sig)
                    VALUES (?, ?)
                ''', (class_sig, dep))

            # 7. 汇总到 dependencies 表
            # 结构性依赖
            cursor.execute('''
                INSERT OR IGNORE INTO dependencies (from_class, to_class, dep_source)
                SELECT DISTINCT class_sig, dep_class_sig, 'structural'
                FROM structural_deps
                WHERE class_sig = ?
            ''', (class_sig,))

            # 方法体依赖
            cursor.execute('''
                INSERT OR IGNORE INTO dependencies (from_class, to_class, dep_source)
                SELECT DISTINCT class_sig, dep_class_sig, 'method_body'
                FROM method_body_deps
                WHERE class_sig = ?
            ''', (class_sig,))

            imported += 1

            # 进度显示
            if (i + 1) % 1000 == 0:
                print(f'[+] Imported {i + 1}/{len(classes)} classes...')

        # 提交事务
        conn.commit()

        print()
        print(f'[+] Import complete!')
        print(f'    Total imported: {imported} classes')
        print()

        # 显示统计
        print('[*] Database statistics:')
        cursor.execute('SELECT COUNT(*) FROM classes')
        print(f'    Classes: {cursor.fetchone()[0]}')

        cursor.execute('SELECT COUNT(*) FROM class_methods')
        print(f'    Methods: {cursor.fetchone()[0]}')

        cursor.execute('SELECT COUNT(*) FROM class_fields')
        print(f'    Fields: {cursor.fetchone()[0]}')

        cursor.execute('SELECT COUNT(*) FROM method_body_deps')
        print(f'    Method body dependencies: {cursor.fetchone()[0]}')

        cursor.execute('SELECT COUNT(*) FROM structural_deps')
        print(f'    Structural dependencies: {cursor.fetchone()[0]}')

        cursor.execute('SELECT COUNT(DISTINCT from_class || to_class) FROM dependencies')
        print(f'    Total unique dependencies: {cursor.fetchone()[0]}')

    except Exception as e:
        conn.rollback()
        print(f'[!] Import failed: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python import_enhanced_json.py <json_path> <db_path>')
        print()
        print('Example:')
        print('  python import_enhanced_json.py jeb-deps-enhanced.json gms-rename.db')
        sys.exit(1)

    json_path = sys.argv[1]
    db_path = sys.argv[2]

    import_enhanced_json(json_path, db_path)
