# -*- coding: utf-8 -*-
"""
GMS 图论分析自动化循环脚本

双 Agent 协作模式：
- Agent A: 分析者，提取类的所有依赖
- Agent B: 审查者，检查方法体依赖是否遗漏

使用方法：
  python gms-analyze-loop.py --seed Lfvxn; --knowledge-dir C:\Users\xxx\gms-knowledge
"""

import json
import os
import sys
import argparse
from collections import deque
from typing import Set, List, Dict, Any, Optional

# 系统类前缀（不入图）
EXCLUDE_PREFIXES = [
    'Landroid/',
    'Landroidx/',
    'Ljava/',
    'Ljavax/',
    'Lkotlin/',
    'Lkotlinx/',
    'Lcom/google/android/material/',
    'Ldalvik/',
    'Lsun/',
    'Lorg/apache/',
    'Lorg/json/',
    'Lorg/w3c/',
    'Lorg/xml/',
    'Lorg/reactivestreams/',
    'Lokhttp3/',
    'Lretrofit2/',
    'Lio/reactivex/',
    'Lcom/squareup/',
    'Lcom/bumptech/',
    'Lorg/intellij/',
    'Lorg/jetbrains/',
]


class AnalysisQueue:
    """分析队列管理器"""

    def __init__(self):
        self.pending: deque = deque()  # 待分析队列
        self.analyzed: Set[str] = set()  # 已分析集合
        self.in_queue: Set[str] = set()  # 已入队集合（用于去重）

    def add(self, class_sig: str) -> bool:
        """添加类到队列（去重）"""
        # 检查是否是系统类
        if self._should_skip(class_sig):
            return False

        # 检查是否已分析或已在队列
        if class_sig in self.analyzed or class_sig in self.in_queue:
            return False

        self.pending.append(class_sig)
        self.in_queue.add(class_sig)
        return True

    def add_many(self, class_sigs: List[str]) -> int:
        """批量添加类到队列"""
        added = 0
        for sig in class_sigs:
            if self.add(sig):
                added += 1
        return added

    def pop(self) -> Optional[str]:
        """取出下一个待分析的类"""
        if not self.pending:
            return None
        sig = self.pending.popleft()
        self.in_queue.discard(sig)
        return sig

    def mark_analyzed(self, class_sig: str):
        """标记为已分析"""
        self.analyzed.add(class_sig)
        self.in_queue.discard(class_sig)

    def _should_skip(self, sig: str) -> bool:
        """检查是否应该跳过（系统类）"""
        for prefix in EXCLUDE_PREFIXES:
            if sig.startswith(prefix):
                return True
        return False

    @property
    def stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            'pending': len(self.pending),
            'analyzed': len(self.analyzed),
            'in_queue': len(self.in_queue),
        }


