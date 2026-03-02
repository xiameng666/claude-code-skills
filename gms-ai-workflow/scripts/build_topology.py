#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建依赖子图并进行拓扑排序

用法:
    python build_topology.py --root "Lfvxn;" --db "C:/Users/24151/Documents/gms-knowledge/gms-rename.db"

    python build_topology.py \
        --root "Lfvxn;" \
        --db "C:/Users/24151/Documents/gms-knowledge/gms-rename.db" \
        --output-dir "./output"

输出:
    - subgraph.json: 依赖子图
    - topology_layers.json: 拓扑排序结果
    - topology_report.md: 可视化报告
"""

import sqlite3
import json
import argparse
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple


# 系统类前缀（需要过滤）
SYSTEM_PREFIXES = [
    'Ljava/', 'Ljavax/', 'Lkotlin/', 'Lkotlinx/',
    'Landroid/', 'Landroidx/', 'Ldalvik/',
    'Lcom/google/android/gms/internal/',  # GMS 内部类也可以考虑过滤
]


def is_system_class(class_sig: str) -> bool:
    """判断是否为系统类"""
    for prefix in SYSTEM_PREFIXES:
        if class_sig.startswith(prefix):
            return True
    return False


class DependencyGraph:
    """依赖图构建器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_class_dependencies(self, class_sig: str) -> List[str]:
        """查询某个类的所有依赖（合并 structural + method_body）"""
        cursor = self.conn.cursor()
        deps = set()

        # 从 structural_deps 表查询
        cursor.execute("""
            SELECT DISTINCT dep_class_sig
            FROM structural_deps
            WHERE class_sig = ?
        """, (class_sig,))
        deps.update(row['dep_class_sig'] for row in cursor.fetchall())

        # 从 method_body_deps 表查询
        cursor.execute("""
            SELECT DISTINCT dep_class_sig
            FROM method_body_deps
            WHERE class_sig = ?
        """, (class_sig,))
        deps.update(row['dep_class_sig'] for row in cursor.fetchall())

        return list(deps)

    def build_subgraph(self, root_class: str, max_depth: int = -1) -> Dict:
        """
        从根节点 BFS 构建依赖子图

        Args:
            root_class: 根节点类签名
            max_depth: 最大深度（-1 表示不限制）

        Returns:
            {
                'root': 'Lfvxn;',
                'nodes': ['Lfvxn;', 'Lfvxo;', ...],
                'edges': [
                    {'from': 'Lfvxn;', 'to': 'Lfvxo;'},
                    ...
                ],
                'node_depths': {'Lfvxn;': 0, 'Lfvxo;': 1, ...},
                'stats': {
                    'total_nodes': 156,
                    'total_edges': 423,
                    'max_depth': 8,
                    'filtered_system_classes': 89
                }
            }
        """
        visited = set()
        queue = deque([(root_class, 0)])  # (class, depth)
        nodes = []
        edges = []
        node_depths = {}
        filtered_count = 0

        print(f"[*] 开始构建子图，根节点: {root_class}")

        while queue:
            current, depth = queue.popleft()

            # 跳过已访问的节点
            if current in visited:
                continue

            # 深度限制
            if max_depth > 0 and depth > max_depth:
                continue

            visited.add(current)
            nodes.append(current)
            node_depths[current] = depth

            # 进度输出
            if len(nodes) % 10 == 0:
                print(f"[+] 已发现 {len(nodes)} 个类，当前深度: {depth}")

            # 查询依赖
            deps = self.get_class_dependencies(current)

            for dep in deps:
                # 过滤系统类
                if is_system_class(dep):
                    filtered_count += 1
                    continue

                # 添加边
                edges.append({
                    'from': current,
                    'to': dep
                })

                # 新节点入队
                if dep not in visited:
                    queue.append((dep, depth + 1))

        max_depth_actual = max(node_depths.values()) if node_depths else 0

        print(f"[+] 子图构建完成:")
        print(f"    - 节点数: {len(nodes)}")
        print(f"    - 边数: {len(edges)}")
        print(f"    - 最大深度: {max_depth_actual}")
        print(f"    - 过滤系统类: {filtered_count}")

        return {
            'root': root_class,
            'nodes': nodes,
            'edges': edges,
            'node_depths': node_depths,
            'stats': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'max_depth': max_depth_actual,
                'filtered_system_classes': filtered_count
            }
        }

    def close(self):
        """关闭数据库连接"""
        self.conn.close()


