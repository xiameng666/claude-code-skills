"""
数据库表结构设计 - 适配增强版 JSON 格式

基于 ExportDepsEnhancedFixed.py 导出的 JSON 格式
"""

# ============================================================================
# 核心表
# ============================================================================

CREATE_TABLES = """
-- 1. 类信息表（主表）
CREATE TABLE IF NOT EXISTS classes (
    signature TEXT PRIMARY KEY,           -- 类签名 (如 LFusionEngine;)
    name TEXT NOT NULL,                   -- 类名 (如 FusionEngine)
    supertype TEXT,                       -- 父类签名
    access_flags INTEGER,                 -- 访问标志
    discovered BOOLEAN DEFAULT 0,         -- Phase 3: 已发现
    analyzed BOOLEAN DEFAULT 0,           -- Phase 4: 已梳理
    documented BOOLEAN DEFAULT 0,         -- Phase 4: 已生成文档
    restored BOOLEAN DEFAULT 0,           -- Phase 5: 已还原
    compiled BOOLEAN DEFAULT 0,           -- Phase 5: 编译通过
    tags TEXT,                            -- 标签 (JSON 数组)
    module TEXT,                          -- 所属模块
    note TEXT,                            -- 备注
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 接口实现表
CREATE TABLE IF NOT EXISTS class_interfaces (
    class_sig TEXT NOT NULL,              -- 类签名
    interface_sig TEXT NOT NULL,          -- 接口签名
    PRIMARY KEY (class_sig, interface_sig),
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE
);

-- 3. 字段表
CREATE TABLE IF NOT EXISTS class_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_sig TEXT NOT NULL,              -- 所属类
    name TEXT NOT NULL,                   -- 字段名
    type TEXT NOT NULL,                   -- 字段类型
    access_flags INTEGER,                 -- 访问标志
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE,
    UNIQUE(class_sig, name)
);

-- 4. 方法表
CREATE TABLE IF NOT EXISTS class_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_sig TEXT NOT NULL,              -- 所属类
    name TEXT NOT NULL,                   -- 方法名
    return_type TEXT,                     -- 返回类型
    access_flags INTEGER,                 -- 访问标志
    signature TEXT,                       -- 完整方法签名 (用于唯一标识)
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE,
    UNIQUE(class_sig, signature)
);

-- 5. 方法参数表
CREATE TABLE IF NOT EXISTS method_params (
    method_id INTEGER NOT NULL,           -- 方法 ID
    param_index INTEGER NOT NULL,         -- 参数索引 (0, 1, 2, ...)
    param_type TEXT NOT NULL,             -- 参数类型
    PRIMARY KEY (method_id, param_index),
    FOREIGN KEY (method_id) REFERENCES class_methods(id) ON DELETE CASCADE
);

-- 6. 方法体依赖表（核心！）
CREATE TABLE IF NOT EXISTS method_body_deps (
    class_sig TEXT NOT NULL,              -- 类签名
    dep_class_sig TEXT NOT NULL,          -- 依赖的类签名
    PRIMARY KEY (class_sig, dep_class_sig),
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE
);

-- 7. 结构性依赖表（汇总）
CREATE TABLE IF NOT EXISTS structural_deps (
    class_sig TEXT NOT NULL,              -- 类签名
    dep_class_sig TEXT NOT NULL,          -- 依赖的类签名
    dep_type TEXT NOT NULL,               -- 依赖类型: supertype, interface, field, method_param, method_return
    PRIMARY KEY (class_sig, dep_class_sig, dep_type),
    FOREIGN KEY (class_sig) REFERENCES classes(signature) ON DELETE CASCADE
);

-- 8. 完整依赖图（方便查询）
CREATE TABLE IF NOT EXISTS dependencies (
    from_class TEXT NOT NULL,             -- 源类
    to_class TEXT NOT NULL,               -- 目标类
    dep_source TEXT NOT NULL,             -- 依赖来源: structural, method_body
    PRIMARY KEY (from_class, to_class, dep_source),
    FOREIGN KEY (from_class) REFERENCES classes(signature) ON DELETE CASCADE
);

-- ============================================================================
-- 索引（优化查询性能）
-- ============================================================================

-- 类名索引（用于搜索）
CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(name);

-- 父类索引（用于查找子类）
CREATE INDEX IF NOT EXISTS idx_classes_supertype ON classes(supertype);

-- 模块索引（用于模块分析）
CREATE INDEX IF NOT EXISTS idx_classes_module ON classes(module);

-- 依赖查询索引
CREATE INDEX IF NOT EXISTS idx_dependencies_from ON dependencies(from_class);
CREATE INDEX IF NOT EXISTS idx_dependencies_to ON dependencies(to_class);

-- 方法体依赖索引
CREATE INDEX IF NOT EXISTS idx_method_body_deps_class ON method_body_deps(class_sig);
CREATE INDEX IF NOT EXISTS idx_method_body_deps_dep ON method_body_deps(dep_class_sig);

-- 结构性依赖索引
CREATE INDEX IF NOT EXISTS idx_structural_deps_class ON structural_deps(class_sig);
CREATE INDEX IF NOT EXISTS idx_structural_deps_dep ON structural_deps(dep_class_sig);
CREATE INDEX IF NOT EXISTS idx_structural_deps_type ON structural_deps(dep_type);

-- ============================================================================
-- 视图（方便查询）
-- ============================================================================

-- 完整依赖视图（结构性 + 方法体）
CREATE VIEW IF NOT EXISTS v_all_dependencies AS
SELECT DISTINCT
    from_class,
    to_class,
    'combined' as dep_source
FROM dependencies;

-- 类统计视图
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

-- 依赖统计视图
CREATE VIEW IF NOT EXISTS v_dependency_stats AS
SELECT
    from_class,
    COUNT(*) as total_deps,
    SUM(CASE WHEN dep_source = 'structural' THEN 1 ELSE 0 END) as structural_deps,
    SUM(CASE WHEN dep_source = 'method_body' THEN 1 ELSE 0 END) as method_body_deps
FROM dependencies
GROUP BY from_class;
"""

# ============================================================================
# 导入函数
# ============================================================================

IMPORT_FUNCTION = """
import json
import sqlite3
from pathlib import Path

def import_enhanced_json(json_path: str, db_path: str):
    '''
    导入增强版 JSON 到 SQLite 数据库

    Args:
        json_path: JSON 文件路径
        db_path: SQLite 数据库路径
    '''

    print(f'[*] Loading JSON from: {json_path}')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    classes = data['classes']
    stats = data['stats']

    print(f'[*] Total classes: {stats["total"]}')
    print(f'[*] Skipped: {stats["skipped"]}')
    print(f'[*] Errors: {stats["errors"]}')
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 开启事务
    cursor.execute('BEGIN TRANSACTION')

    try:
        imported = 0

        for i, cls in enumerate(classes):
            # 1. 插入类信息
            cursor.execute('''
                INSERT OR REPLACE INTO classes (signature, name, supertype, access_flags)
                VALUES (?, ?, ?, ?)
            ''', (
                cls['signature'],
                cls['name'],
                cls.get('supertype'),
                cls.get('accessFlags')
            ))

            class_sig = cls['signature']

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

    except Exception as e:
        conn.rollback()
        print(f'[!] Import failed: {e}')
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) != 3:
        print('Usage: python import_enhanced_json.py <json_path> <db_path>')
        sys.exit(1)

    json_path = sys.argv[1]
    db_path = sys.argv[2]

    import_enhanced_json(json_path, db_path)
"""
