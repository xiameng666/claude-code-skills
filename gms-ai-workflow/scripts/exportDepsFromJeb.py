# -*- coding: utf-8 -*-
#?description=Export class dependencies including method body references (FIXED)
#?shortcut=

"""
Enhanced Dependency Export Script (FIXED VERSION)

Correctly extracts method body dependencies using JEB API:
  - Uses getType() and getValue() to parse instruction parameters
  - Resolves indices from DEX constant pools
  - Extracts class references from method/field/type references

Usage:
  1. Open APK in JEB
  2. File -> Scripts -> Run Script...
  3. Select this script
  4. Enter output path (default: ~/jeb-deps-enhanced.json)
"""

import json
import os
import time
from com.pnfsoftware.jeb.client.api import IScript, IGraphicalClientContext
from com.pnfsoftware.jeb.core.units.code.android import IDexUnit
from com.pnfsoftware.jeb.core.units.code.android.dex import IDalvikInstruction


# SDK class prefixes (exclude)
EXCLUDE = [
    'Landroid/', 'Landroidx/', 'Lkotlin/', 'Lkotlinx/',
    'Ljava/', 'Ljavax/', 'Ldalvik/',
    'Lorg/intellij/', 'Lorg/jetbrains/',
    'Lokhttp3/', 'Lretrofit2/', 'Lio/reactivex/',
    'Lcom/squareup/', 'Lcom/bumptech/', 'Lorg/apache/', 'Lorg/json/',
    'Lsun/', 'Lcom/sun/',
]


