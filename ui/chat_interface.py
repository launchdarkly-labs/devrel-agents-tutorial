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
st.markdown("*Advanced AI/ML technical support powered by LaunchDarkly AI Configs*")

# Add example queries
st.markdown("### 💡 Example Queries:")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🤖 What is machine learning?", use_container_width=True):
        st.session_state.example_query = "What is machine learning and how does it work?"

with col2:
    if st.button("🔍 Search for RL papers", use_container_width=True):
        st.session_state.example_query = "Can you search for recent papers on reinforcement learning?"

with col3:
    if st.button("🧠 Explain neural networks", use_container_width=True):
        st.session_state.example_query = "Explain how neural networks learn and make predictions"

# Additional example queries
col4, col5 = st.columns(2)
with col4:
    if st.button("📊 Compare ML algorithms", use_container_width=True):
        st.session_state.example_query = "Compare supervised vs unsupervised learning algorithms"

with col5:
    if st.button("🔬 Latest AI research", use_container_width=True):
        st.session_state.example_query = "Find recent research papers on transformer architectures"

st.markdown("---")

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
            with st.expander("⚙️ Multi-Agent Configuration"):
                metadata = message["metadata"]
                if "agent_configurations" in metadata:
                    # Display each agent's configuration
                    for agent_config in metadata["agent_configurations"]:
                        st.markdown(f"**{agent_config['agent_name']}:**")
                        
                        # Categorize tools by type
                        tools = agent_config.get("tools", [])
                        internal_tools = []
                        mcp_tools = []
                        unknown_tools = []
                        
                        for tool in tools:
                            if tool in ['search_v1', 'search_v2', 'reranking']:
                                internal_tools.append(tool)
                            elif tool in ['search_papers', 'search_semantic_scholar']:
                                mcp_tools.append(tool)
                            else:
                                unknown_tools.append(tool)
                        
                        config_data = {
                            "variation": agent_config["variation_key"],
                            "model": agent_config["model"]
                        }
                        
                        if internal_tools:
                            config_data["📚 internal_tools"] = internal_tools
                        if mcp_tools:
                            config_data["🔬 mcp_tools"] = mcp_tools
                        if unknown_tools:
                            config_data["🔧 other_tools"] = unknown_tools
                            
                        st.json(config_data)
                        st.markdown("---")
                else:
                    # Fallback for old format
                    st.json(metadata)

# Handle example query selection
if "example_query" in st.session_state:
    prompt = st.session_state.example_query
    del st.session_state.example_query
else:
    prompt = None

# Chat input
if not prompt:
    prompt = st.chat_input("💬 Ask about AI/ML concepts, algorithms, or techniques...")

if prompt:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Get agent response
    try:
        response = requests.post(
            "http://localhost:8002/chat",
            json={
                "user_id": st.session_state.user_id,
                "message": prompt
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Add assistant message with all agent configurations
            metadata = {
                "primary_variation": data["variation_key"],
                "primary_model": data["model"],
                "tools_used": data["tool_calls"]
            }
            
            # Add individual agent configurations if available
            if "agent_configurations" in data and data["agent_configurations"]:
                metadata["agent_configurations"] = data["agent_configurations"]
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": data["response"],
                "metadata": metadata
            })
            
            # Display assistant message
            with st.chat_message("assistant"):
                st.write(data["response"])
                with st.expander("⚙️ Multi-Agent Configuration"):
                    if "agent_configurations" in data and data["agent_configurations"]:
                        # Display each agent's configuration
                        for agent_config in data["agent_configurations"]:
                            st.markdown(f"**{agent_config['agent_name']}:**")
                            
                            # Categorize tools by type
                            tools = agent_config.get("tools", [])
                            internal_tools = []
                            mcp_tools = []
                            unknown_tools = []
                            
                            for tool in tools:
                                if tool in ['search_v1', 'search_v2', 'reranking']:
                                    internal_tools.append(tool)
                                elif tool in ['search_papers', 'search_semantic_scholar']:
                                    mcp_tools.append(tool)
                                else:
                                    unknown_tools.append(tool)
                            
                            config_data = {
                                "variation": agent_config["variation_key"],
                                "model": agent_config["model"]
                            }
                            
                            if internal_tools:
                                config_data["📚 internal_tools"] = internal_tools
                            if mcp_tools:
                                config_data["🔬 mcp_tools"] = mcp_tools
                            if unknown_tools:
                                config_data["🔧 other_tools"] = unknown_tools
                                
                            st.json(config_data)
                            st.markdown("---")
                    else:
                        # Fallback to single configuration - categorize tools
                        tools_used = data.get("tool_calls", [])
                        internal_tools = []
                        mcp_tools = []
                        unknown_tools = []
                        
                        for tool in tools_used:
                            if tool in ['search_v1', 'search_v2', 'reranking']:
                                internal_tools.append(tool)
                            elif tool in ['search_papers', 'search_semantic_scholar']:
                                mcp_tools.append(tool)
                            else:
                                unknown_tools.append(tool)
                        
                        config_data = {
                            "variation": data["variation_key"],
                            "model": data["model"]
                        }
                        
                        if internal_tools:
                            config_data["📚 internal_tools_used"] = internal_tools
                        if mcp_tools:
                            config_data["🔬 mcp_tools_used"] = mcp_tools
                        if unknown_tools:
                            config_data["🔧 other_tools_used"] = unknown_tools
                            
                        st.json(config_data)
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
    