class TopologySort:
    """拓扑排序器（Kahn 算法）"""

    def __init__(self, subgraph: Dict):
        self.subgraph = subgraph
        self.nodes = subgraph['nodes']
        self.edges = subgraph['edges']

    def compute_layers(self, batch_size: int = 100) -> List[Dict]:
        """
        计算拓扑层次（使用 DFS 后序排序，支持循环依赖）

        Args:
            batch_size: 每层包含的类数量（用于分组）

        Returns:
            [
                {
                    'index': 0,
                    'classes': ['Lfvxo;', 'Lfvxp;'],  # 优先还原
                    'count': 2,
                    'description': 'Layer 0'
                },
                ...
            ]
        """
        print(f"\n[*] 开始拓扑排序（DFS 后序算法）...")

        # 构建邻接表
        graph = defaultdict(list)
        for edge in self.edges:
            graph[edge['from']].append(edge['to'])

        # 转换节点列表为集合（快速查找）
        node_set = set(self.nodes)

        # DFS 后序排序
        visited = set()
        temp_visited = set()  # 用于检测循环
        order = []
        cycles = []

        def dfs(node, path):
            if node in temp_visited:
                # 检测到循环
                try:
                    cycle_start = path.index(node)
                    cycles.append(path[cycle_start:] + [node])
                except ValueError:
                    pass
                return
            if node in visited:
                return

            temp_visited.add(node)
            path.append(node)

            # 使用 graph.get() 避免 KeyError
            for neighbor in graph.get(node, []):
                if neighbor in node_set:  # 使用集合，快速查找
                    dfs(neighbor, path)

            path.pop()
            temp_visited.remove(node)
            visited.add(node)
            order.append(node)

        # 对所有节点进行 DFS
        for node in self.nodes:
            if node not in visited:
                dfs(node, [])

        # 反转得到拓扑顺序（依赖少的在前）
        order.reverse()

        print(f"[+] DFS 排序完成，共 {len(order)} 个类")
        if cycles:
            print(f"[!] 检测到 {len(cycles)} 个循环依赖（已自动处理）")

        # 按批次分组（每 batch_size 个类为一层）
        layers = []
        for i in range(0, len(order), batch_size):
            batch = order[i:i + batch_size]
            layer_idx = i // batch_size
            layers.append({
                'index': layer_idx,
                'classes': batch,
                'count': len(batch),
                'description': f'Layer {layer_idx}'
            })

        # 更新描述
        for i, layer in enumerate(layers):
            if i == 0:
                layer['description'] = f'Layer {i} (优先还原)'
            elif i == len(layers) - 1:
                layer['description'] = f'Layer {layer["index"]} (最后还原)'
            else:
                layer['description'] = f'Layer {layer["index"]}'

        print(f"[+] 拓扑排序完成，共 {len(layers)} 层（每层约 {batch_size} 个类）")

        return layers


