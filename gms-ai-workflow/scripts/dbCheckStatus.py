#!/usr/bin/env python3
import sqlite3

db_path = r'C:\Users\24151\Documents\gms-knowledge\gms-rename-v2.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('=== Database Statistics ===')
print()

# 类统计
cursor.execute('SELECT COUNT(*) FROM classes')
print(f'Classes: {cursor.fetchone()[0]}')

# 方法统计
cursor.execute('SELECT COUNT(*) FROM class_methods')
print(f'Methods: {cursor.fetchone()[0]}')

# 字段统计
cursor.execute('SELECT COUNT(*) FROM class_fields')
print(f'Fields: {cursor.fetchone()[0]}')

# 接口统计
cursor.execute('SELECT COUNT(*) FROM class_interfaces')
print(f'Interfaces: {cursor.fetchone()[0]}')

# 方法体依赖
cursor.execute('SELECT COUNT(*) FROM method_body_deps')
print(f'Method body dependencies: {cursor.fetchone()[0]}')

# 结构性依赖
cursor.execute('SELECT COUNT(*) FROM structural_deps')
print(f'Structural dependencies: {cursor.fetchone()[0]}')

# 总依赖
cursor.execute('SELECT COUNT(*) FROM dependencies')
print(f'Total dependencies: {cursor.fetchone()[0]}')

print()
print('=== Sample Data ===')
print()

# 示例类
print('Sample classes:')
cursor.execute('SELECT signature, name, supertype FROM classes LIMIT 5')
for row in cursor.fetchall():
    print(f'  {row[0]} ({row[1]}) extends {row[2]}')

print()

# 检查 FusionEngine
print('FusionEngine dependencies:')
cursor.execute('''
    SELECT dep_class_sig
    FROM method_body_deps
    WHERE class_sig = 'LFusionEngine;'
    LIMIT 10
''')
for row in cursor.fetchall():
    print(f'  -> {row[0]}')

conn.close()
