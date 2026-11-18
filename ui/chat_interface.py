import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Sample users for LaunchDarkly targeting (hardcoded)
sample_users = [
    {"id": "user_other_free_001", "country": "US", "region": "other", "plan": "free"},
    {"id": "user_other_paid_001", "country": "US", "region": "other", "plan": "paid"},
    {"id": "user_eu_free_001", "country": "FR", "region": "eu", "plan": "free"},
    {"id": "user_eu_paid_001", "country": "DE", "region": "eu", "plan": "paid"},
]
print(f" UI: Loaded {len(sample_users)} sample users")

# Function to get user context for LaunchDarkly targeting
def get_user_context(user_id, sample_users):
    """Get user context (country, region, plan) for LaunchDarkly targeting"""
    print(f" UI: Getting user context for user_id={user_id}")
    for user in sample_users:
        if user['id'] == user_id:
            context = {
                "country": user['country'],
                "region": user['region'], 
                "plan": user['plan']
            }
            print(f" UI: Found user context: {context}")
            return context
    # Default context for unknown users
    default_context = {
        "country": "US",
        "region": "other",
        "plan": "free"
    }
    print(f" UI: User not found, using default context: {default_context}")
    return default_context

# Get API configuration from environment
API_HOST = os.getenv('API_HOST', 'localhost')
API_PORT = os.getenv('API_PORT', '8000')
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"

