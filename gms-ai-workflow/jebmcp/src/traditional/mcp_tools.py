# -*- coding: utf-8 -*-
"""
传统 JEB 工具 - MCP 工具定义

所有工具都是 jeb_call 的薄封装，通过 JSON-RPC 转发到 JEB 插件。
详细工作流请参考: skills/gms-ai-workflow/SKILL.md
"""
import sys


def register_tools(mcp, jeb_call):
    """注册所有传统 JEB MCP 工具。

    @param mcp: FastMCP 实例
    @param jeb_call: JEB JSON-RPC 调用函数
    """

    # ==================== 项目管理 ====================

    @mcp.tool()
    def load_project(file_path: str):
        """打开 APK/DEX 项目。

        Args:
            file_path: APK/DEX 文件绝对路径

        Returns:
            {success, project_info, error}
        """
        try:
            result = jeb_call('load_project', file_path)
            print(result)
            return result
        except Exception as e:
            print(f"Error loading project: {e}")
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def has_projects():
        """检查是否有项目已加载。

        Returns:
            {success, has_projects}
        """
        return jeb_call('has_projects')

    @mcp.tool()
    def get_projects():
        """获取所有已加载项目列表。

        Returns:
            {success, projects}
        """
        return jeb_call('get_projects')

    @mcp.tool()
    def get_current_project_info():
        """获取当前 JEB 会话和项目详细信息。

        Returns:
            {connection_status, projects, apk_metadata, dex_metadata, jeb_version}
        """
        return jeb_call('get_current_project_info')

    @mcp.tool()
    def ping():
        """检查 JEB MCP 服务器连接状态。"""
        try:
            _ = jeb_call("ping")
            return "Successfully connected to JEB Pro"
        except Exception:
            shortcut = "Ctrl+Option+M" if sys.platform == "darwin" else "Ctrl+Alt+M"
            return (
                f"Failed to connect to JEB Pro! "
                f"Did you run Edit -> Scripts -> MCP ({shortcut}) to start the server?"
            )

    # ==================== 反编译与查询 ====================

    @mcp.tool()
    def get_app_manifest():
        """获取当前 APK 的 AndroidManifest.xml。"""
        return jeb_call('get_app_manifest')

    @mcp.tool()
    def get_method_decompiled_code(class_name: str, method_name: str):
        """获取方法的反编译代码。

        Args:
            class_name: 类签名（支持 JNI/Java/简短格式）
            method_name: 方法名

        Returns:
            {success, decompiled_code}
        """
        return jeb_call('get_method_decompiled_code', class_name, method_name)

    @mcp.tool()
    def get_class_decompiled_code(class_signature: str):
        """获取类的反编译代码。

        Args:
            class_signature: 类签名（支持 JNI/Java/简短格式）

        Returns:
            {success, decompiled_code}
        """
        return jeb_call('get_class_decompiled_code', class_signature)

    @mcp.tool()
    def get_method_smali(class_signature: str, method_name: str):
        """获取方法的 Smali 指令。

        Args:
            class_signature: 类签名（支持 JNI/Java/简短格式）
            method_name: 方法名

        Returns:
            {success, smali_instructions}
        """
        return jeb_call('get_method_smali', class_signature, method_name)

    # ==================== 交叉引用 ====================

    @mcp.tool()
    def get_method_callers(class_name: str, method_name: str):
        """获取方法的调用者/引用。

        Args:
            class_name: 类签名（JNI/Java 格式）
            method_name: 方法名

        Returns:
            {success, callers}
        """
        return jeb_call('get_method_callers', class_name, method_name)

    @mcp.tool()
    def get_method_overrides(method_signature: str):
        """获取方法的覆写列表。

        Args:
            method_signature: 完整方法签名（如 Lcom/example/Foo;->bar(I[JLjava/lang/String;)V）

        Returns:
            {success, overrides}
        """
        return jeb_call('get_method_overrides', method_signature)

    @mcp.tool()
    def get_field_callers(class_name: str, field_name: str):
        """获取字段的调用者/引用。

        Args:
            class_name: 类签名（JNI/Java 格式）
            field_name: 字段名

        Returns:
            {success, callers}
        """
        return jeb_call('get_field_callers', class_name, field_name)

    # ==================== 类型分析 ====================

    @mcp.tool()
    def get_class_type_tree(class_signature: str, max_node_count: int = 16):
        """获取类的类型树（继承关系）。

        Args:
            class_signature: 类签名（支持 JNI/Java/简短格式）
            max_node_count: 最大遍历节点数（默认 16）

        Returns:
            {success, type_tree}
        """
        return jeb_call('get_class_type_tree', class_signature, max_node_count)

    @mcp.tool()
    def get_class_superclass(class_signature: str):
        """获取类的父类。

        Args:
            class_signature: 类签名（支持 JNI/Java/简短格式）

        Returns:
            {success, superclass}
        """
        return jeb_call('get_class_superclass', class_signature)

    @mcp.tool()
    def get_class_interfaces(class_signature: str):
        """获取类实现的接口列表。

        Args:
            class_signature: 类签名（支持 JNI/Java/简短格式）

        Returns:
            {success, interfaces}
        """
        return jeb_call('get_class_interfaces', class_signature)

    # ==================== 类检查 ====================

    @mcp.tool()
    def get_class_methods(class_signature: str):
        """获取类的所有方法。

        Args:
            class_signature: 类签名（支持 JNI/Java/简短格式）

        Returns:
            {success, methods, method_count}
        """
        return jeb_call('get_class_methods', class_signature)

    @mcp.tool()
    def get_class_fields(class_signature: str):
        """获取类的所有字段。

        Args:
            class_signature: 类签名（支持 JNI/Java/简短格式）

        Returns:
            {success, fields, field_count}
        """
        return jeb_call('get_class_fields', class_signature)

    @mcp.tool()
    def parse_protobuf_class(class_signature: str):
        """解析 Protobuf 类定义。

        Args:
            class_signature: 类签名（支持 JNI/Java/简短格式）

        Returns:
            {success, protobuf_definition}
        """
        return jeb_call('parse_protobuf_class', class_signature)

    # ==================== 重命名（纯 JEB，不带同步） ====================

    @mcp.tool()
    def rename_class_name(class_name: str, new_name: str):
        """重命名类（仅 JEB，不同步）。

        Args:
            class_name: 类签名（JNI/Java 格式）
            new_name: 新类名

        Returns:
            {success, new_class_name}
        """
        return jeb_call('rename_class_name', class_name, new_name)

    @mcp.tool()
    def rename_method_name(class_name: str, method_name: str, new_name: str):
        """重命名方法（仅 JEB，不同步）。

        Args:
            class_name: 类签名（JNI/Java 格式）
            method_name: 原方法名
            new_name: 新方法名

        Returns:
            {success, new_method_name}
        """
        return jeb_call('rename_method_name', class_name, method_name, new_name)

    @mcp.tool()
    def rename_field_name(class_name: str, field_name: str, new_name: str):
        """重命名字段（仅 JEB，不同步）。

        Args:
            class_name: 类签名（JNI/Java 格式）
            field_name: 原字段名
            new_name: 新字段名

        Returns:
            {success, new_field_name}
        """
        return jeb_call('rename_field_name', class_name, field_name, new_name)

    @mcp.tool(name="rename_batch_symbols", description="批量重命名类/字段/方法")
    def rename_batch_symbols(rename_operations: str):
        """批量重命名（仅 JEB，不同步）。

        Args:
            rename_operations: JSON 数组，元素包含 type/old_name/new_name

        Returns:
            {success, summary, failed_operations}
        """
        return jeb_call('rename_batch_symbols', rename_operations)

    # ==================== 初始化工具 ====================

    @mcp.tool()
    def export_dependencies(output_path: str = None):
        """导出 JEB 项目中所有类的依赖关系到 JSON 文件。

        Args:
            output_path: 输出 JSON 文件路径（默认 ~/jeb-deps.json）

        Returns:
            {success, output_path, class_count, error}
        """
        return jeb_call('export_dependencies', output_path)
