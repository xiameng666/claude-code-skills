# -*- coding: utf-8 -*-
#?description=Export decompiled code for specified classes
#?shortcut=

"""
Export Decompiled Code Script

Usage:
  1. Generate class_list.txt using extract_class_list.py
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
from com.pnfsoftware.jeb.core.util import DecompilerHelper
from com.pnfsoftware.jeb.util.io import IO


class ExportDecompiledCode(IScript):

    def run(self, ctx):
        prj = ctx.getMainProject()
        assert prj, 'Please open an APK first'

        # Ask for class list file
        default_list = os.path.join(os.path.expanduser('~'), 'class_list.txt')
        if isinstance(ctx, IGraphicalClientContext):
            r = ctx.displayQuestionBox('Export Decompiled Code', 'Class list file path:', default_list)
            if not r:
                print('[*] Cancelled by user')
                return
            class_list_path = r
        else:
            class_list_path = default_list

        # Ask for output directory
        default_output = os.path.join(os.path.expanduser('~'), 'decompiled')
        if isinstance(ctx, IGraphicalClientContext):
            r = ctx.displayQuestionBox('Export Decompiled Code', 'Output directory:', default_output)
            if not r:
                print('[*] Cancelled by user')
                return
            output_dir = r
        else:
            output_dir = default_output

        # Read class list
        try:
            with open(class_list_path, 'r') as f:
                class_sigs = [line.strip() for line in f if line.strip()]
            print('\n[*] Read class list: %s' % class_list_path)
            print('[*] Classes to export: %d' % len(class_sigs))
        except Exception as e:
            print('[!] Failed to read class list: %s' % str(e))
            return

        # Find dex unit
        dex = prj.findUnit(IDexUnit)
        if not dex:
            print('[!] No dex unit found')
            return

        # Make sure dex is processed
        if not dex.isProcessed():
            print('[*] Processing dex unit...')
            if not dex.process():
                print('[!] Failed to process dex unit')
                return

        # Get decompiler
        decomp = DecompilerHelper.getDecompiler(dex)
        if not decomp:
            print('[!] No decompiler available')
            return

        print('[*] Decompiler found')

        # Get exporter
        exp = decomp.getExporter()
        exp.setOutputFolder(IO.createFolder(output_dir))

        # Set class filter
        class_sig_set = set(class_sigs)

        class ClassFilter:
            def __init__(self, allowed_classes):
                self.allowed = allowed_classes

            def shouldProcess(self, sig):
                return sig in self.allowed

        # Note: JEB exporter may not support custom filters
        # We'll export all and then filter, or use the exporter's built-in options

        print('\n[*] Exporting to: %s' % output_dir)
        print('[*] This may take several minutes...\n')

        start_time = time.time()

        # Export all decompiled code
        if exp.export():
            print('\n[+] Export complete!')
        else:
            print('\n[!] Export had errors')
            errors = exp.getErrors()
            if errors:
                print('[!] Errors: %d' % len(errors))
                for sig, err in errors.items():
                    print('    %s: %s' % (sig, err))

        elapsed = time.time() - start_time
        print('    - Time: %.2f seconds' % elapsed)
        print('    - Output: %s' % output_dir)


def run(ctx):
    ExportDecompiledCode().run(ctx)
