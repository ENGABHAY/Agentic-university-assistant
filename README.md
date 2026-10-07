# Agentic University Assistant

> 🚧 **Status: work in progress.** The core features work, but the project is still under active development
> and is not production-ready.

A secure AI assistant for college students that combines:
- **RAG**: answers general questions from official college documents (rules, syllabus, notices), with no login needed.
- **MCP + browser automation**: after the student logs in with their ERP ID, password and CAPTCHA, the agent browses the ERP in the background (**read-only**) to answer personal questions such as attendance and results.
- **LangGraph agent**: decides which source to use, or combines both (e.g. "Am I eligible for the exam?").

## Current status
- ✅ Guest mode with document RAG
- ✅ ERP-verified student login (CAPTCHA solved by the student)
- ✅ Read-only ERP navigation (menus, dropdowns such as semester)
- ✅ Per-student session isolation, encrypted short-lived sessions, passwords never stored
- 🚧 Speed and reliability of ERP navigation
- 🚧 Admin document upload, evaluation, prompt-injection tests, deployment

## Security notes
The LLM never sees passwords or chooses the student identity, and the ERP session is fixed by the backend.
Only use this with your institution's permission.
