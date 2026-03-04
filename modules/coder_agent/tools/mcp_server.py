"""Local MCP server for coder_agent - code generation tool."""

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Parse --workspace argument to determine the root directory for file operations
_parser = argparse.ArgumentParser()
_parser.add_argument("--workspace", type=str, default=".")
_args, _ = _parser.parse_known_args()

WORKSPACE = Path(_args.workspace).resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("CodeGeneratorServer")


def _safe_resolve(file_path: str) -> Path:
    """Resolve a path within the workspace, blocking directory traversal."""
    resolved = (WORKSPACE / file_path).resolve()
    if not str(resolved).startswith(str(WORKSPACE)):
        raise ValueError(f"Path escapes workspace: {file_path}")
    return resolved


@mcp.tool()
def list_workspace_files() -> dict:
    """List all files in the workspace.

    Returns:
        Dictionary with list of file paths and their sizes
    """
    files = []
    for p in sorted(WORKSPACE.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(WORKSPACE))
            files.append({"path": rel, "size_bytes": p.stat().st_size})
    return {"status": "success", "files": files, "workspace": str(WORKSPACE)}


@mcp.tool()
def read_code_file(file_path: str) -> dict:
    """Read a code file's contents.

    Args:
        file_path: Relative path within the workspace (e.g. "src/main.rs")

    Returns:
        Dictionary with file content and metadata
    """
    try:
        p = _safe_resolve(file_path)
        if not p.exists() or not p.is_file():
            return {"status": "error", "message": f"File not found: {file_path}"}
        return {
            "status": "success",
            "path": file_path,
            "content": p.read_text(encoding="utf-8"),
            "size_bytes": p.stat().st_size,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def write_code_file(file_path: str, content: str) -> dict:
    """Write content to a code file. Creates parent directories as needed.

    Args:
        file_path: Relative path within the workspace (e.g. "src/main.rs")
        content: The full content to write to the file

    Returns:
        Dictionary with write result
    """
    try:
        p = _safe_resolve(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {
            "status": "success",
            "path": file_path,
            "size_bytes": len(content.encode("utf-8")),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
