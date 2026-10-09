"""READ-ONLY MCP server. The ERP session is injected by the backend when it spawns this process.
No tool takes a student ID, and no tool can change anything in the ERP."""
import json, os
from mcp.server.fastmcp import FastMCP
from .erp import MODE, fetch

mcp = FastMCP("university-erp")


def _state() -> dict:
    raw = os.environ.get("ERP_SESSION_STATE")
    if not raw:
        raise PermissionError("Unauthenticated: no ERP session.")
    return json.loads(raw)


if MODE == "mock":  # demo data tools
    @mcp.tool()
    async def get_profile() -> dict:
        """Read the current student's profile (read-only)."""
        return await fetch(_state(), "profile")

    @mcp.tool()
    async def get_courses() -> dict:
        """Read the courses the current student is enrolled in (read-only)."""
        return await fetch(_state(), "courses")

    @mcp.tool()
    async def get_attendance() -> dict:
        """Read the current student's attendance (read-only)."""
        return await fetch(_state(), "attendance")

    @mcp.tool()
    async def get_marks() -> dict:
        """Read the current student's marks (read-only)."""
        return await fetch(_state(), "marks")

    @mcp.tool()
    async def get_exam_schedule() -> dict:
        """Read the current student's exam schedule (read-only)."""
        return await fetch(_state(), "exam_schedule")
else:  # real ERP: navigate like a student, read-only
    from .browser import ERPBrowser
    _b = None

    def _br() -> ERPBrowser:
        global _b
        if _b is None:
            _b = ERPBrowser(_state())
        return _b

    @mcp.tool()
    async def erp_list_menu() -> dict:
        """List the link/menu names available in the ERP right now (read-only)."""
        return await _br().list_menu()

    @mcp.tool()
    async def erp_open(link_text: str) -> dict:
        """Open an ERP menu link by its name (e.g. 'Attendance', 'Marks') and return the page content."""
        return await _br().open_item(link_text)

    @mcp.tool()
    async def erp_read_page() -> dict:
        """Read the current ERP page: text, dropdowns (with index and options) and view buttons."""
        return await _br().read()

    @mcp.tool()
    async def erp_select(dropdown_index: int, option_text: str) -> dict:
        """Choose an option (e.g. 'Semester 1', an academic year) in a dropdown listed by erp_read_page; returns the updated page."""
        return await _br().select(dropdown_index, option_text)

    @mcp.tool()
    async def erp_click(button_text: str) -> dict:
        """Click a VIEW-type button (e.g. 'Show', 'View', 'Search'). Buttons that change data are refused."""
        return await _br().click(button_text)


if __name__ == "__main__":
    mcp.run()
