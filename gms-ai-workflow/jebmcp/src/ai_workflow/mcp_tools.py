# -*- coding: utf-8 -*-
"""
AI 工作流 - MCP 工具定义

工具分类：
1. 重命名同步 - JEB 重命名 + SQLite/MD 同步
2. 知识库管理 - 目录初始化、数据导入
3. 分析报告 - 上下文准备、报告生成

详细工作流请参考: skills/gms-ai-workflow/SKILL.md
"""
import os
import json
import re

from .rename_sync import RenameSync
from .ai_workflow import AIWorkflow


def _normalize_class_name(class_name: str) -> str:
    """标准化类名为 JNI 格式"""
    if not class_name.startswith("L"):
        if "." in class_name:
            return "L" + class_name.replace(".", "/") + ";"
        else:
            return "L" + class_name + ";"
    return class_name


def _get_ai_workflow(knowledge_dir: str = None) -> AIWorkflow:
    """获取 AIWorkflow 实例"""
    kdir = knowledge_dir or os.environ.get("KNOWLEDGE_DIR", "./knowledge")
    return AIWorkflow(kdir)


def register_tools(mcp, jeb_call, get_rename_sync, reset_rename_sync):
    """注册所有 AI 工作流 MCP 工具。

    @param mcp: FastMCP 实例
    @param jeb_call: JEB JSON-RPC 调用函数
    @param get_rename_sync: 获取 RenameSync 单例的函数
    @param reset_rename_sync: 重置 RenameSync 单例（切换知识库时调用）
    """

    # ============================================================
    #  智能初始化工具
    # ============================================================

    @mcp.tool()
    def check_workflow_status(knowledge_dir: str = None):
        """检查工作流状态，判断是否需要初始化。

        Args:
            knowledge_dir: 知识库目录（可选）

        Returns:
            {status, jeb_connected, knowledge_initialized, has_classes, next_step}
        """
        result = {
            "status": "unknown",
            "jeb_connected": False,
            "knowledge_initialized": False,
            "has_classes": False,
            "next_step": None,
            "details": {}
        }

        # 1. 检查 JEB 连接
        try:
            jeb_status = jeb_call('ping')
            result["jeb_connected"] = "Successfully" in str(jeb_status) or jeb_status.get("success", False)

            if result["jeb_connected"]:
                project_info = jeb_call('has_projects')
                result["details"]["has_jeb_project"] = project_info.get("has_projects", False)
        except Exception as e:
            result["details"]["jeb_error"] = str(e)
            result["next_step"] = "请在 JEB 中启动 MCP 服务 (Edit -> Scripts -> MCP)"
            return result

        # 2. 检查知识库
        try:
            sync = get_rename_sync() if knowledge_dir is None else RenameSync(knowledge_dir)
            result["knowledge_initialized"] = os.path.exists(sync.db_path)
            result["details"]["db_path"] = sync.db_path
            result["details"]["notes_dir"] = sync.notes_dir

            if result["knowledge_initialized"]:
                stats = sync.get_stats()
                result["has_classes"] = stats.get("class_count", 0) > 0
                result["details"]["class_count"] = stats.get("class_count", 0)
        except Exception as e:
            result["details"]["knowledge_error"] = str(e)
            result["next_step"] = "初始化知识库: init_knowledge_base(knowledge_dir)"
            return result

        # 3. 确定状态和下一步
        if not result["knowledge_initialized"]:
            result["status"] = "need_init"
            result["next_step"] = "初始化知识库: init_knowledge_base(knowledge_dir)"
        elif not result["has_classes"]:
            result["status"] = "need_import"
            result["next_step"] = "导出并导入类: export_dependencies() + import_from_jeb_json()"
        else:
            result["status"] = "ready"
            result["next_step"] = "可以开始分析类"

        return result

    @mcp.tool()
    def smart_initialize(knowledge_dir: str, project_name: str = "GMS", auto_export: bool = True):
        """智能初始化工作流 - 一键完成所有初始化步骤。

        此工具会自动：
        1. 初始化知识库目录结构
        2. 从 JEB 导出类依赖
        3. 导入到知识库

        Args:
            knowledge_dir: 知识库绝对路径
            project_name: 项目名称
            auto_export: 是否自动从 JEB 导出（默认 True）

        Returns:
            {success, steps_completed, steps_failed, details}
        """
        steps_completed = []
        steps_failed = []
        details = {}

        # Step 1: 初始化知识库
        try:
            init_result = RenameSync.init_knowledge_base(knowledge_dir, project_name)
            if init_result.get("success"):
                steps_completed.append("init_knowledge_base")
                details["knowledge_dir"] = knowledge_dir
                details["db_path"] = init_result.get("db_path")
            else:
                steps_failed.append(("init_knowledge_base", init_result.get("error", "Unknown error")))
        except Exception as e:
            steps_failed.append(("init_knowledge_base", str(e)))

        # 设置为当前知识库
        os.environ["KNOWLEDGE_DIR"] = knowledge_dir
        reset_rename_sync()

        # Step 2: 从 JEB 导出（如果启用）
        if auto_export:
            try:
                export_result = jeb_call('export_dependencies')
                if export_result.get("success"):
                    steps_completed.append("export_dependencies")
                    json_path = export_result.get("output_path")
                    details["exported_classes"] = export_result.get("class_count")
                    details["json_path"] = json_path

                    # Step 3: 导入到知识库
                    sync = get_rename_sync()
                    import_result = sync.import_from_jeb_json(json_path)
                    if import_result.get("success") or import_result.get("imported", 0) > 0:
                        steps_completed.append("import_from_jeb_json")
                        details["imported_classes"] = import_result.get("imported", 0)
                    else:
                        steps_failed.append(("import_from_jeb_json", import_result.get("error", "No classes imported")))
                else:
                    steps_failed.append(("export_dependencies", export_result.get("error", "Export failed")))
            except Exception as e:
                steps_failed.append(("export_dependencies", str(e)))

        return {
            "success": len(steps_failed) == 0,
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
            "details": details,
            "message": "初始化完成: %d 步骤成功, %d 步骤失败" % (len(steps_completed), len(steps_failed))
        }

    # ============================================================
    #  带文件系统同步的重命名工具
    # ============================================================

    @mcp.tool()
    def rename_class_with_sync(class_name: str, new_name: str, note: str = ""):
        """重命名类，同步到 SQLite + MD 文件。

        Args:
            class_name: 类签名（支持 JNI/Java/简短格式）
            new_name: 新类名
            note: 重命名原因备注

        Returns:
            {success, jeb_result, sync_result, obfuscated, renamed, md_file}
        """
        sync = get_rename_sync()
        class_name = _normalize_class_name(class_name)

        try:
            jeb_result = jeb_call('rename_class_name', class_name, new_name)
        except Exception as e:
            return {"success": False, "error": f"JEB 重命名失败: {str(e)}", "jeb_renamed": False}

        sync_result = sync.rename_class(class_name, new_name, note)
        return {
            "success": sync_result.get("success", True),
            "jeb_result": jeb_result,
            "sync_result": sync_result,
            "obfuscated": class_name,
            "renamed": new_name,
            "md_file": sync_result.get("md_file")
        }

    @mcp.tool()
    def rename_method(class_name: str, method_sig: str, new_name: str, note: str = ""):
        """重命名方法，同步到 SQLite。

        Args:
            class_name: 类签名（JNI 格式）
            method_sig: 方法签名或简单方法名
            new_name: 新方法名
            note: 备注说明

        Returns:
            {success, jeb_result, sync_result, class, method_sig, renamed}
        """
        sync = get_rename_sync()
        class_name = _normalize_class_name(class_name)

        try:
            jeb_result = jeb_call('rename_method_name', class_name, method_sig, new_name)
        except Exception as e:
            return {"success": False, "error": f"JEB 重命名失败: {str(e)}", "jeb_renamed": False}

        sync_result = sync.rename_method(class_name, method_sig, new_name, note)
        return {
            "success": sync_result.get("success", True),
            "jeb_result": jeb_result,
            "sync_result": sync_result,
            "class": class_name,
            "method_sig": method_sig,
            "renamed": new_name
        }

    @mcp.tool()
    def rename_field(class_name: str, field_name: str, new_name: str, note: str = ""):
        """重命名字段，同步到 SQLite。

        Args:
            class_name: 类签名（JNI 格式）
            field_name: 字段名
            new_name: 新字段名
            note: 备注说明

        Returns:
            {success, jeb_result, sync_result, class, field_name, renamed}
        """
        sync = get_rename_sync()
        class_name = _normalize_class_name(class_name)

        try:
            jeb_result = jeb_call('rename_field_name', class_name, field_name, new_name)
        except Exception as e:
            return {"success": False, "error": f"JEB 重命名失败: {str(e)}", "jeb_renamed": False}

        sync_result = sync.rename_field(class_name, field_name, new_name, note)
        return {
            "success": sync_result.get("success", True),
            "jeb_result": jeb_result,
            "sync_result": sync_result,
            "class": class_name,
            "field_name": field_name,
            "renamed": new_name
        }

    @mcp.tool()
    def rename_batch_with_sync(rename_operations: str, note: str = ""):
        """批量重命名，同步到 SQLite。

        Args:
            rename_operations: JSON 数组，元素包含 type/old_name/new_name
                - type: "class" | "method" | "field"
                - old_name: "类名.符号名" 格式（如 "fvxn.a", "fvxn.B"）
                  * 类名使用简短名（不含包路径），如 "fvxn" 而非 "Lfvxn;"
                  * 方法只需方法名，不需要签名（如 "fvxn.a" 而非 "fvxn.a(J)V"）
                  * 字段只需字段名（如 "fvxn.B"）
                - new_name: 新名称
            note: 备注说明

        Returns:
            {success, jeb_result, sync_results, total_synced}

        示例:
            [
              {"type": "method", "old_name": "fvxn.a", "new_name": "onLocationUpdate"},
              {"type": "field", "old_name": "fvxn.B", "new_name": "locationCallback"}
            ]
        """
        sync = get_rename_sync()

        try:
            operations = json.loads(rename_operations)
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON 解析失败: {str(e)}"}

        try:
            jeb_result = jeb_call('rename_batch_symbols', rename_operations)
        except Exception as e:
            return {"success": False, "error": f"JEB 批量重命名失败: {str(e)}", "jeb_renamed": False}

        sync_results = []
        for op in operations:
            op_type = op.get("type")
            old_name = op["old_name"]
            new_name = op["new_name"]

            if not old_name.startswith("L") and op_type in ["class", "method", "field"]:
                if "." in old_name.split(".")[0] if "." in old_name else False:
                    old_name = "L" + old_name.replace(".", "/") + ";"
                elif op_type == "class":
                    old_name = "L" + old_name + ";"

            if op_type == "class":
                result = sync.rename_class(old_name, new_name, note)
            elif op_type == "method":
                parts = old_name.rsplit(".", 1) if "." in old_name else [old_name, "a"]
                result = sync.rename_method(
                    parts[0] if len(parts) > 1 else old_name,
                    parts[1] if len(parts) > 1 else old_name,
                    new_name, note)
            elif op_type == "field":
                parts = old_name.rsplit(".", 1) if "." in old_name else [old_name, "a"]
                result = sync.rename_field(
                    parts[0] if len(parts) > 1 else old_name,
                    parts[1] if len(parts) > 1 else old_name,
                    new_name, note)
            else:
                result = {"success": False, "error": f"未知类型: {op_type}"}

            sync_results.append({
                "type": op_type, "obfuscated": old_name,
                "renamed": new_name, "sync_success": result.get("success", False)
            })

        return {
            "success": True, "jeb_result": jeb_result,
            "sync_results": sync_results,
            "total_synced": len([r for r in sync_results if r["sync_success"]])
        }

    # ============================================================
    #  重命名查询工具
    # ============================================================

    @mcp.tool()
    def get_rename_index_stats():
        """获取重命名索引统计信息。

        Returns:
            {class_count, method_count, field_count, total_count, last_updated, db_path}
        """
        sync = get_rename_sync()
        return sync.get_stats()

    @mcp.tool()
    def lookup_rename(obfuscated: str):
        """查询混淆名对应的重命名。

        Args:
            obfuscated: 混淆名（支持 JNI/Java/简短格式）

        Returns:
            {obfuscated, renamed, found}
        """
        sync = get_rename_sync()
        obfuscated = _normalize_class_name(obfuscated)
        renamed = sync.get_class_rename(obfuscated)
        return {"obfuscated": obfuscated, "renamed": renamed, "found": renamed is not None}

    @mcp.tool()
    def get_rename(obfuscated: str):
        """获取类的所有重命名信息（类+方法+字段）。

        Args:
            obfuscated: 类混淆名（支持 JNI/Java/简短格式）

        Returns:
            {class, methods, fields}
        """
        sync = get_rename_sync()
        obfuscated = _normalize_class_name(obfuscated)
        return sync.get_all_renames(obfuscated)

    # ============================================================
    #  知识库管理工具
    # ============================================================

    @mcp.tool()
    def set_knowledge_dir(knowledge_dir: str):
        """设置知识库目录路径。

        Args:
            knowledge_dir: 知识库绝对路径

        Returns:
            {success, knowledge_dir, db_path, notes_dir}
        """
        os.environ["KNOWLEDGE_DIR"] = knowledge_dir
        reset_rename_sync()
        sync = get_rename_sync()
        return {
            "success": True,
            "knowledge_dir": knowledge_dir,
            "db_path": sync.db_path,
            "notes_dir": sync.notes_dir
        }

    @mcp.tool()
    def init_knowledge_base(knowledge_dir: str, project_name: str = "GMS"):
        """初始化知识库目录结构。

        Args:
            knowledge_dir: 知识库绝对路径
            project_name: 项目名称

        Returns:
            {success, knowledge_dir, db_path, notes_dir, reports_dir, ...}
        """
        result = RenameSync.init_knowledge_base(knowledge_dir, project_name)

        # 设置为当前知识库
        os.environ["KNOWLEDGE_DIR"] = knowledge_dir
        reset_rename_sync()

        return result

    @mcp.tool()
    def import_from_jeb_json(json_path: str, knowledge_dir: str = None, create_md: bool = True):
        """从 JEB 导出的 JSON 批量导入类信息。

        Args:
            json_path: JEB ExportDeps.py 导出的 JSON 路径
            knowledge_dir: 知识库目录（可选）
            create_md: 是否创建 MD 文件（默认 True）

        Returns:
            {total, imported, skipped}
        """
        sync = get_rename_sync() if knowledge_dir is None else RenameSync(knowledge_dir)
        json_path = os.path.expanduser(json_path)
        return sync.import_from_jeb_json(json_path)

    # ============================================================
    #  AI 模块分析工具
    # ============================================================

    @mcp.tool()
    def list_analyzed_classes(knowledge_dir: str = None):
        """列出所有已分析的类。

        Args:
            knowledge_dir: 知识库目录（可选）

        Returns:
            类列表 [{obfuscated, renamed, md_created, note}, ...]
        """
        workflow = _get_ai_workflow(knowledge_dir)
        return workflow.list_classes()

    @mcp.tool()
    def get_analysis_stats(knowledge_dir: str = None):
        """获取分析统计信息。

        Args:
            knowledge_dir: 知识库目录（可选）

        Returns:
            {total_classes, analyzed_classes, renamed_classes, ...}
        """
        workflow = _get_ai_workflow(knowledge_dir)
        return workflow.get_stats()

    @mcp.tool()
    def get_class_md_content(obfuscated: str, knowledge_dir: str = None):
        """获取类的 MD 分析文件内容。

        Args:
            obfuscated: 类混淆名
            knowledge_dir: 知识库目录（可选）

        Returns:
            MD 文件内容字符串
        """
        workflow = _get_ai_workflow(knowledge_dir)
        return workflow.get_class_md_content(obfuscated)

    @mcp.tool()
    def prepare_module_context(seed_classes: str, knowledge_dir: str = None):
        """准备模块分析上下文。

        Args:
            seed_classes: 种子类列表（逗号分隔）
            knowledge_dir: 知识库目录（可选）

        Returns:
            上下文字符串，包含已分析类摘要和 MD 内容
        """
        workflow = _get_ai_workflow(knowledge_dir)
        seed_list = [s.strip() for s in seed_classes.split(",")]
        return workflow.prepare_module_context(seed_list)

    @mcp.tool()
    def generate_module_report(module_name: str, classes: str, structure: str = "", knowledge_dir: str = None):
        """生成模块分析报告。

        Args:
            module_name: 模块名称（如 gms/location）
            classes: 类列表（逗号分隔）
            structure: mermaid 类图（可选）
            knowledge_dir: 知识库目录（可选）

        Returns:
            报告文件路径
        """
        workflow = _get_ai_workflow(knowledge_dir)

        class_list = []
        for cls_name in [s.strip() for s in classes.split(",")]:
            obf = cls_name if cls_name.startswith("L") else f"L{cls_name};"
            md_content = workflow.get_class_md_content(obf)
            class_info = {"obfuscated": obf}
            if md_content:
                renamed_match = re.search(r'renamed: "([^"]+)"', md_content)
                if renamed_match:
                    class_info["renamed"] = renamed_match.group(1)
            class_list.append(class_info)

        return workflow.generate_module_report(module_name, class_list, structure)

    @mcp.tool()
    def create_session_report(seed_class: str, analyzed: str, findings: str,
                              renames: str, issues: str, next_steps: str,
                              knowledge_dir: str = None):
        """创建分析会话报告。

        Args:
            seed_class: 种子类（分析起点）
            analyzed: 分析过的类（JSON 数组）
            findings: 发现列表（JSON 数组）
            renames: 重命名列表（JSON 数组）
            issues: 问题列表（JSON 数组）
            next_steps: 下一步计划（JSON 数组）
            knowledge_dir: 知识库目录（可选）

        Returns:
            报告文件路径
        """
        workflow = _get_ai_workflow(knowledge_dir)
        return workflow.create_session_report(
            seed_class,
            json.loads(analyzed) if analyzed else [],
            json.loads(findings) if findings else [],
            json.loads(renames) if renames else [],
            json.loads(issues) if issues else [],
            json.loads(next_steps) if next_steps else []
        )
