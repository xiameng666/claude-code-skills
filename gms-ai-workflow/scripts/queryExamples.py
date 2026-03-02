#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库查询示例脚本

演示如何查询类和方法的依赖关系
"""

import sqlite3
import sys

DB_PATH = r'C:\Users\24151\Documents\gms-knowledge\gms-rename-v2.db'


def query_class_all_deps(class_sig: str):
    """查询类的所有依赖"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"\n{'='*60}")
    print(f"类: {class_sig}")
    print(f"{'='*60}\n")

    # 1. 基本信息
    cursor.execute('''
        SELECT name, supertype, access_flags
        FROM classes
        WHERE signature = ?
    ''', (class_sig,))

    row = cursor.fetchone()
    if not row:
        print(f"[!] 类 {class_sig} 不存在")
        conn.close()
        return

    name, supertype, access_flags = row
    print(f"类名: {name}")
    print(f"父类: {supertype}")
    print(f"访问标志: {access_flags}")
    print()

    # 2. 实现的接口
    cursor.execute('''
        SELECT interface_sig
        FROM class_interfaces
        WHERE class_sig = ?
    ''', (class_sig,))

    interfaces = cursor.fetchall()
    print(f"实现的接口 ({len(interfaces)}):")
    for (iface,) in interfaces[:10]:
        print(f"  - {iface}")
    if len(interfaces) > 10:
        print(f"  ... 还有 {len(interfaces) - 10} 个")
    print()

    # 3. 方法列表
    cursor.execute('''
        SELECT name, return_type, signature
        FROM class_methods
        WHERE class_sig = ?
    ''', (class_sig,))

    methods = cursor.fetchall()
    print(f"方法数量: {len(methods)}")
    print("方法列表 (前10个):")
    for name, return_type, sig in methods[:10]:
        print(f"  - {name} -> {return_type}")
    if len(methods) > 10:
        print(f"  ... 还有 {len(methods) - 10} 个方法")
    print()

    # 4. 方法体依赖（运行时依赖）
    cursor.execute('''
        SELECT dep_class_sig
        FROM method_body_deps
        WHERE class_sig = ?
    ''', (class_sig,))

    method_deps = cursor.fetchall()
    print(f"方法体依赖 ({len(method_deps)}) - 运行时调用的类:")
    for (dep,) in method_deps[:15]:
        print(f"  -> {dep}")
    if len(method_deps) > 15:
        print(f"  ... 还有 {len(method_deps) - 15} 个")
    print()

    # 5. 结构性依赖（编译时依赖）
    cursor.execute('''
        SELECT dep_class_sig, dep_type
        FROM structural_deps
        WHERE class_sig = ?
    ''', (class_sig,))

    struct_deps = cursor.fetchall()
    print(f"结构性依赖 ({len(struct_deps)}) - 编译时依赖:")

    # 按类型分组
    by_type = {}
    for dep, dep_type in struct_deps:
        if dep_type not in by_type:
            by_type[dep_type] = []
        by_type[dep_type].append(dep)

    for dep_type, deps in by_type.items():
        print(f"  [{dep_type}] ({len(deps)}):")
        for dep in deps[:5]:
            print(f"    - {dep}")
        if len(deps) > 5:
            print(f"    ... 还有 {len(deps) - 5} 个")
    print()

    # 6. 所有依赖（合并）
    cursor.execute('''
        SELECT to_class, dep_source
        FROM dependencies
        WHERE from_class = ?
    ''', (class_sig,))

    all_deps = cursor.fetchall()
    print(f"总依赖数: {len(all_deps)}")
    print()

    conn.close()


