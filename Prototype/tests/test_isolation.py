import inspect, pytest
from mcp_server import server

TOOLS = [server.get_profile, server.get_courses, server.get_attendance, server.get_marks, server.get_exam_schedule]


def test_tools_take_no_student_id():
    for t in TOOLS:
        assert len(inspect.signature(t).parameters) == 0  # LLM cannot pick an ID


def test_each_user_only_sees_own_data(monkeypatch):
    monkeypatch.setenv("AUTH_USER_ERP_ID", "101")
    assert server.get_profile()["name"] == "Abhay"
    assert server.get_attendance()["courses"]["Data Science"] == 68
    monkeypatch.setenv("AUTH_USER_ERP_ID", "202")
    assert server.get_profile()["name"] == "Riya"


def test_unauthenticated_blocked(monkeypatch):
    monkeypatch.delenv("AUTH_USER_ERP_ID", raising=False)
    for t in TOOLS:
        with pytest.raises(PermissionError):
            t()


def test_unknown_user_blocked(monkeypatch):
    monkeypatch.setenv("AUTH_USER_ERP_ID", "999")
    with pytest.raises(PermissionError):
        server.get_marks()
