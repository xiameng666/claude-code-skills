#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版拓扑排序脚本 - 只输出统计信息

用法:
    python build_topology_simple.py --root "LFusionEngine;" --db "C:/Users/24151/Documents/gms-knowledge/gms-rename-v2.db"
"""

import sqlite3
import json
import argparse
from collections import defaultdict, deque

from typing import Dict, List, Set

import sys


# 系统类前缀
SYSTEM_PREFIXES = [
    'Ljava/', 'Ljavax/', 'Lkotlin/', 'Lkotlinx/',
    'Landroid/', 'Landroidx/', 'Ldalvik/',
]


def is_system_class(class_sig: str) -> bool:
    for prefix in SYSTEM_PREFIXES:
        if class_sig.startswith(prefix):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description='构建依赖子图并进行拓扑排序')
    parser.add_argument('--root', required=True, help='根节点类签名')
    parser.add_argument('--db', required=True, help='SQLite 数据库路径')
    parser.add_argument('--max-depth', type=int, default=-1, help='最大深度')
    args = parser.parse_args()


    print("=" * 60)
    print("依赖图拓扑分析工具")
    print("=" * 60)
    print(f"根节点: {args.root}")
    print(f"数据库: {args.db}")

    # 连接数据库
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # 统计总类数
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM classes")
    total_classes = cursor.fetchone()[0]
    print(f"数据库总类数: {total_classes}")

    # 统计依赖表数据
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM structural_deps")
    structural_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM method_body_deps")
    method_body_count = cursor.fetchone()[0]
    print(f"依赖表: structural_deps={structural_count}, method_body_deps={method_body_count}")

    # 检查根节点是否存在
    cursor.execute("SELECT signature FROM classes WHERE signature = ?", (args.root,))
    root_exists = cursor.fetchone()
    if not root_exists:
        print(f"[!] 根节点 {args.root} 不存在于数据库中")
        sys.exit(1)

    print(f"[+] 根节点存在: {args.root}")

    # BFS 构建子图
    print("\n[*] 开始 BFS 构建子图...")
    visited = set()
    queue = deque([(args.root, 0)])
    nodes = []
    edges = []
    node_depths = {}
    filtered_count = 0

    while queue:
        current, depth = queue.popleft()

        if current in visited:
            continue

        visited.add(current)
        nodes.append(current)
        node_depths[current] = depth

        if len(nodes) % 100 == 0:
            print(f"[+] 已发现 {len(nodes)} 个类, 深度: {depth}")

        # 查询依赖
        cursor = conn.cursor()

        # 从 structural_deps 和 method_body_deps 合并查询
        cursor.execute("""
            SELECT DISTINCT dep_class_sig
            FROM (
                SELECT class_sig, dep_class_sig FROM structural_deps
                WHERE class_sig = ?
                UNION
                SELECT class_sig, dep_class_sig FROM method_body_deps
                WHERE class_sig = ?
            )
        """, (current,))

        deps = [row['dep_class_sig'] for row in cursor.fetchall()]

        for dep in deps:
            if is_system_class(dep):
                filtered_count += 1
                continue

            edges.append({'from': current, 'to': dep})

            if dep not in visited:
                queue.append((dep, depth + 1))

    print(f"\n[+] BFS 完成:")
    print(f"    节点数: {len(nodes)}")
    print(f"    边数: {len(edges)}")
    print(f"    过滤系统类: {filtered_count}")

    # 构建邻接表
    print("\n[*] 构建邻接表...")
    graph = defaultdict(list)
    in_degree = {node: 0 for node in nodes}

    for edge in edges:
        graph[edge['from']].append(edge['to'])
        in_degree[edge['to']] += 1

    # 统计
    leaf_count = sum(1 for d in in_degree.values() if d == 0)
    non_leaf_count = sum(1 for d in in_degree.values() if d > 0)
    print(f"\n[+] 邻接表统计:")
    print(f"    有出边的节点: {len(graph)}")
    print(f"    叶子节点（入度=0）: {leaf_count}")
    print(f"    非叶子节点（入度>0）: {non_leaf_count}")

    # DFS 后序排序
    print("\n[*] 开始 DFS 后序排序...")
    visited = set()
    order = []

    # 转换为集合（快速查找）
    node_set = set(nodes)

    def dfs(node):
        if node in visited:
            return
        visited.add(node)
        # 先处理所有邻居（递归）
        for neighbor in graph.get(node, []):
            if neighbor in node_set and  neighbor not in visited:
                dfs(neighbor)
        order.append(node)

    # 对所有节点进行 DFS
    for node in nodes:
        if node not in visited:
            dfs(node)

    order.reverse()

    print(f"\n[+] DFS 完成:")
    print(f"    排序后节点数: {len(order)}")

    # 分层（每 100 个一组）
    layers = []
    for i in range(0, len(order), 100):
        batch = order[i:i + 100]
        layers.append({
            'index': i // 100,
            'classes': batch,
            'count': len(batch)
        })

    print(f"\n[+] 分层完成:")
    print(f"    共 {len(layers)} 层")
    print(f"    每层约 100 个类")

    # 输出统计
    print("\n" + "=" * 60)
    print("统计信息")
    print("=" * 60)
    print(f"总节点数: {len(nodes)}")
    print(f"总边数: {len(edges)}")
    print(f"叶子节点数: {leaf_count}")
    print(f"拓扑层数: {len(layers)}")
    print(f"前 5 层类数: {sum(l['count'] for l in layers[:5])}")
    print(f"后 5 层类数: {sum(l['count'] for l in layers[-5:])}")

    # 保存 JSON
    output_dir = "."
    subgraph_path = f"{output_dir}/subgraph_simple.json"
    with open(subgraph_path, 'w', encoding='utf-8') as f:
        json.dump({
            'root': args.root,
            'nodes': nodes,
            'edges': edges,
            'stats': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'leaf_count': leaf_count,
                'layer_count': len(layers)
            }
        }, f, indent=2, ensure_ascii=False)

    print(f"\n[+] 已保存: {subgraph_path}")

    # 保存拓扑层次
    topology_path = f"{output_dir}/topology_layers_simple.json"
    with open(topology_path, 'w', encoding='utf-8') as f:
        json.dump(layers, f, indent=2, ensure_ascii=False)

    print(f"[+] 已保存: {topology_path}")

    print("\n" + "=" * 60)
    print("完成！请查看生成的 JSON 文件")
    print("=" * 60)


    print(f"\n输出文件:")
    print(f"  - {subgraph_path}")
    print(f"  - {topology_path}")
    print(f"\n使用方式:")
    print(f"  python -c \"import json; layers = json.load(open('{topology_path}')); print(f'Layer count: {{len(layers)}}'); print(f'Layer 0: {{layers[0]['count']}} classes')\"")


if __name__ == '__main__':
