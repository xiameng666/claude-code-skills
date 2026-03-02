# -*- coding: utf-8 -*-
#?description=Test method body dependency extraction on a single class
#?shortcut=

"""
Test Script - Verify method body dependency extraction

Features:
  - Select a class to test
  - Display all methods of the class
  - For each method:
    * Show decompiled code
    * Show extracted dependencies
    * Manual verification

Usage:
  1. Open APK in JEB
  2. File -> Scripts -> Run Script...
  3. Select this script
  4. Enter class signature to test (e.g. Lfvxn;)
"""

from com.pnfsoftware.jeb.client.api import IScript, IGraphicalClientContext
from com.pnfsoftware.jeb.core.units.code.android import IDexUnit
from com.pnfsoftware.jeb.core.units.code.android.dex import IDalvikInstruction


class TestMethodBodyDeps(IScript):

    def run(self, ctx):
        prj = ctx.getMainProject()
        assert prj, 'Please open an APK first'

        # 询问要测试的类
        test_class = 'Lfvxn;'
        if isinstance(ctx, IGraphicalClientContext):
            r = ctx.displayQuestionBox('Test Class', 'Enter class signature to test:', test_class)
            if not r:
                print('[*] Cancelled by user')
                return
            test_class = r

        # Normalize class signature
        if not test_class.startswith('L'):
            test_class = 'L' + test_class
        if not test_class.endswith(';'):
            test_class = test_class + ';'

        print('=' * 80)
        print('Testing class: %s' % test_class)
        print('=' * 80)

        # Find the class
        target_class = None
        target_dex = None
        sample_count = 0

        for dex in prj.findUnits(IDexUnit):
            print('[*] Scanning DEX: %s' % dex.getName())
            for cls in dex.getClasses():
                cls_sig = cls.getSignature(True)

                # Debug: show first 3 classes from each DEX
                if sample_count < 3:
                    print('[DEBUG] Sample class: %s' % cls_sig)
                    sample_count += 1

                if cls_sig == test_class:
                    target_class = cls
                    target_dex = dex
                    print('[+] Found in DEX: %s' % dex.getName())
                    break
            if target_class:
                break

        if not target_class:
            print('[!] Class not found: %s' % test_class)
            print('[!] Make sure the class signature is correct')
            print('[!] Expected format: Lfvxn; or Lcom/example/Foo;')
            return

        print('[+] Class found!')
        print('    Name: %s' % target_class.getName(True))
        print('    Methods: %d' % len(target_class.getMethods()))
        print()

        # Test each method
        for i, method in enumerate(target_class.getMethods(), 1):
            self._test_method(method, target_dex, i)

        print('=' * 80)
        print('[+] Test complete!')

    def _test_method(self, method, dex, index):
        """Test dependency extraction for a single method"""
        method_name = method.getName(True)
        method_sig = method.getSignature(True)

        print('-' * 80)
        print('[Method %d] %s' % (index, method_name))
        print('Signature: %s' % method_sig)
        print()

        # Get decompiled code
        try:
            decompiled = self._get_decompiled_code(method)
            if decompiled:
                print('Decompiled Code:')
                print(decompiled[:500])  # Show first 500 chars only
                if len(decompiled) > 500:
                    print('... (truncated)')
                print()
        except Exception as e:
            print('[!] Failed to decompile: %s' % e)
            print()

        # Extract dependencies
        try:
            deps = self._extract_method_body_deps(method, dex)
            if deps:
                print('Extracted Dependencies (%d):' % len(deps))
                for dep in sorted(deps):
                    print('  - %s' % dep)
            else:
                print('No dependencies found')
            print()
        except Exception as e:
            print('[!] Failed to extract deps: %s' % e)
            print()

    def _get_decompiled_code(self, method):
        """Get decompiled code"""
        try:
            # Try to get decompiler
            decomp = method.getClassUnit().getDecompiler()
            if not decomp:
                return None

            # Decompile method
            src = decomp.decompile(method.getSignature(True))
            if src:
                return src
            return None
        except:
            return None

    def _extract_method_body_deps(self, method, dex):
        """Extract method body dependencies (FIXED VERSION)"""
        deps = set()

        try:
            method_data = method.getData()
            if not method_data:
                return deps

            code_item = method_data.getCodeItem()
            if not code_item:
                return deps

            instructions = code_item.getInstructions()
            if not instructions:
                return deps

            for insn in instructions:
                try:
                    opcode = insn.getMnemonic()
                    params = insn.getParameters()
                    if not params:
                        continue

                    # invoke-* instructions (method calls)
                    if opcode.startswith('invoke-'):
                        # Find the first TYPE_IDX parameter (method reference)
                        for param in params:
                            if param.getType() == IDalvikInstruction.TYPE_IDX:
                                idx = int(param.getValue())
                                class_sig = self._resolve_method_class(idx, dex)
                                if class_sig:
                                    deps.add(class_sig)
                                break  # Only process the first TYPE_IDX

                    # new-instance (object creation)
                    elif opcode == 'new-instance':
                        if len(params) >= 2:
                            type_param = params[1]
                            if type_param.getType() == IDalvikInstruction.TYPE_IDX:
                                idx = int(type_param.getValue())
                                type_sig = self._resolve_type(idx, dex)
                                if type_sig:
                                    deps.add(type_sig)

                    # const-class (Class literal)
                    elif opcode == 'const-class':
                        if len(params) >= 2:
                            type_param = params[1]
                            if type_param.getType() == IDalvikInstruction.TYPE_IDX:
                                idx = int(type_param.getValue())
                                type_sig = self._resolve_type(idx, dex)
                                if type_sig:
                                    deps.add(type_sig)

                    # check-cast (type casting)
                    elif opcode == 'check-cast':
                        if len(params) >= 2:
                            type_param = params[1]
                            if type_param.getType() == IDalvikInstruction.TYPE_IDX:
                                idx = int(type_param.getValue())
                                type_sig = self._resolve_type(idx, dex)
                                if type_sig:
                                    deps.add(type_sig)

                    # instance-of (type check)
                    elif opcode == 'instance-of':
                        if len(params) >= 3:
                            type_param = params[2]
                            if type_param.getType() == IDalvikInstruction.TYPE_IDX:
                                idx = int(type_param.getValue())
                                type_sig = self._resolve_type(idx, dex)
                                if type_sig:
                                    deps.add(type_sig)

                except:
                    continue

        except:
            pass

        return list(deps)

    def _resolve_method_class(self, idx, dex):
        """Resolve method index to class signature"""
        try:
            dex_method = dex.getMethod(idx)
            if dex_method:
                class_type = dex_method.getClassType()
                if class_type:
                    return class_type.getSignature(True)
        except:
            pass
        return None

    def _resolve_type(self, idx, dex):
        """Resolve type index to type signature"""
        try:
            dex_type = dex.getType(idx)
            if dex_type:
                return dex_type.getSignature(True)
        except:
            pass
        return None


def run(ctx):
    TestMethodBodyDeps().run(ctx)
