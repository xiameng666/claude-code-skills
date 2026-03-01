#?description=Export class hierarchy (extends/implements) to JSON
#?shortcut=

import json
import os
from com.pnfsoftware.jeb.client.api import IScript, IGraphicalClientContext
from com.pnfsoftware.jeb.core.units.code.android import IDexUnit

EXCLUDE = [
    'Landroid/', 'Landroidx/', 'Lkotlin/', 'Lkotlinx/',
    'Ljava/', 'Ljavax/', 'Ldalvik/',
    'Lorg/intellij/', 'Lorg/jetbrains/',
    'Lokhttp3/', 'Lretrofit2/', 'Lio/reactivex/',
    'Lcom/squareup/', 'Lcom/bumptech/', 'Lorg/apache/', 'Lorg/json/',
    'Lsun/', 'Lcom/sun/',
]


class ExportDeps(IScript):

  def run(self, ctx):
    prj = ctx.getMainProject()
    assert prj, 'Please open an APK first'

    output_file = os.path.join(os.path.expanduser('~'), 'jeb-deps.json')
    if isinstance(ctx, IGraphicalClientContext):
      r = ctx.displayQuestionBox('Export', 'Output JSON path:', output_file)
      if r:
        output_file = r

    result = {'classes': []}
    for dex in prj.findUnits(IDexUnit):
      for cls in dex.getClasses():
        sig = cls.getSignature(True)
        if self._skip(sig):
          continue
        try:
          result['classes'].append(self._extract(cls))
        except Exception as e:
          print('[!] %s: %s' % (sig, e))

    with open(output_file, 'w') as f:
      json.dump(result, f, indent=2, ensure_ascii=False)
    print('[+] Done! %d classes -> %s' % (len(result['classes']), output_file))

  def _skip(self, sig):
    for p in EXCLUDE:
      if sig.startswith(p):
        return True
    return False

  def _extract(self, cls):
    sig = cls.getSignature(True)
    info = {
      'signature': sig, 'name': cls.getName(True),
      'accessFlags': cls.getAccessFlags(),
      'supertype': None, 'interfaces': [], 'fields': [], 'methods': [],
    }
    try:
      info['supertype'] = cls.getSupertypeSignature(True)
    except: pass
    try:
      for iface in cls.getInterfaceSignatures(True):
        info['interfaces'].append(iface)
    except: pass
    for f in cls.getFields():
      try:
        info['fields'].append({
          'name': f.getName(True),
          'type': f.getFieldTypeSignature(True),
          'accessFlags': f.getAccessFlags(),
        })
      except: pass
    for m in cls.getMethods():
      try:
        mi = {'name': m.getName(True), 'accessFlags': m.getGenericFlags()}
        try:
          rt = m.getReturnType()
          if rt: mi['returnType'] = rt.getSignature()
        except: pass
        try:
          params = m.getParameterTypes()
          if params: mi['paramTypes'] = [p.getSignature() for p in params]
        except: pass
        info['methods'].append(mi)
      except: pass
    return info
