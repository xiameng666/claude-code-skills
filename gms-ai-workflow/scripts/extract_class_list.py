#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从数据库中提取依赖类列表

用法:
    python extract_class_list.py --db "path/to/gms-rename-v2.db" --root "LFusionEngine;" --output "class_list.txt"

输出:
    class_list.txt - 每行一个类签名
"""

import sqlite3
import argparse


# 需要过滤的类前缀（系统类）
SYSTEM_PREFIXES = [
    'Ljava/', 'Ljavax/', 'Lkotlin/', 'Lkotlinx/',
    'Landroid/', 'Landroidx/', 'Ldalvik/',
    'Lcom/google/android/gms/internal/',
]


def is_valid_class(class_sig: str) -> bool:
    """检查类签名格式是否有效"""
    if not class_sig:
        return False

    # 过滤系统类
    for prefix in SYSTEM_PREFIXES:
        if class_sig.startswith(prefix):
            return False

    # 类签名必须以 L 开头，以 ; 结尾
    if not class_sig.startswith('L') or not class_sig.endswith(';'):
        return False

    return True


def class_exists(class_sig: str, cursor) -> bool:
    """检查类是否存在于 classes 表中"""
    cursor.execute('SELECT 1 FROM classes WHERE signature = ?', (class_sig,))
    return cursor.fetchone() is not None


def get_all_dependencies(root_class: str, cursor):
    """
    递归获取所有依赖类

    只保留在 classes 表中实际存在的类

    Returns:
        set of class signatures
    """
    visited = set()
    queue = [root_class]
    not_found = set()

    while queue:
        current = queue.pop(0)

        if current in visited:
            continue

        # 跳过无效的类签名
        if not is_valid_class(current):
            continue

        # 检查类是否存在于 classes 表中
        if not class_exists(current, cursor):
            not_found.add(current)
            continue

        visited.add(current)

        # 查询依赖
        cursor.execute('''
            SELECT DISTINCT to_class
            FROM dependencies
            WHERE from_class = ?
        ''', (current,))

        for row in cursor.fetchall():
            dep = row[0]
            if dep not in visited:
                queue.append(dep)

    return visited, not_found


def main():
    parser = argparse.ArgumentParser(description='从数据库中提取依赖类列表')
    parser.add_argument('--db', required=True, help='SQLite 数据库路径')
    parser.add_argument('--output', required=True, help='输出文件路径')
    parser.add_argument('--root', required=True, help='根节点类签名 (如 LFusionEngine;)')

    args = parser.parse_args()

    print("=" * 60)
    print("从数据库提取依赖类列表")
    print("=" * 60)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 检查根节点是否存在
    cursor.execute('SELECT signature, name FROM classes WHERE signature = ?', (args.root,))
    root_info = cursor.fetchone()
    if not root_info:
        print(f"\n[!] 错误: 根节点 {args.root} 不在数据库中")
        conn.close()
        return

    print(f"\n[*] 根节点: {args.root} ({root_info['name']})")

    # 递归获取所有依赖
    all_classes, not_found_classes = get_all_dependencies(args.root, cursor)

    print(f"[*] 依赖类数量: {len(all_classes)}")
    if not_found_classes:
        print(f"[!] 警告: {len(not_found_classes)} 个依赖类在 classes 表中不存在，已过滤")
        if len(not_found_classes) <= 20:
            print(f"    过滤的类: {', '.join(sorted(not_found_classes))}")

    # 写入文件（先写根节点，再写依赖类）
    with open(args.output, 'w', encoding='utf-8') as f:
        # 先写根节点
        f.write(args.root + '\n')
        # 再写所有依赖类（不包括根节点）
        for cls in sorted(all_classes):
            if cls != args.root:
                f.write(cls + '\n')

    print(f"\n[+] 类列表已保存: {args.output}")
    print(f"    - 总数: {len(all_classes) + 1} (含根节点)")

    # 显示一些统计信息
    print(f"\n[*] 过滤规则:")
    print(f"    - 系统类前缀: {', '.join(SYSTEM_PREFIXES)}")
    print(f"    - 只保留在 classes 表中存在的类")

    conn.close()
    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
