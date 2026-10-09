import base64, os, requests, streamlit as st

API = os.getenv("BACKEND_URL", "http://localhost:8000")
st.set_page_config(page_title="University Assistant", page_icon="🎓")
st.title("🎓 University Assistant")
ss = st.session_state
ss.setdefault("mode", None)  # None | "guest" | "student"

if ss.mode is None:
    tab1, tab2 = st.tabs(["Student login (ERP)", "Continue as guest"])
    with tab1:
        if "pending" not in ss:
            try:
                d = requests.post(f"{API}/login/start", timeout=90).json()
                ss.pending, ss.captcha = d.get("pending_id"), d.get("captcha_image")
            except Exception:
                ss.pending, ss.captcha = None, None
                st.error("Could not reach the ERP right now.")
        if ss.get("err"):
            st.error(ss.pop("err"))
        with st.form("login"):
            u = st.text_input("ERP username"); pw = st.text_input("ERP password", type="password")
            cap = ""
            if ss.get("captcha"):
                st.image(base64.b64decode(ss.captcha), caption="Type the characters shown (from the ERP)")
                cap = st.text_input("Captcha")
            go = st.form_submit_button("Log in")
        if st.button("Refresh captcha"):
            ss.pop("pending", None); st.rerun()
        if go:
            with st.spinner("Verifying with ERP..."):
                r = requests.post(f"{API}/login", json={"username": u, "password": pw,
                                  "pending_id": ss.get("pending"), "captcha": cap}, timeout=90)
            if r.ok:
                ss.pop("pending", None); ss.pop("captcha", None)
                ss.update(mode="student", token=r.json()["access_token"], msgs=[], sid=None); st.rerun()
            else:
                ss.err = r.json().get("detail", "Login failed")
                ss.pop("pending", None); st.rerun()
        st.caption("Use your college ERP login. Your password is only used to sign in to the ERP and is never stored. "
                   "The assistant is read-only. Demo (mock mode): CS101 / abhay123 · CS202 / riya123")
    with tab2:
        st.write("Ask general questions about college rules, syllabus and notices. "
                 "Personal info (attendance, marks, exams) needs a student login.")
        if st.button("Continue as guest"):
            ss.update(mode="guest", msgs=[], sid=None); st.rerun()
    st.stop()

if ss.mode == "guest":
    st.sidebar.info("Guest mode: general college information only.")
    if st.sidebar.button("Log in as student"):
        ss.clear(); st.rerun()
else:
    st.sidebar.success("Logged in via ERP (read-only)")
    if st.sidebar.button("Log out"):
        try: requests.post(f"{API}/logout", headers={"Authorization": f"Bearer {ss.token}"}, timeout=10)
        except Exception: pass
        ss.clear(); st.rerun()

for m in ss.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("tools"): st.caption("Tools used: " + ", ".join(m["tools"]))

if q := st.chat_input("Ask a question..."):
    ss.msgs.append({"role": "user", "content": q})
    with st.chat_message("user"): st.markdown(q)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            if ss.mode == "guest":
                hist = [{"role": m["role"], "content": m["content"]} for m in ss.msgs[:-1]]
                r = requests.post(f"{API}/chat/guest", json={"message": q, "history": hist}, timeout=120)
            else:
                r = requests.post(f"{API}/chat", json={"message": q, "session_id": ss.sid},
                                  headers={"Authorization": f"Bearer {ss.token}"}, timeout=120)
        if r.status_code == 401:
            ss.clear(); st.error("Session expired. Please log in again."); st.stop()
        if r.status_code == 429:
            st.warning("Too many questions. Please wait a minute."); st.stop()
        d = r.json() if r.ok else {"answer": "Something went wrong.", "tools_used": []}
        ss.sid = d.get("session_id", ss.get("sid"))
        tools = list(dict.fromkeys(d.get("tools_used", [])))
        st.markdown(d["answer"])
        if tools: st.caption("Tools used: " + ", ".join(tools))
    ss.msgs.append({"role": "assistant", "content": d["answer"], "tools": tools})