st.set_page_config(
    page_title="LangGraph Multi-Agent System",
    page_icon="→",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
.main {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

/* Simplified header styling */
.header-container {
    background: transparent;
    padding: 1rem 0;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.header-title {
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0;
    color: #ffffff;
    text-align: left;
    margin-bottom: 0.25rem;
}

.header-subtitle {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.7);
    text-align: left;
    margin: 0;
    font-weight: 400;
    line-height: 1.4;
}

.header-badge {
    display: inline-block;
    background: rgba(255, 255, 255, 0.08);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.7rem;
    color: rgba(255, 255, 255, 0.8);
    margin-top: 0.5rem;
    border: 1px solid rgba(255, 255, 255, 0.1);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Simplified example queries section */
.example-queries-container {
    background: transparent;
    padding: 0.5rem 0;
    margin: 1rem 0;
    border: none;
}

.example-queries-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
    margin-bottom: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.example-queries-subtitle {
    color: rgba(255, 255, 255, 0.6);
    margin-bottom: 1rem;
    font-size: 0.75rem;
    line-height: 1.4;
}

/* Gradient button styling inspired by LaunchDarkly cards */
.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    font-weight: 500;
    font-size: 0.8rem;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
    position: relative;
    overflow: hidden;
}

.stButton > button::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
    transition: left 0.5s;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #5a67d8 0%, #6b46c1 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.stButton > button:hover::before {
    left: 100%;
}

.stButton > button:active {
    transform: translateY(0);
    background: linear-gradient(135deg, #4c51bf 0%, #553c9a 100%);
}

/* Chat message styling */
.stChatMessage {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    margin: 0.5rem 0;
}

.stTitle {
    color: white;
}

/* Enhanced dropdown styling */
.stSelectbox > div > div {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    color: white;
}

.stSelectbox > div > div:hover {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.25);
}

.stSelectbox > div > div > div {
    color: white;
}

/* Sidebar styling */
.css-1d391kg {
    background: rgba(0, 0, 0, 0.1);
}

/* Responsive design */
@media (max-width: 768px) {
    .header-title {
        font-size: 1.25rem;
    }
    
    .header-subtitle {
        font-size: 0.8rem;
    }
    
    .example-queries-container {
        padding: 0.25rem 0;
    }
}
</style>
""", unsafe_allow_html=True)

# Simplified header section
st.markdown("""
<div class="header-container">
    <h1 class="header-title">LaunchDarkly Multi-Agent System</h1>
    <p class="header-subtitle">Intelligent document search and research powered by LangGraph and RAG architecture</p>
</div>
""", unsafe_allow_html=True)

def process_tool_display(tools, tool_details):
    """Single function to process tools and tool_details for consistent UI display"""
    tools = tools or []
    tool_details = tool_details or []
    tool_list = []

    for i, tool_name in enumerate(tools):
        # tool_details is in call order, so match by index for repeated tools
        search_query = ""
        if i < len(tool_details) and tool_details[i].get("name") == tool_name:
            search_query = tool_details[i].get("search_query") or ""

        # Add tool with search query if available
        if search_query:
            tool_list.append(f"{tool_name} ('{search_query}')")
        else:
            tool_list.append(tool_name)

    return tool_list

def show_workflow_details(metadata):
    """Show each agent's served configuration and the backend console output"""
    with st.expander("Workflow Details"):
        agent_configurations = metadata.get("agent_configurations")
        if agent_configurations:
            security = next((a for a in agent_configurations if a["agent_name"] == "security-agent"), {})

            # Display each agent's configuration
            for agent_config in agent_configurations:
                st.markdown(f"**{agent_config['agent_name']}:**")

                config_data = {
                    "model": agent_config["model"],
                    "variation_key": agent_config["variation_key"]
                }

                # Show available tools if any
                if agent_config.get("tools"):
                    config_data["tools_available"] = agent_config["tools"]

                # Show tools actually used, with their search queries
                tools_used = process_tool_display(agent_config.get("tools_used"), agent_config.get("tool_details"))
                if tools_used:
                    config_data["tools_used"] = tools_used

                # Show redacted text for supervisor agent only if PII was detected
                if agent_config["agent_name"] == "supervisor-agent" and security.get("detected") and security.get("redacted"):
                    config_data["redacted_text"] = security["redacted"]

                # Show PII findings for security agent
                if agent_config["agent_name"] == "security-agent" and agent_config.get("detected") is not None:
                    config_data["security_clearance"] = {
                        "detected": agent_config["detected"],
                        "types": agent_config.get("types", []),
                        "redacted": agent_config.get("redacted", "")
                    }

                st.json(config_data)
                st.markdown("---")
        else:
            # No per-agent details (e.g. an error response)
            config_data = {
                "model": metadata["primary_model"],
                "variation_key": metadata["primary_variation"]
            }
            if metadata.get("tools_used"):
                config_data["tools_used"] = metadata["tools_used"]
            st.json(config_data)

    with st.expander("Backend Console Output"):
        if metadata.get("console_logs"):
            for log in metadata["console_logs"]:
                st.code(log, language="text")
        else:
            st.markdown("*Console output not captured*")

# Enhanced example queries section
st.markdown("""
<div class="example-queries-container">
    <h3 class="example-queries-title">Example Queries</h3>
    <p class="example-queries-subtitle">Test different tool combinations with these curated queries</p>
</div>
""", unsafe_allow_html=True)

# Row 1: Basic search tools
col1, col2 = st.columns(2)
with col1:
    if st.button("Basic Search", use_container_width=True):
        st.session_state.example_query = "What are the key concepts I should understand from your knowledge base?"

with col2:
    if st.button("RAG + Reranking", use_container_width=True):
        st.session_state.example_query = "Search for implementation guidance, then rerank the results to show me the most relevant information"

# Row 2: Security and research tools
col4, col5, col6 = st.columns(3)
with col4:
    if st.button("Security Check", use_container_width=True):
        st.session_state.example_query = "My name is John Doe, email: john.doe@example.com. I'm a VP at StarSystems, and I need help with my account"

with col5:
    if st.button("ArXiv Research", use_container_width=True):
        st.session_state.example_query = "Find recent ArXiv papers on machine learning from the last 6 months"

with col6:
    if st.button("OpenAlex Research", use_container_width=True):
        st.session_state.example_query = "Search OpenAlex for highly cited research papers on artificial intelligence"

# Row 3: Advanced research
col7 = st.columns(1)[0]
with col7:
    if st.button("Full Research Stack", use_container_width=True):
        st.session_state.example_query = "Compare what you know from your internal documentation with recent academic research papers"

st.markdown("---")

# Initialize session state with dual history for PII isolation
if "messages" not in st.session_state:
    st.session_state.messages = []  # Raw messages (display only, contains PII)

# SECURITY BOUNDARY: Sanitized history for API calls
# This ensures support agent never sees raw PII from conversation history
if "sanitized_messages" not in st.session_state:
    st.session_state.sanitized_messages = []  # PII-free messages (API calls only)

if "user_id" not in st.session_state:
    st.session_state.user_id = "user_other_paid_001"


def send_feedback(message_id, feedback):
    """Button callback, so a click on the newest response isn't lost on rerun."""
    message = next(m for m in st.session_state.messages if m.get("message_id") == message_id)
    try:
        feedback_response = requests.post(
            f"{API_BASE_URL}/feedback",
            json={
                "user_id": st.session_state.user_id,
                "message_id": message_id,
                "user_query": message.get("user_query", ""),
                "ai_response": message["content"],
                "feedback": feedback,
                "variation_key": message["metadata"].get("primary_variation", "unknown"),
                "model": message["metadata"].get("primary_model", "unknown"),
                "tool_calls": message["metadata"].get("tools_used", []),
                "source": "real_user",
                "user_context": get_user_context(st.session_state.user_id, sample_users),
            },
        )
        if feedback_response.status_code == 200:
            message["feedback"] = feedback
        else:
            st.error("Failed to submit feedback")
    except Exception as e:
        st.error(f"Failed to submit feedback: {e}")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message["role"] == "assistant":
            # Show feedback buttons for assistant messages
            message_id = message["message_id"]
            current_feedback = message.get("feedback")

            col1, col2, col3 = st.columns([1, 1, 8])
            with col1:
                st.button("👍", key=f"hist_thumbs_up_{message_id}", disabled=current_feedback == "positive",
                          help="Helpful response", on_click=send_feedback, args=(message_id, "positive"))

            with col2:
                st.button("👎", key=f"hist_thumbs_down_{message_id}", disabled=current_feedback == "negative",
                          help="Not helpful", on_click=send_feedback, args=(message_id, "negative"))

            # Show current feedback status
            if current_feedback:
                feedback_emoji = "👍" if current_feedback == "positive" else "👎"
                st.caption(f"Feedback: {feedback_emoji}")

            show_workflow_details(message["metadata"])

# Handle input sources
prompt = None

# Check for example query first
if st.session_state.get("example_query"):
    prompt = st.session_state.example_query

# Always show chat input - it should never disappear
user_text = st.chat_input("Ask questions about your documents or request research...")
if user_text is not None:
    user_text = user_text.strip()
    if user_text:
        # Override example query if user types something
        prompt = user_text
    else:
        st.warning("Please enter a question or pick an example query.")

if prompt:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.write(prompt)

    # Get agent response
    try:
        # Get user context for LaunchDarkly targeting
        user_context = get_user_context(st.session_state.user_id, sample_users)

        # SECURITY BOUNDARY: Send only sanitized conversation history to API
        # Raw messages (with PII) are never sent to backend - support agent isolation maintained
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={
                "user_id": st.session_state.user_id,
                "message": prompt,  # Raw current message (security agent will process)
                "user_context": user_context,
                "sanitized_conversation_history": st.session_state.sanitized_messages  # PII-free history only
            }
        )

        if response.status_code == 200:
            data = response.json()

            # SECURITY BOUNDARY: Extract sanitized messages from security agent
            # Support agent only ever sees these PII-free versions
            sanitized_user_message = prompt  # Default fallback

            # Extract redacted user message from security agent output
            for agent_config in data.get("agent_configurations") or []:
                if agent_config.get("agent_name") == "security-agent" and agent_config.get("redacted"):
                    sanitized_user_message = agent_config["redacted"]
                    break

            # Update sanitized conversation history (PII-free, for API calls)
            st.session_state.sanitized_messages.append({
                "role": "user",
                "content": sanitized_user_message  # Redacted version only
            })
            st.session_state.sanitized_messages.append({
                "role": "assistant",
                "content": data["response"]
            })

            # Add assistant message with all agent configurations
            metadata = {
                "primary_variation": data["variation_key"],
                "primary_model": data["model"],
                "tools_used": data["tool_calls"],
                "console_logs": data.get("console_logs", []),
                "agent_configurations": data.get("agent_configurations") or []
            }

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

                # Show feedback options
                st.markdown("**Was this response helpful?**")
                col1, col2, col3 = st.columns([1, 1, 8])

                with col1:
                    st.button("👍 Helpful", key=f"new_thumbs_up_{message_id}", help="This response was helpful",
                              on_click=send_feedback, args=(message_id, "positive"))

                with col2:
                    st.button("👎 Not helpful", key=f"new_thumbs_down_{message_id}", help="This response was not helpful",
                              on_click=send_feedback, args=(message_id, "negative"))

                show_workflow_details(metadata)

            # Clear example query only after successful processing to avoid losing it on reruns
            if st.session_state.get("example_query") == prompt:
                del st.session_state.example_query
        else:
            st.error(f"Error: {response.status_code}")

    except Exception as e:
        st.error(f"Connection error: {e}")

# Sidebar for user settings
with st.sidebar:
    st.header("Context")

    user_options = [user['id'] for user in sample_users]
    selected_user_id = st.selectbox("User ID", user_options, index=user_options.index("user_other_paid_001"),
                                   help="Different User IDs may receive different AI configurations via LaunchDarkly")

    # Show user context for selected user
    user_context = get_user_context(selected_user_id, sample_users)
    st.caption(f"Context: {user_context['country']} {user_context['plan']} user")

    if selected_user_id != st.session_state.user_id:
        st.session_state.user_id = selected_user_id
        # Clear both message histories when switching users
        st.session_state.messages = []
        st.session_state.sanitized_messages = []
        st.rerun()

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.sanitized_messages = []
        st.rerun()
