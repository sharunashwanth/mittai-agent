import json
import uuid

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Chat", layout="wide")

# Initialize session state
if "conversations" not in st.session_state:
    st.session_state.conversations = {}
if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None
if "init_done" not in st.session_state:
    st.session_state.init_done = False
if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0


def get_or_create_conversation():
    if st.session_state.current_conversation_id is None:
        conv_id = str(uuid.uuid4())
        st.session_state.conversations[conv_id] = {"title": "New Chat", "messages": []}
        st.session_state.current_conversation_id = conv_id
    return st.session_state.current_conversation_id


def start_new_conversation():
    conv_id = str(uuid.uuid4())
    st.session_state.conversations[conv_id] = {"title": "New Chat", "messages": []}
    st.session_state.current_conversation_id = conv_id


def current_chat_has_messages():
    if st.session_state.current_conversation_id is None:
        return False
    conv = st.session_state.conversations.get(st.session_state.current_conversation_id)
    return conv and len(conv.get("messages", [])) > 0


def fetch_conversation_list():
    try:
        resp = httpx.get(f"{API_BASE}/conversations-list", timeout=5.0)
        if resp.status_code == 200:
            return resp.json().get("conversations", [])
    except httpx.RequestError:
        pass
    return []


def load_conversation(conv_id: str):
    if conv_id in st.session_state.conversations:
        return
    try:
        resp = httpx.get(f"{API_BASE}/chat/{conv_id}", timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            messages = data.get("messages", [])
            title = "Chat"
            for msg in messages:
                if msg.get("role") == "user":
                    title = msg.get("content", "Chat")[:40]
                    break
            st.session_state.conversations[conv_id] = {"title": title, "messages": messages}
    except httpx.RequestError:
        pass


# --- Sidebar ---
with st.sidebar:
    st.title("💬 Conversations")

    if st.button("➕ New Chat", use_container_width=True, disabled=not current_chat_has_messages()):
        start_new_conversation()
        st.rerun()

    st.divider()

    # Load from API only once on startup
    if not st.session_state.init_done:
        for conv_id in fetch_conversation_list():
            load_conversation(conv_id)
        st.session_state.init_done = True

    # Display from local state (fast) - newest first
    conv_ids = list(st.session_state.conversations.keys())
    for conv_id in reversed(conv_ids):
        conv_data = st.session_state.conversations[conv_id]
        if not conv_data.get("messages"):
            continue
            
        is_current = conv_id == st.session_state.current_conversation_id
        label = conv_data.get("title", "Chat")[:30]

        if st.button(
            f"{'\u25b6 ' if is_current else ''}{label}",
            key=conv_id,
            use_container_width=True,
            type="primary" if is_current else "secondary",
        ):
            st.session_state.current_conversation_id = conv_id
            st.rerun()

# --- Main Chat Area ---
st.title("Chat")

conv_id = get_or_create_conversation()
messages = st.session_state.conversations[conv_id]["messages"]

# File upload at top
uploaded = st.file_uploader("Upload a document (PDF/TXT)", type=["pdf", "txt"], key=f"upload_{st.session_state.upload_key}")
if uploaded:
    # Check if already uploaded in this conversation (by checking messages)
    already_uploaded = any(
        msg.get("content", "").startswith(f"User uploaded a document: {uploaded.name}")
        for msg in messages if msg.get("role") == "system"
    )
    
    if not already_uploaded:
        with st.spinner(f"Uploading {uploaded.name}..."):
            files = {"file": (uploaded.name, uploaded.getvalue())}
            data = {"conversation_id": conv_id}
            try:
                resp = httpx.post(f"{API_BASE}/ingest-file", files=files, data=data, timeout=60.0)
                if resp.status_code == 200:
                    messages.append({"role": "system", "content": f"User uploaded a document: {uploaded.name}"})
                    st.session_state.upload_key += 1  # Clear uploader
                    st.rerun()
            except httpx.RequestError:
                st.error("Failed to upload file")

# Display chat history
for msg in messages:
    role = msg["role"]
    content = msg["content"]
    
    if role == "system" and content.startswith("User uploaded a document:"):
        filename = content.split("\n")[0].replace("User uploaded a document: ", "")
        with st.chat_message("user"):
            st.markdown(f"📎 **Uploaded:** {filename}")
    elif role in ["user", "assistant"]:
        with st.chat_message(role):
            st.markdown(content)

# Chat input
prompt = st.chat_input("Type your message...")

if prompt:
    # Display and store user message first
    with st.chat_message("user"):
        st.markdown(prompt)
    messages.append({"role": "user", "content": prompt})

    if st.session_state.conversations[conv_id]["title"] == "New Chat":
        st.session_state.conversations[conv_id]["title"] = prompt[:40]

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        tool_status = st.status("Thinking...")

        try:
            with httpx.stream(
                "POST",
                f"{API_BASE}/chat",
                json={"message": prompt, "conversation_id": conv_id},
                timeout=120.0,
            ) as response:
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        try:
                            event_data = json.loads(line[6:])
                            if event_data["type"] == "text":
                                full_response += event_data["content"]
                                response_placeholder.markdown(full_response + "▌")
                            elif event_data["type"] == "tool_call":
                                for name, _ in event_data["content"]:
                                    tool_status.update(label=f"Using {name}...")
                        except json.JSONDecodeError:
                            pass

            response_placeholder.markdown(full_response)
            tool_status.update(label="Done", state="complete")

        except httpx.RequestError as e:
            st.error(f"Connection error: {e}")
            full_response = "Sorry, I couldn't connect to the server."

        messages.append({"role": "assistant", "content": full_response})
    
    st.rerun()
