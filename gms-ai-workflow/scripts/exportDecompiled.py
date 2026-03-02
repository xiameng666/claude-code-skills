# -*- coding: utf-8 -*-
#?description=Export decompiled code for class list
#?shortcut=

"""
Export Decompiled Code

Usage:
  1. Run extract_class_list.py to generate class_list.txt
  2. Open APK in JEB
  3. File -> Scripts -> Run Script...
  4. Select this script
  5. Enter class_list.txt path
  6. Enter output directory
"""

import os
import time
from com.pnfsoftware.jeb.client.api import IScript, IGraphicalClientContext
from com.pnfsoftware.jeb.core.units.code.android import IDexUnit


class ExportDecompiled(IScript):

    def run(self, ctx):
        prj = ctx.getMainProject()
        if not prj:
            print('[!] Please open an APK first')
            return

        # Ask for class list file
        default_list = os.path.join(os.path.expanduser('~'), 'class_list.txt')
        class_list_path = ctx.displayQuestionBox(
            'Export Decompiled Code',
            'Class list file path:',
            default_list
        )
        if not class_list_path:
            print('[*] Cancelled')
            return

        # Ask for output directory
        default_output = os.path.join(os.path.expanduser('~'), 'decompiled')
        output_dir = ctx.displayQuestionBox(
            'Export Decompiled Code',
            'Output directory:',
            default_output
        )
        if not output_dir:
            print('[*] Cancelled')
            return

        # Read class list
        try:
            with open(class_list_path, 'r') as f:
                class_sigs = [line.strip() for line in f if line.strip()]
            print('\n[*] Read class list: %s' % class_list_path)
            print('[*] Classes to export: %d' % len(class_sigs))
        except Exception as e:
            print('[!] Failed to read class list: %s' % str(e))
            return

        # Build class map
        class_map = {}
        for dex in prj.findUnits(IDexUnit):
            for cls in dex.getClasses():
                sig = cls.getSignature(True)
                if sig in class_sigs:
                    class_map[sig] = cls

        found = len(class_map)
        missing = len(class_sigs) - found
        print('[*] Found %d classes in JEB' % found)
        if missing > 0:
            print('[!] Missing %d classes' % missing)

        # Export
        print('\n[*] Exporting to: %s\n' % output_dir)
        start = time.time()
        success = 0
        failed = 0

        for sig, cls in class_map.items():
            if self._export_class(cls, output_dir):
                success += 1
                if success % 10 == 0:
                    print('    Progress: %d/%d' % (success, found))
            else:
                failed += 1

        elapsed = time.time() - start
        print('\n[+] Export complete!')
        print('    - Success: %d' % success)
        print('    - Failed: %d' % failed)
        print('    - Missing: %d' % missing)
        print('    - Time: %.2f sec' % elapsed)
        if elapsed > 0:
            print('    - Speed: %.1f classes/sec' % (success / elapsed))
        print('    - Output: %s' % output_dir)

    def _export_class(self, cls, output_dir):
        sig = cls.getSignature(True)
        # Convert Lfoo/bar/Baz; to foo/bar/Baz.java
        path = sig[1:-1].replace('/', os.sep) + '.java'
        file_path = os.path.join(output_dir, path)

        # Create directory
        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        try:
            java_class = cls.getJavaClass()
            if not java_class:
                print('[!] %s: No Java class' % sig)
                return False

            code = java_class.getBody()
            if not code or code.isEmpty():
                print('[!] %s: Empty code' % sig)
                return False

            with open(file_path, 'w') as f:
                f.write(str(code))
            return True

        except Exception as e:
            print('[!] %s: %s' % (sig, str(e)))
            return False


def run(ctx):
    ExportDecompiled().run(ctx)
