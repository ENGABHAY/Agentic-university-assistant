"""ERP access. READ-ONLY by design.
ERP_MODE=mock (default) uses data/mock_erp.json; ERP_MODE=playwright uses the real ERP via erp_config.json."""
import base64, hmac, json, os, re, secrets, time
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
MODE = os.getenv("ERP_MODE", "mock")
# Read-only guards. By default ONLY GET requests are allowed. If the ERP needs POST just to VIEW data
# (e.g. choosing a semester), set ERP_ALLOW_POST_VIEW=1; POSTs to URLs that look like write actions stay blocked.
ALLOW_POST_VIEW = os.getenv("ERP_ALLOW_POST_VIEW") == "1"
WRITE_WORDS = re.compile(r"(save|update|delete|remove|insert|create|edit|modify|change|pay|register|enrol|apply|"
                         r"upload|confirm|cancel|withdraw|reset|password|submit-?form)", re.I)
LOGOUT = re.compile(r"log-?out|sign-?out", re.I)


class ERPLoginError(Exception):
    pass


class ERPSessionExpired(PermissionError):
    pass


def _mock():
    return json.loads((ROOT / "data" / "mock_erp.json").read_text())


def _cfg():
    return json.loads((ROOT / "erp_config.json").read_text())


# ---------------- login (the ONLY place a write/POST is allowed) ----------------
_PENDING = {}  # pending_id -> (expires, playwright, browser, ctx, page)
_PENDING_TTL = 180
CAPTCHA_IMG = "img[src*=aptcha], img[id*=aptcha], img[alt*=aptcha], [id*=aptcha] img, [class*=aptcha] img"


async def _close(pid):
    item = _PENDING.pop(pid, None)
    if item:
        try:
            await item[2].close()
            await item[1].stop()
        except Exception:
            pass


async def start_login():
    """Open the ERP login page in the background. Returns (pending_id, captcha_png_base64 | None).
    The CAPTCHA is shown to the STUDENT, who solves it. The app never solves or bypasses it."""
    if MODE == "mock":
        return None, None
    from playwright.async_api import async_playwright
    for pid, item in list(_PENDING.items()):
        if item[0] < time.time():
            await _close(pid)
    if len(_PENDING) >= 20:
        raise RuntimeError("Too many pending logins")
    cfg = _cfg()
    p = await async_playwright().start()
    browser = None
    try:
        browser = await p.chromium.launch(headless=True, channel=cfg.get("browser_channel"))
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(cfg["login_url"], wait_until="networkidle")
        img = None
        loc = page.locator(cfg.get("captcha_image_selector") or CAPTCHA_IMG)
        if await loc.count() > 0:
            img = base64.b64encode(await loc.first.screenshot()).decode()
    except Exception:
        if browser:
            await browser.close()
        await p.stop()
        raise
    pid = secrets.token_urlsafe(16)
    _PENDING[pid] = (time.time() + _PENDING_TTL, p, browser, ctx, page)
    return pid, img


async def login(username: str, password: str, pending_id: str | None = None, captcha: str = "") -> dict:
    """Verify credentials against the ERP. Returns an opaque session state. Password is never stored."""
    if MODE == "mock":
        for sid, s in _mock().items():
            ok_user = s["login"]["username"].lower() == username.lower()
            if ok_user and hmac.compare_digest(s["login"]["password"], password):
                return {"mock_student": sid}
        raise ERPLoginError("Invalid ERP username or password.")

    item = _PENDING.get(pending_id)
    if not item or item[0] < time.time():
        await _close(pending_id)
        raise ERPLoginError("Login page expired. Please refresh the captcha and try again.")
    cfg, ctx, page = _cfg(), item[3], item[4]
    try:
        texts = page.locator("input:visible:not([type=password]):not([type=hidden]):not([type=checkbox])"
                             ":not([type=radio]):not([type=submit]):not([type=button])")
        pwd = page.locator("input[type=password]:visible").first
        if await pwd.count() == 0:
            raise ERPLoginError("Could not find the ERP login form.")
        await texts.nth(0).fill(username)
        await pwd.fill(password)
        if captcha:
            cap = page.locator(cfg["captcha_input_selector"]) if cfg.get("captcha_input_selector") else texts.nth(1)
            await cap.fill(captcha)
        await pwd.press("Enter")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1500)
        if await page.locator("input[type=password]:visible").count() > 0:
            raise ERPLoginError("Login failed: wrong ID, password or captcha. Please try again with the new captcha.")
        return await ctx.storage_state()
    finally:
        await _close(pending_id)


# ---------------- reading ----------------
async def fetch(state: dict, section: str) -> dict:
    """Mock-mode data only. In real mode the MCP server uses mcp_server/browser.py to navigate the ERP."""
    if not state:
        raise ERPSessionExpired("No ERP session. Please log in again.")
    student = _mock().get(state.get("mock_student"))
    if student is None:
        raise PermissionError("No ERP record for the authenticated user.")
    data = student[section]
    if section == "attendance":
        return {"courses": data, "unit": "percent"}
    if section in ("courses", "marks"):
        return {"courses": data}
    return {"exams": data} if section == "exam_schedule" else data


async def block_writes(route):
    """Hard read-only guard applied to every request of the navigation browser."""
    r = route.request
    if LOGOUT.search(r.url):
        await route.abort()
    elif r.method in ("GET", "HEAD", "OPTIONS"):
        await route.continue_()
    elif ALLOW_POST_VIEW and not WRITE_WORDS.search(r.url):
        await route.continue_()
    else:
        await route.abort()
