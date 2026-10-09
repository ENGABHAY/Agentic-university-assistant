import asyncio, inspect, json, pytest
from mcp_server import server, erp
from app import sessions

TOOLS = [server.get_profile, server.get_courses, server.get_attendance, server.get_marks, server.get_exam_schedule]
run = asyncio.run


def test_tools_take_no_student_id():
    for t in TOOLS:
        assert len(inspect.signature(t).parameters) == 0


def test_login_checks_credentials():
    assert run(erp.login("CS101", "abhay123")) == {"mock_student": "101"}
    for u, p in [("CS101", "wrong"), ("nobody", "x"), ("CS101", "riya123")]:
        with pytest.raises(erp.ERPLoginError):
            run(erp.login(u, p))


def test_each_session_sees_only_own_data(monkeypatch):
    monkeypatch.setenv("ERP_SESSION_STATE", json.dumps(run(erp.login("CS101", "abhay123"))))
    assert run(server.get_profile())["name"] == "Abhay"
    assert run(server.get_attendance())["courses"]["Data Science"] == 68
    monkeypatch.setenv("ERP_SESSION_STATE", json.dumps(run(erp.login("CS202", "riya123"))))
    assert run(server.get_profile())["name"] == "Riya"


def test_no_session_blocked(monkeypatch):
    monkeypatch.delenv("ERP_SESSION_STATE", raising=False)
    for t in TOOLS:
        with pytest.raises(PermissionError):
            run(t())


def test_session_store_expiry_and_delete(monkeypatch):
    sid = sessions.create("cs101", {"a": 1})
    assert sessions.get(sid) == ("cs101", {"a": 1})
    sessions.delete(sid)
    assert sessions.get(sid) is None
    sid = sessions.create("cs101", {"a": 1})
    monkeypatch.setattr(sessions, "TTL", -1)
    sessions._S[sid] = (0, "cs101", sessions._S[sid][2])
    assert sessions.get(sid) is None


def test_start_login_mock_has_no_captcha():
    assert run(erp.start_login()) == (None, None)