class AgentA:
    """分析者 Agent - 提取类的所有依赖"""

    def __init__(self, mcp_client):
        self.mcp = mcp_client

    def analyze(self, class_sig: str) -> Dict[str, Any]:
        """
        分析类的所有依赖

        返回：
        {
            'class_sig': 'Lfvxn;',
            'superclass': 'Ljava/lang/Object;',
            'interfaces': ['Lcjdx;', ...],
            'field_types': ['Lcmua;', ...],
            'method_deps': ['Lgpus;', ...],  # 方法体中的依赖
            'all_deps': ['Lcjdx;', ...],     # 所有混淆类依赖（去重）
        }
        """
        result = {
            'class_sig': class_sig,
            'superclass': None,
            'interfaces': [],
            'field_types': [],
            'method_deps': [],
            'all_deps': [],
        }

        # 1. 获取父类
        superclass = self._get_superclass(class_sig)
        result['superclass'] = superclass

        # 2. 获取接口
        interfaces = self._get_interfaces(class_sig)
        result['interfaces'] = interfaces

        # 3. 获取字段类型
        field_types = self._get_field_types(class_sig)
        result['field_types'] = field_types

        # 4. 获取方法体依赖（最关键！）
        method_deps = self._get_method_deps(class_sig)
        result['method_deps'] = method_deps

        # 5. 合并所有依赖（去重）
        all_deps = set()
        if superclass and self._is_obfuscated(superclass):
            all_deps.add(superclass)
        all_deps.update([i for i in interfaces if self._is_obfuscated(i)])
        all_deps.update([f for f in field_types if self._is_obfuscated(f)])
        all_deps.update([m for m in method_deps if self._is_obfuscated(m)])
        result['all_deps'] = list(all_deps)

        return result

    def _get_superclass(self, class_sig: str) -> Optional[str]:
        """获取父类"""
        # 调用 MCP: get_class_superclass
        # 这里是伪代码，实际需要调用 MCP
        pass

    def _get_interfaces(self, class_sig: str) -> List[str]:
        """获取接口列表"""
        # 调用 MCP: get_class_interfaces
        pass

    def _get_field_types(self, class_sig: str) -> List[str]:
        """获取字段类型"""
        # 调用 MCP: get_class_fields
        pass

    def _get_method_deps(self, class_sig: str) -> List[str]:
        """
        从方法体中提取依赖（最关键！）

        需要分析：
        1. new 语句
        2. 静态方法调用
        3. 类型转换
        4. Lambda/匿名类
        5. instanceof 检查
        """
        # 调用 MCP: get_class_decompiled_code
        # 然后解析代码提取依赖
        pass

    def _is_obfuscated(self, sig: str) -> bool:
        """检查是否是混淆类"""
        if not sig:
            return False
        # 检查是否是系统类
        for prefix in EXCLUDE_PREFIXES:
            if sig.startswith(prefix):
                return False
        return True


class AgentB:
    """审查者 Agent - 检查分析结果是否完整"""

    def review(self, analysis_result: Dict[str, Any], decompiled_code: str) -> Dict[str, Any]:
        """
        审查分析结果

        审查重点：
        1. 方法体依赖是否遗漏（最重要！）
        2. new 语句是否全部提取
        3. 静态方法调用是否全部提取

        返回：
        {
            'passed': True/False,
            'missing_deps': ['Lxxx;', ...],  # 遗漏的依赖
            'review_notes': '...',
        }
        """
        result = {
            'passed': True,
            'missing_deps': [],
            'review_notes': '',
        }

        # 从反编译代码中提取所有类引用
        actual_deps = self._extract_all_deps_from_code(decompiled_code)

        # 与分析结果对比
        reported_deps = set(analysis_result.get('all_deps', []))

        # 找出遗漏的依赖
        missing = actual_deps - reported_deps
        if missing:
            result['passed'] = False
            result['missing_deps'] = list(missing)
            result['review_notes'] = f'发现遗漏的依赖: {missing}'
        else:
            result['review_notes'] = '审查通过，未发现遗漏'

        return result

    def _extract_all_deps_from_code(self, code: str) -> Set[str]:
        """从代码中提取所有类依赖"""
        import re

        deps = set()

        # 1. new Lxxx;() 模式
        for match in re.finditer(r'new\s+(L[^;]+;)', code):
            deps.add(match.group(1))

        # 2. 静态方法调用 Lxxx;.method()
        for match in re.finditer(r'(L[^;]+)\.\w+\(', code):
            deps.add(match.group(1) + ';')

        # 3. 类型转换 (Lxxx;)
        for match in re.finditer(r'\((L[^;]+;)\)', code):
            deps.add(match.group(1))

        # 4. instanceof 检查
        for match in re.finditer(r'instanceof\s+(L[^;]+;)', code):
            deps.add(match.group(1))

        # 过滤系统类
        deps = {d for d in deps if not self._should_skip(d)}

        return deps

    def _should_skip(self, sig: str) -> bool:
        for prefix in EXCLUDE_PREFIXES:
            if sig.startswith(prefix):
                return True
        return False


