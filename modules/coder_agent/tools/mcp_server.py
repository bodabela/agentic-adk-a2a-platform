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
def generate_code_files(
    specification: str,
    language: str = "python",
    output_format: str = "json",
) -> dict:
    """Generate code file contents based on a specification.

    Args:
        specification: Description of what code to generate
        language: Programming language (python, typescript, etc.)
        output_format: Output format (json)

    Returns:
        Dictionary with generated file paths and contents
    """
    return {
        "status": "success",
        "files": [
            {
                "path": f"src/main.{_ext(language)}",
                "content": (
                    f"# Generated from specification\n"
                    f"# Language: {language}\n"
                    f"# Spec: {specification}\n"
                ),
                "language": language,
            }
        ],
        "summary": f"Generated 1 file for: {specification}",
    }


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


def _ext(language: str) -> str:
    mapping = {
        "python": "py",
        "typescript": "ts",
        "javascript": "js",
        "java": "java",
        "go": "go",
        "rust": "rs",
    }
    return mapping.get(language, "txt")


if __name__ == "__main__":
    mcp.run(transport="stdio")
