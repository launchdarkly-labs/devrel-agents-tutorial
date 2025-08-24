import streamlit as st
import requests
import json

st.title("Support Agent Chat")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "user_id" not in st.session_state:
    st.session_state.user_id = "user_001"

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message["role"] == "assistant" and "metadata" in message:
            with st.expander("Agent Details"):
                st.json(message["metadata"])

# Chat input
if prompt := st.chat_input("Ask your question"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Get agent response
    try:
        response = requests.post(
            "http://localhost:8000/chat",
            json={
                "user_id": st.session_state.user_id,
                "message": prompt
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Add assistant message
            st.session_state.messages.append({
                "role": "assistant", 
                "content": data["response"],
                "metadata": {
                    "variation": data["variation_key"],
                    "tools_used": data["tool_calls"]
                }
            })
            
            # Display assistant message
            with st.chat_message("assistant"):
                st.write(data["response"])
                with st.expander("Agent Details"):
                    st.json({
                        "variation": data["variation_key"],
                        "tools_used": data["tool_calls"]
                    })
        else:
            st.error(f"Error: {response.status_code}")
            
    except Exception as e:
        st.error(f"Connection error: {e}")

# Sidebar for user settings
with st.sidebar:
    st.header("User Settings")
    new_user_id = st.text_input("User ID", value=st.session_state.user_id)
    if new_user_id != st.session_state.user_id:
        st.session_state.user_id = new_user_id
        st.rerun()
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()