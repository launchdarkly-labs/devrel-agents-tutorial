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

def process_tool_display(tools, tool_details):
    """Single function to process tools and tool_details for consistent UI display"""
    tool_list = []
    
    # Define mapping from actual tool names to display names
    mcp_name_mapping = {
        "search_papers": "arxiv_search",
        "search_semantic_scholar": "semantic_scholar"
    }
    
    for i, tool in enumerate(tools):
        tool_name = tool if isinstance(tool, str) else tool.get("name", str(tool))
        
        # Get search query from matching tool_details with proper name mapping
        search_query = ""
        for detail in tool_details:
            detail_name = detail.get("name")
            # Check both direct match and mapped match
            mapped_name = mcp_name_mapping.get(detail_name, detail_name)
            if mapped_name == tool_name:
                search_query = detail.get("search_query", "") or ""
                break
        
        # Add tool with search query if available
        if search_query:
            tool_list.append(f"{tool_name} ('{search_query}')")
        else:
            tool_list.append(tool_name)
    
    return tool_list

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
        st.session_state.example_query = "Find the best matches for 'deep learning algorithms' in your documentation. Rereank them for closest relevance."

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
                                "http://localhost:8000/feedback",
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
                                "http://localhost:8000/feedback",
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
                        
                        # Use shared tool processing function
                        tools = agent_config.get("tools", [])
                        tool_details = agent_config.get("tool_details", [])
                        processed_tools = process_tool_display(tools, tool_details)
                        
                        config_data = {
                            "variation": agent_config["variation_key"],
                            "model": agent_config["model"]
                        }
                        
                        if processed_tools:
                            config_data["🛠️ tools_used"] = processed_tools
                            
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
            "http://localhost:8000/chat",
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
                
                # Add improved feedback system after the response
                message_obj = None
                for msg in st.session_state.messages:
                    if msg.get("message_id") == message_id:
                        message_obj = msg
                        break
                
                if message_obj:
                    current_feedback = message_obj.get("feedback")
                    
                    # Show feedback status if already provided
                    if current_feedback:
                        feedback_emoji = "👍" if current_feedback == "positive" else "👎"
                        st.caption(f"Feedback recorded: {feedback_emoji}")
                    else:
                        # Show feedback options
                        st.markdown("**Was this response helpful?**")
                        col1, col2, col3 = st.columns([1, 1, 8])
                        
                        with col1:
                            if st.button("👍 Helpful", key=f"new_thumbs_up_{message_id}", help="This response was helpful"):
                                # Send positive feedback to backend
                                try:
                                    feedback_response = requests.post(
                                        "http://localhost:8000/feedback",
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
                                        st.success("Thanks for your feedback! 👍")
                                        st.rerun()
                                    else:
                                        st.error("Failed to submit feedback")
                                except Exception as e:
                                    st.error(f"Failed to submit feedback: {e}")
                        
                        with col2:
                            if st.button("👎 Not helpful", key=f"new_thumbs_down_{message_id}", help="This response was not helpful"):
                                # Send negative feedback to backend
                                try:
                                    feedback_response = requests.post(
                                        "http://localhost:8000/feedback",
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
                                        st.success("Thanks for your feedback! 👎")
                                        st.rerun()
                                    else:
                                        st.error("Failed to submit feedback")
                                except Exception as e:
                                    st.error(f"Failed to submit feedback: {e}")
                    
                with st.expander("⚙️ Multi-Agent Configuration"):
                    if "agent_configurations" in data and data["agent_configurations"]:
                        # Display each agent's configuration
                        for agent_config in data["agent_configurations"]:
                            st.markdown(f"**{agent_config['agent_name']}:**")
                            
                            # Use shared tool processing function
                            tools = agent_config.get("tools", [])
                            tool_details = agent_config.get("tool_details", [])
                            processed_tools = process_tool_display(tools, tool_details)
                            
                            config_data = {
                                "variation": agent_config["variation_key"],
                                "model": agent_config["model"]
                            }
                            
                            if processed_tools:
                                config_data["🛠️ tools_used"] = processed_tools
                                
                            st.json(config_data)
                            st.markdown("---")
                    else:
                        # Fallback to single configuration - use shared tool processing
                        tools_used = data.get("tool_calls", [])
                        # Convert old format to new format for compatibility
                        tool_details = []
                        processed_tools = process_tool_display(tools_used, tool_details)
                        
                        config_data = {
                            "variation": data["variation_key"],
                            "model": data["model"]
                        }
                        
                        if processed_tools:
                            config_data["🛠️ tools_used"] = processed_tools
                            
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
    