def generate_report(subgraph: Dict, layers: List[Dict], output_path: str):
    """生成可视化报告"""

    md = f"""# 依赖图拓扑分析报告

## 概览

- **根节点**: `{subgraph['root']}`
- **总节点数**: {subgraph['stats']['total_nodes']}
- **总边数**: {subgraph['stats']['total_edges']}
- **最大深度**: {subgraph['stats']['max_depth']}
- **拓扑层数**: {len(layers)}

---

## 还原策略

使用 **DFS 后序排序** 算法，按依赖关系从少到多排序：
- **Layer 0** 的类依赖最少，优先还原
- **Layer N** 的类依赖最多，最后还原
- 存在循环依赖时，自动处理

---

## 拓扑层次概览

"""

    # 只显示前 5 层和后 5 层的详细信息
    show_detail_layers = 5

    # 前 5 层
    md += "### 前几层（优先还原）\n\n"
    for layer in layers[:show_detail_layers]:
        md += f"#### {layer['description']}\n\n"
        md += f"**类数量**: {layer['count']}\n\n"

        if layer['count'] <= 10:
            md += "**类列表**:\n"
            for cls in layer['classes']:
                md += f"- `{cls}`\n"
        else:
            md += "**类列表** (前 10 个):\n"
            for cls in layer['classes'][:10]:
                md += f"- `{cls}`\n"
            md += f"\n... 还有 {layer['count'] - 10} 个类\n"
        md += "\n"

    # 中间省略
    if len(layers) > show_detail_layers * 2:
        md += f"\n... 省略中间 {len(layers) - show_detail_layers * 2} 层 ...\n\n"

    # 后 5 层
    if len(layers) > show_detail_layers:
        md += "### 后几层（最后还原）\n\n"
        for layer in layers[-show_detail_layers:]:
            md += f"#### {layer['description']}\n\n"
            md += f"**类数量**: {layer['count']}\n\n"
            if layer['count'] <= 10:
                md += "**类列表**:\n"
                for cls in layer['classes']:
                    md += f"- `{cls}`\n"
            else:
                md += "**类列表** (前 10 个):\n"
                for cls in layer['classes'][:10]:
                    md += f"- `{cls}`\n"
                md += f"\n... 还有 {layer['count'] - 10} 个类\n"
            md += "\n"

    # 统计信息
    md += "\n---\n\n## 统计信息\n\n"
    md += "| 层次范围 | 层数 | 类总数 |\n"
    md += "|---------|------|--------|\n"

    # 分组统计（每 10 层一组）
    group_size = 10
    for i in range(0, len(layers), group_size):
        group = layers[i:i + group_size]
        total_classes = sum(l['count'] for l in group)
        start_layer = group[0]['index']
        end_layer = group[-1]['index']
        md += f"| Layer {start_layer}-{end_layer} | {len(group)} | {total_classes} |\n"

    # Mermaid 图（如果节点数不太多）
    if subgraph['stats']['total_nodes'] <= 50:
        md += "\n---\n\n## 依赖关系图\n\n"
        md += "```mermaid\ngraph TD\n"

        for edge in subgraph['edges'][:100]:  # 最多显示 100 条边
            from_short = edge['from'].split('/')[-1].rstrip(';')
            to_short = edge['to'].split('/')[-1].rstrip(';')
            md += f"    {from_short} --> {to_short}\n"

        md += "```\n"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)

    print(f"[+] 报告已生成: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='构建依赖子图并进行拓扑排序')
    parser.add_argument('--root', required=True, help='根节点类签名 (如 Lfvxn;)')
    parser.add_argument('--db', required=True, help='SQLite 数据库路径')
    parser.add_argument('--max-depth', type=int, default=-1, help='最大深度 (-1 表示不限制)')
    parser.add_argument('--output-dir', default='.', help='输出目录')

    args = parser.parse_args()

    print("=" * 60)
    print("依赖图拓扑分析工具")
    print("=" * 60)

    # 步骤 1: 构建子图
    graph_builder = DependencyGraph(args.db)
    subgraph = graph_builder.build_subgraph(args.root, args.max_depth)
    graph_builder.close()

    # 保存子图
    subgraph_path = f"{args.output_dir}/subgraph.json"
    with open(subgraph_path, 'w', encoding='utf-8') as f:
        json.dump(subgraph, f, indent=2, ensure_ascii=False)
    print(f"[+] 子图已保存: {subgraph_path}")

    # 步骤 2: 拓扑排序
    sorter = TopologySort(subgraph)
    layers = sorter.compute_layers()

    # 保存拓扑层次
    topology_path = f"{args.output_dir}/topology_layers.json"
    with open(topology_path, 'w', encoding='utf-8') as f:
        json.dump(layers, f, indent=2, ensure_ascii=False)
    print(f"[+] 拓扑层次已保存: {topology_path}")

    # 步骤 3: 生成报告
    report_path = f"{args.output_dir}/topology_report.md"
    generate_report(subgraph, layers, report_path)

    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)
    print(f"\n输出文件:")
    print(f"  - {subgraph_path}")
    print(f"  - {topology_path}")
    print(f"  - {report_path}")


if __name__ == '__main__':
    main()
