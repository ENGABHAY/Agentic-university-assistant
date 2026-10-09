# Agentic University Assistant (MVP)

RAG (college documents) + MCP (private ERP tools, mock data) + LangGraph agent, behind JWT auth.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # add your LLM key
python -m scripts.ingest        # index data/raw/*.pdf|txt into Chroma
uvicorn app.main:app --reload   # backend  :8000
streamlit run frontend/streamlit_app.py
pytest                          # authorization/isolation tests
```
Demo logins: `abhay@example.com / abhay123`, `riya@example.com / riya123` (change/remove for real use).
Try: "What is my attendance?", "What's the minimum attendance?", "Can I appear for the exam?"

## Security design
- Identity comes from the JWT -> DB user -> `erp_student_id`; the LLM never supplies it.
- MCP server is spawned per request with the identity in its environment; tools take **no** student ID.
- Users without an ERP identity get no private tools. Retrieved docs are wrapped as untrusted data.
- Chat memory stores only user/assistant text, not raw ERP output. Logs exclude credentials/ERP data.

## Next phases
- Phase 7: implement `PlaywrightERP` in `mcp_server/erp.py` (only where permitted; no CAPTCHA/MFA bypass; isolated browser context per user).
- Phase 9-10: add agent/RAG evals, prompt-injection tests, admin upload endpoint, PostgreSQL via `DATABASE_URL`.