def query_method_deps(class_sig: str, method_name: str):
    """查询特定方法的依赖"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"\n{'='*60}")
    print(f"方法: {class_sig} -> {method_name}")
    print(f"{'='*60}\n")

    # 1. 查找方法
    cursor.execute('''
        SELECT id, name, return_type, signature
        FROM class_methods
        WHERE class_sig = ? AND name = ?
    ''', (class_sig, method_name))

    methods = cursor.fetchall()
    if not methods:
        print(f"[!] 方法 {method_name} 不存在")
        conn.close()
        return

    print(f"找到 {len(methods)} 个重载方法:\n")

    for method_id, name, return_type, signature in methods:
        print(f"方法签名: {signature}")
        print(f"返回类型: {return_type}")

        # 2. 查询参数
        cursor.execute('''
            SELECT param_index, param_type
            FROM method_params
            WHERE method_id = ?
            ORDER BY param_index
        ''', (method_id,))

        params = cursor.fetchall()
        if params:
            print(f"参数:")
            for idx, param_type in params:
                print(f"  [{idx}] {param_type}")
        else:
            print("参数: 无")
        print()

    # 注意: method_body_deps 是按类聚合的，不是按方法
    # 如果要知道某个方法调用了哪些类，需要反编译代码分析
    print("注意: 方法体依赖是按类聚合的，不是按单个方法")
    print(f"该类的所有方法体依赖:")

    cursor.execute('''
        SELECT dep_class_sig
        FROM method_body_deps
        WHERE class_sig = ?
    ''', (class_sig,))

    deps = cursor.fetchall()
    for (dep,) in deps[:10]:
        print(f"  -> {dep}")
    if len(deps) > 10:
        print(f"  ... 还有 {len(deps) - 10} 个")

    conn.close()


def query_reverse_deps(class_sig: str):
    """查询哪些类依赖了这个类（反向依赖）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"\n{'='*60}")
    print(f"反向依赖: 哪些类依赖了 {class_sig}")
    print(f"{'='*60}\n")

    # 从 dependencies 表查询
    cursor.execute('''
        SELECT from_class, dep_source
        FROM dependencies
        WHERE to_class = ?
    ''', (class_sig,))

    reverse_deps = cursor.fetchall()
    print(f"被 {len(reverse_deps)} 个类依赖:\n")

    # 按来源分组
    by_source = {}
    for from_class, dep_source in reverse_deps:
        if dep_source not in by_source:
            by_source[dep_source] = []
        by_source[dep_source].append(from_class)

    for source, classes in by_source.items():
        print(f"[{source}] ({len(classes)}):")
        for cls in classes[:10]:
            print(f"  <- {cls}")
        if len(classes) > 10:
            print(f"  ... 还有 {len(classes) - 10} 个")
        print()

    conn.close()


def query_dependency_chain(start_class: str, max_depth: int = 3):
    """查询依赖链（BFS遍历）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"\n{'='*60}")
    print(f"依赖链: 从 {start_class} 开始 (深度={max_depth})")
    print(f"{'='*60}\n")

    visited = set()
    queue = [(start_class, 0)]

    while queue:
        current, depth = queue.pop(0)

        if current in visited or depth > max_depth:
            continue

        visited.add(current)
        indent = "  " * depth
        print(f"{indent}[{depth}] {current}")

        # 查询直接依赖
        cursor.execute('''
            SELECT DISTINCT to_class
            FROM dependencies
            WHERE from_class = ?
        ''', (current,))

        deps = cursor.fetchall()
        for (dep,) in deps:
            if dep not in visited:
                queue.append((dep, depth + 1))

    print(f"\n总共遍历了 {len(visited)} 个类")
    conn.close()


def search_class_by_name(pattern: str):
    """按名称搜索类"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"\n{'='*60}")
    print(f"搜索类: {pattern}")
    print(f"{'='*60}\n")

    cursor.execute('''
        SELECT signature, name, supertype
        FROM classes
        WHERE name LIKE ? OR signature LIKE ?
        LIMIT 20
    ''', (f'%{pattern}%', f'%{pattern}%'))

    results = cursor.fetchall()
    print(f"找到 {len(results)} 个结果:\n")

    for sig, name, supertype in results:
        print(f"{sig}")
        print(f"  名称: {name}")
        print(f"  父类: {supertype}")
        print()

    conn.close()


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python queryExamples.py class <类签名>")
        print("  python queryExamples.py method <类签名> <方法名>")
        print("  python queryExamples.py reverse <类签名>")
        print("  python queryExamples.py chain <类签名> [深度]")
        print("  python queryExamples.py search <搜索词>")
        print()
        print("示例:")
        print("  python queryExamples.py class LFusionEngine;")
        print("  python queryExamples.py method LFusionEngine; onCreate")
        print("  python queryExamples.py reverse LFusionEngine;")
        print("  python queryExamples.py chain LFusionEngine; 2")
        print("  python queryExamples.py search Fusion")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'class':
        if len(sys.argv) < 3:
            print("[!] 请提供类签名")
            sys.exit(1)
        query_class_all_deps(sys.argv[2])

    elif cmd == 'method':
        if len(sys.argv) < 4:
            print("[!] 请提供类签名和方法名")
            sys.exit(1)
        query_method_deps(sys.argv[2], sys.argv[3])

    elif cmd == 'reverse':
        if len(sys.argv) < 3:
            print("[!] 请提供类签名")
            sys.exit(1)
        query_reverse_deps(sys.argv[2])

    elif cmd == 'chain':
        if len(sys.argv) < 3:
            print("[!] 请提供类签名")
            sys.exit(1)
        depth = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        query_dependency_chain(sys.argv[2], depth)

    elif cmd == 'search':
        if len(sys.argv) < 3:
            print("[!] 请提供搜索词")
            sys.exit(1)
        search_class_by_name(sys.argv[2])

    else:
        print(f"[!] 未知命令: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    main()
