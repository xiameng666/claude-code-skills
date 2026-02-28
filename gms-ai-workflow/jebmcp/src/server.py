# -*- coding: utf-8 -*-
"""
JEB Pro MCP Server - 主入口

职责：
1. 初始化 FastMCP 实例
2. 提供共享基础设施（JSON-RPC 转发、RenameSync 单例）
3. 注册子模块的 MCP 工具
"""
import os
import json
import argparse
import http.client
from pathlib import Path

from fastmcp import FastMCP

from ai_workflow.rename_sync import RenameSync

# ============================================================
#  FastMCP 初始化
# ============================================================

mcp = FastMCP("github.com/flankerhqd/jeb-pro-mcp")

# ============================================================
#  共享基础设施：JSON-RPC 转发到 JEB 插件
# ============================================================

_jsonrpc_request_id = 1


def make_jsonrpc_request(method, *params, jeb_host="127.0.0.1", jeb_port=16161, jeb_path="/mcp"):
    """转发到本地 JEB 插件的 JSON-RPC 接口"""
    global _jsonrpc_request_id
    conn = http.client.HTTPConnection(jeb_host, jeb_port, timeout=30)
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "params": list(params),
        "id": _jsonrpc_request_id,
    }
    _jsonrpc_request_id += 1

    try:
        conn.request("POST", jeb_path, json.dumps(request), {"Content-Type": "application/json"})
        response = conn.getresponse()
        data = json.loads(response.read().decode("UTF-8"))

        if "error" in data:
            err = data["error"]
            code = err.get("code")
            message = err.get("message")
            pretty = f"JSON-RPC error {code}: {message}"
            if "data" in err:
                pretty += "\n" + err["data"]
            raise RuntimeError(pretty)

        result = data.get("result")
        return "success" if result is None else result
    finally:
        conn.close()


def _jeb_call(method, *params):
    """统一的 JEB 调用包装器，从环境变量读取连接参数"""
    return make_jsonrpc_request(
        method, *params,
        jeb_host=os.environ.get("JEB_HOST", "127.0.0.1"),
        jeb_port=int(os.environ.get("JEB_PORT", "16161")),
        jeb_path=os.environ.get("JEB_PATH", "/mcp"),
    )


# ============================================================
#  共享基础设施：RenameSync 单例管理
# ============================================================

_rename_sync = None


def get_rename_sync():
    """获取 RenameSync 单例"""
    global _rename_sync
    if _rename_sync is None:
        knowledge_dir = os.environ.get(
            "KNOWLEDGE_DIR",
            str(Path.home() / "reverse-tool" / "knowledge-base")
        )
        _rename_sync = RenameSync(knowledge_dir)
    return _rename_sync


def reset_rename_sync():
    """重置 RenameSync 单例（切换知识库时调用）"""
    global _rename_sync
    _rename_sync = None


# ============================================================
#  注册子模块的 MCP 工具
# ============================================================

from traditional.mcp_tools import register_tools as register_traditional_tools
from ai_workflow.mcp_tools import register_tools as register_ai_workflow_tools

register_traditional_tools(mcp, _jeb_call)
register_ai_workflow_tools(mcp, _jeb_call, get_rename_sync, reset_rename_sync)


# ============================================================
#  健康检查路由（仅 HTTP 传输时可见）
# ============================================================

@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    from starlette.responses import PlainTextResponse
    return PlainTextResponse("OK")


# ============================================================
#  CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="JEB Pro MCP Server (SSE/HTTP)")
    parser.add_argument("--transport", choices=["sse", "http", "stdio"],
                        default=os.environ.get("TRANSPORT", "stdio"),
                        help="MCP 传输协议：sse、http、stdio(默认)")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                        help="对外绑定地址（sse/http 有效）")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PORT", "16162")),
                        help="对外端口（sse/http 有效，默认 16162）")
    parser.add_argument("--jeb-host", default=os.environ.get("JEB_HOST", "127.0.0.1"))
    parser.add_argument("--jeb-port", type=int, default=int(os.environ.get("JEB_PORT", "16161")))
    parser.add_argument("--jeb-path", default=os.environ.get("JEB_PATH", "/mcp"))
    args = parser.parse_args()

    os.environ["JEB_HOST"] = args.jeb_host
    os.environ["JEB_PORT"] = str(args.jeb_port)
    os.environ["JEB_PATH"] = args.jeb_path

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