class GMSAnalyzer:
    """GMS 图论分析器 - 协调双 Agent 工作"""

    def __init__(self, knowledge_dir: str):
        self.knowledge_dir = knowledge_dir
        self.queue = AnalysisQueue()
        self.agent_a = AgentA(None)  # TODO: 传入 MCP client
        self.agent_b = AgentB()
        self.results = {}  # 分析结果缓存

    def run(self, seed_class: str, max_iterations: int = 100):
        """
        运行图论分析

        Args:
            seed_class: 种子类（分析起点）
            max_iterations: 最大迭代次数（防止无限循环）
        """
        print(f"[启动] GMS 图论分析")
        print(f"[种子] {seed_class}")
        print(f"[知识库] {self.knowledge_dir}")
        print("-" * 50)

        # 添加种子类到队列
        self.queue.add(seed_class)

        iteration = 0
        while self.queue.pending and iteration < max_iterations:
            iteration += 1

            # 取出下一个待分析的类
            class_sig = self.queue.pop()
            print(f"\n[进度] 迭代 {iteration} | 分析: {class_sig}")
            print(f"[统计] 待处理: {len(self.queue.pending)} | 已分析: {len(self.queue.analyzed)}")

            # Agent A: 分析
            print(f"[Agent A] 正在分析 {class_sig}...")
            analysis = self.agent_a.analyze(class_sig)

            # Agent B: 审查
            print(f"[Agent B] 正在审查分析结果...")
            decompiled = self._get_decompiled_code(class_sig)
            review = self.agent_b.review(analysis, decompiled)

            if not review['passed']:
                print(f"[审查] ✗ 不通过 - {review['review_notes']}")
                # 补充遗漏的依赖
                analysis['all_deps'].extend(review['missing_deps'])
                analysis['all_deps'] = list(set(analysis['all_deps']))
                print(f"[补充] 添加遗漏依赖: {review['missing_deps']}")
            else:
                print(f"[审查] ✓ 通过 - {review['review_notes']}")

            # 标记为已分析
            self.queue.mark_analyzed(class_sig)

            # 添加依赖到队列
            new_deps = analysis['all_deps']
            added = self.queue.add_many(new_deps)
            print(f"[依赖] 发现 {len(new_deps)} 个 | 新入队: {added}")

            # 持久化结果
            self._save_result(class_sig, analysis)

            # 保存进度
            self.results[class_sig] = analysis

        # 输出最终统计
        self._print_final_stats()

    def _get_decompiled_code(self, class_sig: str) -> str:
        """获取反编译代码"""
        # 调用 MCP: get_class_decompiled_code
        pass

    def _save_result(self, class_sig: str, analysis: Dict[str, Any]):
        """保存分析结果到知识库"""
        # 保存到 notes/ 目录
        notes_dir = os.path.join(self.knowledge_dir, 'notes')
        os.makedirs(notes_dir, exist_ok=True)

        # 生成文件名
        class_name = class_sig.replace('/', '_').replace(';', '').lstrip('L')
        md_file = os.path.join(notes_dir, f"{class_name}.md")

        # 生成 MD 内容
        md_content = self._generate_md(analysis)

        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"[保存] {md_file}")

    def _generate_md(self, analysis: Dict[str, Any]) -> str:
        """生成 MD 文件内容"""
        class_sig = analysis['class_sig']
        deps = analysis['all_deps']

        md = f"""# {class_sig}

## 基本信息

| 属性 | 值 |
|------|-----|
| 类签名 | {class_sig} |
| 父类 | {analysis.get('superclass', 'N/A')} |
| 接口数 | {len(analysis.get('interfaces', []))} |
| 依赖数 | {len(deps)} |

## 实现的接口

"""
        for iface in analysis.get('interfaces', []):
            md += f"- {iface}\n"

        md += "\n## 依赖的混淆类\n\n"
        for dep in sorted(deps):
            md += f"- {dep}\n"

        return md

    def _print_final_stats(self):
        """输出最终统计"""
        print("\n" + "=" * 50)
        print("[完成] GMS 图论分析完成")
        print(f"[统计] 已分析: {len(self.queue.analyzed)} 个类")
        print(f"[统计] 叶子节点: {len(self.queue.analyzed) - sum(1 for r in self.results.values() if r['all_deps'])}")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description='GMS 图论分析自动化脚本')
    parser.add_argument('--seed', required=True, help='种子类（分析起点）')
    parser.add_argument('--knowledge-dir', required=True, help='知识库目录')
    parser.add_argument('--max-iterations', type=int, default=100, help='最大迭代次数')

    args = parser.parse_args()

    analyzer = GMSAnalyzer(args.knowledge_dir)
    analyzer.run(args.seed, args.max_iterations)


if __name__ == '__main__':
    main()