class ExportDepsEnhancedFixed(IScript):

    def run(self, ctx):
        prj = ctx.getMainProject()
        assert prj, 'Please open an APK first'

        # Ask for output path
        output_file = os.path.join(os.path.expanduser('~'), 'jeb-deps-enhanced.json')
        if isinstance(ctx, IGraphicalClientContext):
            r = ctx.displayQuestionBox('Export Enhanced Dependencies', 'Output JSON path:', output_file)
            if not r:
                print('[*] Cancelled by user')
                return
            output_file = r

        result = {'classes': [], 'stats': {'total': 0, 'skipped': 0, 'errors': 0}}

        # Progress tracking
        start_time = time.time()
        last_progress_time = start_time

        # First pass: count total classes (for progress percentage)
        print('[*] Counting total classes...')
        total_classes = 0
        for dex in prj.findUnits(IDexUnit):
            for cls in dex.getClasses():
                if not self._skip(cls.getSignature(True)):
                    total_classes += 1
        print('[*] Found %d classes to process (excluding SDK)' % total_classes)
        print()

        # Process all DEX units
        for dex in prj.findUnits(IDexUnit):
            print('[*] Processing DEX: %s' % dex.getName())

            for cls in dex.getClasses():
                sig = cls.getSignature(True)

                # Skip SDK classes
                if self._skip(sig):
                    result['stats']['skipped'] += 1
                    continue

                try:
                    class_info = self._extract(cls, dex)
                    result['classes'].append(class_info)
                    result['stats']['total'] += 1

                    # Progress (every 100 classes)
                    if result['stats']['total'] % 100 == 0:
                        current_time = time.time()
                        elapsed = current_time - start_time
                        speed = result['stats']['total'] / elapsed if elapsed > 0 else 0

                        # Calculate progress
                        progress = (result['stats']['total'] * 100.0) / total_classes if total_classes > 0 else 0

                        # Estimate remaining time
                        remaining_classes = total_classes - result['stats']['total']
                        eta_seconds = remaining_classes / speed if speed > 0 else 0
                        eta_minutes = int(eta_seconds / 60)

                        print('[+] Progress: %d/%d (%.1f%%) | Speed: %.1f classes/sec | ETA: %d min' %
                              (result['stats']['total'], total_classes, progress, speed, eta_minutes))

                except Exception as e:
                    print('[!] Error processing %s: %s' % (sig, e))
                    result['stats']['errors'] += 1

        # Save result
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print('[+] Done!')
        print('    Total classes: %d' % result['stats']['total'])
        print('    Skipped (SDK): %d' % result['stats']['skipped'])
        print('    Errors: %d' % result['stats']['errors'])
        print('    Output: %s' % output_file)

    def _skip(self, sig):
        """Check if SDK class"""
        for p in EXCLUDE:
            if sig.startswith(p):
                return True
        return False

    def _extract(self, cls, dex):
        """Extract complete class dependencies"""
        sig = cls.getSignature(True)

        info = {
            'signature': sig,
            'name': cls.getName(True),
            'accessFlags': cls.getAccessFlags(),
            'supertype': None,
            'interfaces': [],
            'fields': [],
            'methods': [],
            'method_body_deps': []
        }

        # Superclass
        try:
            info['supertype'] = cls.getSupertypeSignature(True)
        except:
            pass

        # Interfaces
        try:
            for iface in cls.getInterfaceSignatures(True):
                info['interfaces'].append(iface)
        except:
            pass

        # Fields
        for f in cls.getFields():
            try:
                info['fields'].append({
                    'name': f.getName(True),
                    'type': f.getFieldTypeSignature(True),
                    'accessFlags': f.getAccessFlags(),
                })
            except:
                pass

        # Methods
        for m in cls.getMethods():
            try:
                mi = {
                    'name': m.getName(True),
                    'accessFlags': m.getGenericFlags()
                }

                # Return type
                try:
                    rt = m.getReturnType()
                    if rt:
                        mi['returnType'] = rt.getSignature()
                except:
                    pass

                # Parameter types
                try:
                    params = m.getParameterTypes()
                    if params:
                        mi['paramTypes'] = [p.getSignature() for p in params]
                except:
                    pass

                info['methods'].append(mi)

                # Extract method body dependencies (FIXED)
                method_deps = self._extract_method_body_deps(m, dex)
                if method_deps:
                    info['method_body_deps'].extend(method_deps)

            except:
                pass

        # Deduplicate
        info['method_body_deps'] = list(set(info['method_body_deps']))

        return info

    def _extract_method_body_deps(self, method, dex):
        """
        Extract method body dependencies (FIXED VERSION)

        Uses correct JEB API:
          - param.getType() to get parameter type (TYPE_IDX, TYPE_REG, etc.)
          - param.getValue() to get index value
          - dex.getMethod(idx), dex.getType(idx), dex.getField(idx) to resolve
        """
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

            # Process each instruction
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
                                if class_sig and not self._skip(class_sig):
                                    deps.add(class_sig)
                                break  # Only process the first TYPE_IDX

                    # new-instance (object creation)
                    elif opcode == 'new-instance':
                        if len(params) >= 2:
                            type_param = params[1]
                            if type_param.getType() == IDalvikInstruction.TYPE_IDX:
                                idx = int(type_param.getValue())
                                type_sig = self._resolve_type(idx, dex)
                                if type_sig and not self._skip(type_sig):
                                    deps.add(type_sig)

                    # const-class (Class literal)
                    elif opcode == 'const-class':
                        if len(params) >= 2:
                            type_param = params[1]
                            if type_param.getType() == IDalvikInstruction.TYPE_IDX:
                                idx = int(type_param.getValue())
                                type_sig = self._resolve_type(idx, dex)
                                if type_sig and not self._skip(type_sig):
                                    deps.add(type_sig)

                    # check-cast (type casting)
                    elif opcode == 'check-cast':
                        if len(params) >= 2:
                            type_param = params[1]
                            if type_param.getType() == IDalvikInstruction.TYPE_IDX:
                                idx = int(type_param.getValue())
                                type_sig = self._resolve_type(idx, dex)
                                if type_sig and not self._skip(type_sig):
                                    deps.add(type_sig)

                    # instance-of (type check)
                    elif opcode == 'instance-of':
                        if len(params) >= 3:
                            type_param = params[2]
                            if type_param.getType() == IDalvikInstruction.TYPE_IDX:
                                idx = int(type_param.getValue())
                                type_sig = self._resolve_type(idx, dex)
                                if type_sig and not self._skip(type_sig):
                                    deps.add(type_sig)

                    # Field access (iget/iput/sget/sput)
                    elif opcode.startswith('iget') or opcode.startswith('iput') or \
                         opcode.startswith('sget') or opcode.startswith('sput'):
                        # Last parameter is field index
                        field_param = params[-1]
                        if field_param.getType() == IDalvikInstruction.TYPE_IDX:
                            idx = int(field_param.getValue())
                            class_sig = self._resolve_field_class(idx, dex)
                            if class_sig and not self._skip(class_sig):
                                deps.add(class_sig)

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

    def _resolve_field_class(self, idx, dex):
        """Resolve field index to class signature"""
        try:
            dex_field = dex.getField(idx)
            if dex_field:
                class_type = dex_field.getClassType()
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
    ExportDepsEnhancedFixed().run(ctx)
