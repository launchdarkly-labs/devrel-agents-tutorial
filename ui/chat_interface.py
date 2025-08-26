import streamlit as st
import requests
import json

st.set_page_config(
    page_title="Enterprise AI Assistant",
    page_icon="🤖",
    layout="wide"
)

st.markdown("""
<style>
.main {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    color: white;
}
.stChatMessage {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(10px);
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.stTitle {
    color: white;
}
</style>
""", unsafe_allow_html=True)

st.title("🤖 Enterprise AI Assistant")
st.markdown("*Advanced AI/ML technical support powered by LaunchDarkly AI Config*")

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
            with st.expander("⚙️ Agent Configuration"):
                st.json(message["metadata"])

# Chat input
if prompt := st.chat_input("💬 Ask about AI/ML concepts, algorithms, or techniques..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Get agent response
    try:
        response = requests.post(
            "http://localhost:8001/chat",
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
                    "model": data["model"],
                    "tools_used": data["tool_calls"]
                }
            })
            
            # Display assistant message
            with st.chat_message("assistant"):
                st.write(data["response"])
                with st.expander("⚙️ Agent Configuration"):
                    st.json({
                        "variation": data["variation_key"],
                        "model": data["model"],
                        "tools_used": data["tool_calls"]
                    })
        else:
            st.error(f"Error: {response.status_code}")
            
    except Exception as e:
        st.error(f"Connection error: {e}")

# Sidebar for user settings
with st.sidebar:
    st.header("⚙️ Configuration")
    new_user_id = st.text_input("👤 User ID", value=st.session_state.user_id, 
                               help="Different User IDs may receive different AI configurations via LaunchDarkly")
    if new_user_id != st.session_state.user_id:
        st.session_state.user_id = new_user_id
        st.rerun()
    
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 💡 Example Queries")
    st.code("What is reinforcement learning?")
    st.code("Explain Q-learning algorithm") 
    st.code("How does temporal difference work?")
    st.code("Define Markov Decision Process")