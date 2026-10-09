import os, requests, streamlit as st

API = os.getenv("BACKEND_URL", "http://localhost:8000")
st.set_page_config(page_title="University Assistant", page_icon="🎓")
st.title("🎓 University Assistant")
ss = st.session_state

if "mode" not in ss:
    ss.mode = None  # None | "guest" | "student"

if ss.mode is None:
    tab1, tab2 = st.tabs(["Student login", "Continue as guest"])
    with tab1:
        with st.form("login"):
            email = st.text_input("Email"); pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in"):
                r = requests.post(f"{API}/login", json={"email": email, "password": pw})
                if r.ok:
                    ss.update(mode="student", token=r.json()["access_token"], msgs=[], sid=None); st.rerun()
                else:
                    st.error("Invalid credentials")
        st.caption("Demo: abhay@example.com / abhay123 · riya@example.com / riya123")
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
    if st.sidebar.button("Log out"):
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