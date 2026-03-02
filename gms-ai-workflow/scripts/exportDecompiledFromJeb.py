# -*- coding: utf-8 -*-
#?description=Export decompiled Java code from class list
#?shortcut=

"""
从 JEB 导出反编译代码

用法:
    1. 先运行 extract_class_list.py 生成 class_list.txt
    2. 在 JEB 中打开 APK
    3. File -> Scripts -> Run Script...
    4. 选择本脚本
    5. 输入 class_list.txt 路径
    6. 输入输出目录
"""

import os
import time
from java.lang import Thread, Runnable
from java.util.concurrent import Executors, TimeUnit
from com.pnfsoftware.jeb.client.api import IScript, IGraphicalClientContext
from com.pnfsoftware.jeb.core.units.code.android import IDexUnit
from com.pnfsoftware.jeb.core.units.code.java import IJavaSourceUnit
from com.pnfsoftware.jeb.core.output.text import ITextDocument


def get_source_text(java_unit):
    """
    从 IJavaSourceUnit 获取反编译的源代码文本

    Returns:
        源代码字符串，失败返回 None
    """
    try:
        formatter = java_unit.getFormatter()
        if not formatter:
            return None

        presentations = formatter.getPresentations()
        if not presentations:
            return None

        # 获取第一个 presentation 的文档
        for pres in presentations:
            doc = pres.getDocument()
            if isinstance(doc, ITextDocument):
                # 获取整个文档内容
                doc_part = doc.getDocumentPart(0, 10000000)
                lines = []
                for line in doc_part.getLines():
                    lines.append(line.getText().toString())
                return '\n'.join(lines)

        return None
    except Exception as e:
        return None


class ExportDecompiledFromJeb(IScript):
    """JEB 脚本类"""

    def run(self, ctx):
        """脚本入口"""
        prj = ctx.getMainProject()
        if not prj:
            print('[!] 请先在 JEB 中打开 APK 项目')
            return

        # 询问类列表文件
        default_list = os.path.join(os.path.expanduser('~'), 'class_list.txt')
        class_list_path = ctx.displayQuestionBox(
            '导出反编译代码',
            '类列表文件路径 (每行一个类签名):',
            default_list
        )
        if not class_list_path:
            print('[*] 已取消')
            return

        # 询问输出目录
        default_output = os.path.join(os.path.expanduser('~'), 'decompiled')
        output_dir = ctx.displayQuestionBox(
            '导出反编译代码',
            '输出目录:',
            default_output
        )
        if not output_dir:
            print('[*] 已取消')
            return

        # 读取类列表
        try:
            with open(class_list_path, 'r') as f:
                class_sigs = set([line.strip() for line in f if line.strip()])

            print('\n[*] 读取类列表: %s' % class_list_path)
            print('[*] 待导出类数量: %d' % len(class_sigs))

        except Exception as e:
            print('[!] 读取类列表失败: %s' % str(e))
            return

        # 构建 IJavaSourceUnit 映射
        print('[*] 正在查找 IJavaSourceUnit...')
        java_unit_map = {}

        for java_unit in prj.findUnits(IJavaSourceUnit):
            # 获取类签名
            class_sig = java_unit.getName()
            if class_sig in class_sigs:
                java_unit_map[class_sig] = java_unit

        found_count = len(java_unit_map)
        missing_count = len(class_sigs) - found_count

        print('[*] 找到 %d 个 IJavaSourceUnit' % found_count)
        if missing_count > 0:
            print('[!] 未找到 %d 个类' % missing_count)

        # 导出
        print('\n[*] 开始导出到: %s\n' % output_dir)

        start_time = time.time()
        success_count = 0
        failed_count = 0

        for class_sig, java_unit in java_unit_map.items():
            # 转换类签名为文件路径
            # Lfoo/bar/Baz; -> foo/bar/Baz.java
            path = class_sig[1:-1].replace('/', os.sep) + '.java'
            file_path = os.path.join(output_dir, path)

            # 创建目录
            dir_path = os.path.dirname(file_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

            # 获取源代码
            source_text = get_source_text(java_unit)
            if source_text:
                try:
                    with open(file_path, 'w') as f:
                        f.write(source_text)
                    success_count += 1

                    # 进度
                    if success_count % 100 == 0:
                        print('    进度: %d/%d' % (success_count, found_count))
                except Exception as e:
                    print('[!] %s: 写入失败 - %s' % (class_sig, str(e)))
                    failed_count += 1
            else:
                print('[!] %s: 无法获取源代码' % class_sig)
                failed_count += 1

        elapsed = time.time() - start_time

        print('\n[+] 导出完成!')
        print('    - 成功: %d' % success_count)
        print('    - 失败: %d' % failed_count)
        print('    - 未找到: %d' % missing_count)
        print('    - 耗时: %.2f 秒' % elapsed)
        if elapsed > 0:
            print('    - 速度: %.1f 类/秒' % (success_count / elapsed))
        print('    - 输出目录: %s' % output_dir)


def run(ctx):
    """JEB 脚本入口函数"""
    ExportDecompiledFromJeb().run(ctx)
