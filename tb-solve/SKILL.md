---
name: tb-solve
description: 解决单框架问题的工作流程
license: MIT
compatibility: opencode
metadata:
  domain: tb-problem-solve
  arch: arm64
  tools: all
---
解压日志：将单框问题的日志文件夹解压，将hilog中的日志解压到上级目录，清除其他不必要的日志文件仅保留压缩包，保持目录规整
阅读日志，分析问题：从问题的Apk包名、复现时间、错误表现入手，在日志中定位问题原因。不限于各种崩溃，闪退，环境检测，系统杀后台等等
给出结论：将总结日志依据、论点与结论，给出全面的分析报告