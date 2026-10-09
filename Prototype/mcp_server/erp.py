"""ERP data source. Swap MockERP for PlaywrightERP in Phase 7 without touching the tools."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "mock_erp.json"


class MockERP:
    def __init__(self):
        self._db = json.loads(DATA.read_text())

    def fetch(self, student_id: str, section: str):
        student = self._db.get(student_id)
        if student is None:
            raise PermissionError("No ERP record for the authenticated user.")
        return student[section]


class PlaywrightERP:
    """Phase 7 stub. Only use where the university permits automated access.
    Must not bypass CAPTCHA/MFA/rate limits. Use an isolated browser context per user."""

    def fetch(self, student_id: str, section: str):
        raise NotImplementedError("Implement login/navigate/parse with Playwright here.")


def get_erp():
    return MockERP()
