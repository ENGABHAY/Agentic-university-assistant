"""MCP server. Identity comes ONLY from the environment set by the backend when it
spawns this process for an authenticated user. No tool accepts a student ID."""
import os
from mcp.server.fastmcp import FastMCP
from .erp import get_erp

mcp = FastMCP("university-erp")
_erp = get_erp()


def _me() -> str:
    uid = os.environ.get("AUTH_USER_ERP_ID")
    if not uid:
        raise PermissionError("Unauthenticated: no user context.")
    return uid


@mcp.tool()
def get_profile() -> dict:
    """Get the current student's profile (name, roll number, department, semester)."""
    return _erp.fetch(_me(), "profile")


@mcp.tool()
def get_courses() -> list:
    """Get the courses the current student is enrolled in."""
    return _erp.fetch(_me(), "courses")


@mcp.tool()
def get_attendance() -> dict:
    """Get the current student's attendance percentage per course."""
    return {"courses": _erp.fetch(_me(), "attendance"), "unit": "percent"}


@mcp.tool()
def get_marks() -> dict:
    """Get the current student's marks per course."""
    return {"courses": _erp.fetch(_me(), "marks")}


@mcp.tool()
def get_exam_schedule() -> list:
    """Get the current student's exam schedule."""
    return _erp.fetch(_me(), "exam_schedule")


if __name__ == "__main__":
    mcp.run()  # stdio
