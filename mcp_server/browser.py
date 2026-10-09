"""Generic READ-ONLY ERP navigator (one instance per chat request, inside the MCP server process).
The LLM can only: list menu links, open a link, read the page, choose a dropdown option, click view-type buttons.
It can NOT type into fields. Write-looking buttons are refused and every non-GET request is blocked (see erp.block_writes)."""
import logging, re
from urllib.parse import urljoin
from .erp import ERPSessionExpired, WRITE_WORDS, LOGOUT, _cfg, block_writes

log = logging.getLogger("erp.nav")
ANCHORS = ("() => [...document.querySelectorAll('a')].map((a,i) => "
           "({i, t:(a.textContent||'').replace(/\\s+/g,' ').trim(), h:a.getAttribute('href')}))")


class ERPBrowser:
    def __init__(self, state: dict):
        self.state, self.page, self._selects = dict(state), None, []

    async def _ensure(self):
        if self.page:
            return
        from playwright.async_api import async_playwright
        cfg = _cfg()
        home = self.state.pop("_home_url", None) or cfg.get("home_url") or cfg["login_url"]
        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch(headless=True, channel=cfg.get("browser_channel"))
        ctx = await self.browser.new_context(storage_state=self.state)
        await ctx.route("**/*", block_writes)
        self.page = await ctx.new_page()
        await self.page.goto(home, wait_until="networkidle")
        await self._check()

    async def _check(self):
        if await self.page.locator("input[type=password]:visible").count() > 0:
            raise ERPSessionExpired("ERP_SESSION_EXPIRED: the student must log out and log in again.")

    async def _settle(self):
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        await self.page.wait_for_timeout(800)

    async def list_menu(self) -> dict:
        await self._ensure()
        seen, items = set(), []
        for fr in self.page.frames:
            for a in await fr.evaluate(ANCHORS):
                t = a["t"]
                if t and len(t) < 60 and t.lower() not in seen and not LOGOUT.search(t):
                    seen.add(t.lower()); items.append(t)
        return {"url": self.page.url, "links": items[:150]}

    async def open_item(self, text: str) -> dict:
        await self._ensure()
        want, best = text.strip().lower(), None
        for fr in self.page.frames:
            for a in await fr.evaluate(ANCHORS):
                t = a["t"].lower()
                if not t or LOGOUT.search(t):
                    continue
                score = 2 if t == want else 1 if want in t else 0
                if score and (best is None or score > best[0]):
                    best = (score, fr, a)
        if not best:
            return {"error": f"No link named '{text}'. Call erp_list_menu to see the available links."}
        _, fr, a = best
        log.info("ERP action: open link")
        h = a["h"]
        if h and not h.startswith(("#", "javascript")):
            await self.page.goto(urljoin(fr.url, h), wait_until="networkidle")  # plain GET
        else:
            await fr.locator("a").nth(a["i"]).dispatch_event("click")
        await self._settle()
        return await self.read()

    async def read(self, limit: int = 6000) -> dict:
        await self._ensure()
        await self._check()
        self._selects, texts, drops, buttons = [], [], [], []
        for fr in self.page.frames:
            try:
                texts.append(await fr.locator("body").inner_text(timeout=5000))
            except Exception:
                continue
            sels = fr.locator("select")
            for i in range(await sels.count()):
                s = sels.nth(i)
                if not await s.is_visible():
                    continue
                info = await s.evaluate("e => ({o:[...e.options].map(o=>o.text.trim()), "
                                        "s:(e.options[e.selectedIndex]||{}).text||'', "
                                        "l:(e.labels&&e.labels[0]&&e.labels[0].innerText)||e.getAttribute('aria-label')||e.name||e.id||''})")
                drops.append({"index": len(drops), "label": info["l"].strip(), "selected": info["s"].strip(),
                              "options": info["o"][:60]})
                self._selects.append((fr, i))
            for b in await fr.locator("button:visible, input[type=submit]:visible, input[type=button]:visible").all():
                lab = ((await b.get_attribute("value")) or (await b.text_content()) or "").strip()
                if lab and not WRITE_WORDS.search(lab) and lab not in buttons:
                    buttons.append(lab)
        text = re.sub(r"\n{3,}", "\n\n", "\n---\n".join(texts)).strip()
        return {"url": self.page.url, "title": await self.page.title(), "text": text[:limit],
                "truncated": len(text) > limit, "dropdowns": drops, "buttons": buttons[:15]}

    async def select(self, index: int, option: str) -> dict:
        await self._ensure()
        if not self._selects:
            await self.read()
        if not 0 <= index < len(self._selects):
            return {"error": "No such dropdown. Use the index from erp_read_page."}
        fr, i = self._selects[index]
        s = fr.locator("select").nth(i)
        opts = await s.evaluate("e => [...e.options].map(o=>o.text.trim())")
        want = option.strip().lower()
        pick = next((o for o in opts if o.lower() == want), None) or next((o for o in opts if want in o.lower()), None)
        if not pick:
            return {"error": f"Option not found. Available: {opts[:60]}"}
        log.info("ERP action: select option")
        await s.select_option(label=pick)
        await self._settle()
        return await self.read()

    async def click(self, text: str) -> dict:
        await self._ensure()
        if WRITE_WORDS.search(text) or LOGOUT.search(text):
            return {"error": "Refused: this looks like an action that changes data. The assistant is read-only."}
        want = text.strip().lower()
        for fr in self.page.frames:
            btns = fr.locator("button:visible, input[type=submit]:visible, input[type=button]:visible")
            for i in range(await btns.count()):
                b = btns.nth(i)
                lab = ((await b.get_attribute("value")) or (await b.text_content()) or "").strip()
                if want in lab.lower():
                    if WRITE_WORDS.search(lab) or LOGOUT.search(lab):
                        return {"error": "Refused: read-only assistant."}
                    log.info("ERP action: click button")
                    await b.click()
                    await self._settle()
                    return await self.read()
        return {"error": f"No button named '{text}'. See 'buttons' from erp_read_page."}
