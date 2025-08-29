import streamlit as st
import requests
import json

st.set_page_config(
    page_title="Enterprise AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
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

# Add example queries from TOOL_TEST_QUERIES.md
st.markdown("### 💡 Example Queries:")
st.markdown("*Test different tool combinations with these curated queries*")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📚 Internal Knowledge", use_container_width=True):
        st.session_state.example_query = "What information do you have about machine learning in your knowledge base?"

with col2:
    if st.button("🔍 ArXiv Research", use_container_width=True):
        st.session_state.example_query = "Find recent ArXiv papers on reinforcement learning from the last 6 months"

with col3:
    if st.button("🔬 Academic Search", use_container_width=True):
        st.session_state.example_query = "Search Semantic Scholar for papers on federated learning"

# Additional example queries
col4, col5 = st.columns(2)
with col4:
    if st.button("🎯 RAG + Reranking", use_container_width=True):
        st.session_state.example_query = "Find the best matches for 'deep learning algorithms' in your documentation"

with col5:
    if st.button("🚀 Full Stack Search", use_container_width=True):
        st.session_state.example_query = "Compare what you know about transformers from your knowledge base with recent ArXiv and Semantic Scholar papers"

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
            # Show feedback buttons for assistant messages
            if "message_id" in message:
                message_id = message["message_id"]
                current_feedback = message.get("feedback")
                
                col1, col2, col3 = st.columns([1, 1, 8])
                with col1:
                    feedback_key = f"hist_thumbs_up_{message_id}"
                    disabled = current_feedback == "positive"
                    if st.button("👍", key=feedback_key, disabled=disabled, help="Helpful response"):
                        # Send feedback for historical message
                        try:
                            feedback_response = requests.post(
                                "http://localhost:8001/feedback",
                                json={
                                    "user_id": st.session_state.user_id,
                                    "message_id": message_id,
                                    "user_query": message.get("user_query", ""),
                                    "ai_response": message["content"],
                                    "feedback": "positive",
                                    "variation_key": message["metadata"].get("primary_variation", "unknown"),
                                    "model": message["metadata"].get("primary_model", "unknown"),
                                    "tool_calls": message["metadata"].get("tools_used", []),
                                    "source": "real_user"
                                }
                            )
                            if feedback_response.status_code == 200:
                                message["feedback"] = "positive"
                                st.rerun()
                            else:
                                st.error("Failed to submit feedback")
                        except Exception as e:
                            st.error(f"Failed to submit feedback: {e}")
                
                with col2:
                    feedback_key = f"hist_thumbs_down_{message_id}"
                    disabled = current_feedback == "negative"
                    if st.button("👎", key=feedback_key, disabled=disabled, help="Not helpful"):
                        # Send feedback for historical message
                        try:
                            feedback_response = requests.post(
                                "http://localhost:8001/feedback",
                                json={
                                    "user_id": st.session_state.user_id,
                                    "message_id": message_id,
                                    "user_query": message.get("user_query", ""),
                                    "ai_response": message["content"],
                                    "feedback": "negative",
                                    "variation_key": message["metadata"].get("primary_variation", "unknown"),
                                    "model": message["metadata"].get("primary_model", "unknown"),
                                    "tool_calls": message["metadata"].get("tools_used", []),
                                    "source": "real_user"
                                }
                            )
                            if feedback_response.status_code == 200:
                                message["feedback"] = "negative"
                                st.rerun()
                            else:
                                st.error("Failed to submit feedback")
                        except Exception as e:
                            st.error(f"Failed to submit feedback: {e}")
                            
                # Show current feedback status
                if current_feedback:
                    feedback_emoji = "👍" if current_feedback == "positive" else "👎"
                    st.caption(f"Feedback: {feedback_emoji}")
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
                            tool_name = tool if isinstance(tool, str) else tool.get("name", str(tool))
                            if tool_name in ['search_v1', 'search_v2', 'reranking']:
                                # Add search query if available
                                if isinstance(tool, dict) and tool.get("search_query"):
                                    internal_tools.append(f"{tool_name} ('{tool['search_query']}')")
                                else:
                                    internal_tools.append(tool_name)
                            elif tool_name in ['search_papers', 'search_semantic_scholar']:
                                # Add search query if available
                                if isinstance(tool, dict) and tool.get("search_query"):
                                    mcp_tools.append(f"{tool_name} ('{tool['search_query']}')")
                                else:
                                    mcp_tools.append(tool_name)
                            else:
                                if isinstance(tool, dict) and tool.get("search_query"):
                                    unknown_tools.append(f"{tool_name} ('{tool['search_query']}')")
                                else:
                                    unknown_tools.append(tool_name)
                        
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
            "http://localhost:8001/chat",
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
            
            # Add message with unique ID for feedback tracking
            message_id = f"msg_{len(st.session_state.messages)}"
            st.session_state.messages.append({
                "role": "assistant", 
                "content": data["response"],
                "metadata": metadata,
                "message_id": message_id,
                "user_query": prompt,
                "feedback": None
            })
            
            # Display assistant message
            with st.chat_message("assistant"):
                st.write(data["response"])
                
                # Add feedback buttons after the response
                col1, col2, col3 = st.columns([1, 1, 8])
                
                # Check current feedback status for this message
                current_feedback = None
                for msg in st.session_state.messages:
                    if msg.get("message_id") == message_id:
                        current_feedback = msg.get("feedback")
                        break
                
                with col1:
                    disabled_up = current_feedback == "positive"
                    if st.button("👍", key=f"new_thumbs_up_{message_id}", disabled=disabled_up, help="Helpful response"):
                        # Send feedback to backend
                        try:
                            feedback_response = requests.post(
                                "http://localhost:8001/feedback",
                                json={
                                    "user_id": st.session_state.user_id,
                                    "message_id": message_id,
                                    "user_query": prompt,
                                    "ai_response": data["response"],
                                    "feedback": "positive",
                                    "variation_key": data["variation_key"],
                                    "model": data["model"],
                                    "tool_calls": data["tool_calls"],
                                    "source": "real_user"
                                }
                            )
                            if feedback_response.status_code == 200:
                                # Update message in session state
                                for msg in st.session_state.messages:
                                    if msg.get("message_id") == message_id:
                                        msg["feedback"] = "positive"
                                        break
                                st.success("👍 Thanks for your feedback!")
                                st.rerun()
                            else:
                                st.error("Failed to submit feedback")
                        except Exception as e:
                            st.error(f"Failed to submit feedback: {e}")
                
                with col2:
                    disabled_down = current_feedback == "negative"
                    if st.button("👎", key=f"new_thumbs_down_{message_id}", disabled=disabled_down, help="Not helpful"):
                        # Send feedback to backend
                        try:
                            feedback_response = requests.post(
                                "http://localhost:8001/feedback",
                                json={
                                    "user_id": st.session_state.user_id,
                                    "message_id": message_id,
                                    "user_query": prompt,
                                    "ai_response": data["response"],
                                    "feedback": "negative",
                                    "variation_key": data["variation_key"],
                                    "model": data["model"],
                                    "tool_calls": data["tool_calls"],
                                    "source": "real_user"
                                }
                            )
                            if feedback_response.status_code == 200:
                                # Update message in session state
                                for msg in st.session_state.messages:
                                    if msg.get("message_id") == message_id:
                                        msg["feedback"] = "negative"
                                        break
                                st.success("👎 Thanks for your feedback!")
                                st.rerun()
                            else:
                                st.error("Failed to submit feedback")
                        except Exception as e:
                            st.error(f"Failed to submit feedback: {e}")
                
                # Show current feedback status
                if current_feedback:
                    feedback_emoji = "👍" if current_feedback == "positive" else "👎"
                    st.caption(f"Feedback: {feedback_emoji}")
                    
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
                                tool_name = tool if isinstance(tool, str) else tool.get("name", str(tool))
                                if tool_name in ['search_v1', 'search_v2', 'reranking']:
                                    # Add search query if available
                                    if isinstance(tool, dict) and tool.get("search_query"):
                                        internal_tools.append(f"{tool_name} ('{tool['search_query']}')")
                                    else:
                                        internal_tools.append(tool_name)
                                elif tool_name in ['search_papers', 'search_semantic_scholar']:
                                    # Add search query if available
                                    if isinstance(tool, dict) and tool.get("search_query"):
                                        mcp_tools.append(f"{tool_name} ('{tool['search_query']}')")
                                    else:
                                        mcp_tools.append(tool_name)
                                else:
                                    if isinstance(tool, dict) and tool.get("search_query"):
                                        unknown_tools.append(f"{tool_name} ('{tool['search_query']}')")
                                    else:
                                        unknown_tools.append(tool_name)
                            
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
                            tool_name = tool if isinstance(tool, str) else tool.get("name", str(tool))
                            if tool_name in ['search_v1', 'search_v2', 'reranking']:
                                # Add search query if available
                                if isinstance(tool, dict) and tool.get("search_query"):
                                    internal_tools.append(f"{tool_name} ('{tool['search_query']}')")
                                else:
                                    internal_tools.append(tool_name)
                            elif tool_name in ['search_papers', 'search_semantic_scholar']:
                                # Add search query if available  
                                if isinstance(tool, dict) and tool.get("search_query"):
                                    mcp_tools.append(f"{tool_name} ('{tool['search_query']}')")
                                else:
                                    mcp_tools.append(tool_name)
                            else:
                                if isinstance(tool, dict) and tool.get("search_query"):
                                    unknown_tools.append(f"{tool_name} ('{tool['search_query']}')")
                                else:
                                    unknown_tools.append(tool_name)
                        
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
    
