import base64
import os
from pathlib import Path
import requests
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

UI_DIR = Path(__file__).resolve().parent
ASSETS_DIR = UI_DIR / "assets"
KB_DIR = UI_DIR.parent / "kb"
ALBERT_AVATAR = ASSETS_DIR / "albert-proud.png"
USER_AVATAR = ASSETS_DIR / "avatar-user.png"
ASSISTANT_AVATAR = ASSETS_DIR / "avatar-assistant.png"
LD_WORDMARK_SVG = ASSETS_DIR / "launchdarkly-logo-white.svg"

# Clear identifiers (always redacted) plus employer, city, and role (redacted only by strict security).
SECURITY_CHECK_QUERY = (
    "My name is Jane Doe, email jane.doe@example.com. "
    "I work at Acme Corp in Berlin as a manager. "
    "Can you explain temporal-difference learning?"
)

LD_LOGO_B64 = base64.b64encode(LD_WORDMARK_SVG.read_bytes()).decode("ascii")
ALBERT_B64 = base64.b64encode(ALBERT_AVATAR.read_bytes()).decode("ascii")
KB_FILES = sorted(p.name for p in KB_DIR.glob("*.pdf"))
KB_SUMMARY = (
    f"{', '.join(KB_FILES)} (Reinforcement Learning)"
    if KB_FILES == ["SuttonBartoIPRLBook2ndEd.pdf"]
    else (", ".join(KB_FILES) if KB_FILES else "No PDFs in kb/")
)

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

# Get API and LaunchDarkly project configuration from environment
API_HOST = os.getenv('API_HOST', 'localhost')
API_PORT = os.getenv('API_PORT', '8000')
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
LD_PROJECT_KEY = os.getenv('LD_PROJECT_KEY', 'multi-agent-chatbot')
LD_APP_URL = os.getenv('LD_APP_URL', 'https://app.launchdarkly.com').rstrip('/')

st.set_page_config(
    page_title="LaunchDarkly Multi-Agent System",
    page_icon=str(ALBERT_AVATAR),
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Sora:wght@600;700&display=swap');

html, body, [class*="css"], .stApp {
    background-color: #191919;
    color: #F4F5F7;
    font-family: 'Inter', sans-serif;
}

.slide {
    margin-bottom: 1.25rem;
    border-radius: 28px;
    background:
        linear-gradient(#F8F8F8, #F8F8F8) padding-box,
        linear-gradient(100deg, #DDFF46 0%, #FF35A2 46%, #3DD6F5 100%) border-box;
    border: 14px solid transparent;
    background-origin: border-box;
    background-clip: padding-box, border-box;
    position: relative;
    overflow: hidden;
}

.slide::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background-image:
        linear-gradient(rgba(25, 25, 25, 0.16) 1px, transparent 1px),
        linear-gradient(90deg, rgba(25, 25, 25, 0.16) 1px, transparent 1px);
    background-size: 26px 26px;
    mask-image: linear-gradient(#000, transparent 72%);
    pointer-events: none;
}

.slide-body {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    background: #FFFFFF;
    border-radius: 16px 16px 0 0;
    padding: 1.6rem 1.8rem 1.2rem;
}

.eyebrow {
    display: inline-block;
    background: #DDFF46;
    color: #191919;
    font-family: 'Inter', sans-serif;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.22rem 0.45rem;
    border-radius: 2px;
    margin-bottom: 0.7rem;
}

.slide h1.header-title {
    font-family: 'Sora', sans-serif;
    font-size: 2.35rem;
    font-weight: 700;
    margin: 0 0 0.45rem;
    color: #191919 !important;
    letter-spacing: -0.03em;
    line-height: 1.05;
}

.header-subtitle {
    font-size: 1rem;
    color: #6D6E71;
    margin: 0;
    line-height: 1.45;
    max-width: 38rem;
}

.slide-albert {
    width: 168px;
    height: 168px;
    flex-shrink: 0;
    border-radius: 50%;
    background:
        radial-gradient(circle at 35% 30%, #DDFF46 0%, #DDFF46 42%, transparent 43%),
        radial-gradient(circle at 78% 72%, #FF35A2 0%, #FF35A2 36%, transparent 37%),
        #F8F8F8;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    overflow: hidden;
}

.header-mascot {
    height: 150px;
    width: auto;
}

.slide-foot {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    background: #191919;
    padding: 0.85rem 1.3rem;
    border-radius: 0 0 12px 12px;
}

.ld-wordmark {
    height: 22px;
    width: auto;
}

.kb-foot {
    color: #DDFF46;
    font-size: 0.78rem;
    font-weight: 600;
}

.queries-label {
    color: #A7A9AC;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin: 0.2rem 0 0.55rem;
}

[class*="st-key-ask-"] button {
    background: #212124;
    color: #F4F5F7;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 12px;
    text-align: left;
    padding: 0.72rem 1rem;
    font-weight: 600;
}

[class*="st-key-ask-"] button:hover {
    border-color: #DDFF46;
    color: #FFFFFF;
    background: #26262A;
}

.stButton > button {
    background: #282A30;
    color: #F4F5F7;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
}

[data-testid="stSidebar"] .stButton > button {
    background: #DDFF46;
    color: #191919;
    border: none;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background: #FFFFFF;
    color: #191919;
}

.stChatMessage {
    background: #212124;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    margin: 0.5rem 0;
}

.stChatMessage img {
    border-radius: 8px;
}

.stSelectbox > div > div {
    background: #282A30;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 6px;
    color: #F4F5F7;
}

.trace-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-top: 0.65rem;
    padding: 0.65rem 0.95rem;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 8px;
    font-size: 0.8rem;
    color: rgba(244, 245, 247, 0.8);
}

.trace-links {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 0.6rem;
}

.trace-link {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.3rem 0.7rem;
    background: rgba(64, 91, 255, 0.16);
    border: 1px solid rgba(96, 122, 255, 0.5);
    border-radius: 6px;
    color: #D8DEFF !important;
    font-weight: 500;
    text-decoration: none !important;
    transition: all 0.15s ease;
}

.trace-link:hover {
    background: #405BFF;
    border-color: #DDFF46;
    color: #FFFFFF !important;
}

.pii-note {
    margin-top: 0.45rem;
    padding: 0.45rem 0.75rem;
    background: rgba(221, 255, 70, 0.08);
    border-left: 3px solid #DDFF46;
    border-radius: 4px;
    font-size: 0.8rem;
    color: #E5E7EB;
}

@media (max-width: 768px) {
    .slide-body {
        flex-direction: column;
        align-items: flex-start;
    }
    .slide h1.header-title {
        font-size: 1.6rem;
    }
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="slide">
    <div class="slide-body">
        <div>
            <span class="eyebrow">Research demo</span>
            <h1 class="header-title">Multi-Agent Research System</h1>
            <p class="header-subtitle">A LangGraph supervisor, a PII security boundary, and hybrid RAG with live academic search.</p>
        </div>
        <div class="slide-albert">
            <img class="header-mascot" src="data:image/png;base64,{ALBERT_B64}" alt="Albert" />
        </div>
    </div>
    <div class="slide-foot">
        <img class="ld-wordmark" src="data:image/svg+xml;base64,{LD_LOGO_B64}" alt="LaunchDarkly" />
        <span class="kb-foot">{KB_SUMMARY} · ArXiv · OpenAlex</span>
    </div>
</div>
""", unsafe_allow_html=True)

def show_observability_links(metadata):
    """Render served summary, PII redaction confirmation, and direct LaunchDarkly Trace & Monitoring links."""
    import html
    from urllib.parse import quote

    agent_configurations = metadata.get("agent_configurations") or []
    support = next((a for a in agent_configurations if a.get("agent_name") == "support-agent"), {})
    security = next((a for a in agent_configurations if a.get("agent_name") == "security-agent"), {})

    variation = support.get("variation_key") or metadata.get("primary_variation", "unknown")
    model = support.get("model") or metadata.get("primary_model", "unknown")
    tools_used = support.get("tools_used") or metadata.get("tools_used") or []
    tools_summary = f" · tools: {', '.join(tools_used)}" if tools_used else ""

    trace_id = metadata.get("trace_id")
    span_id = metadata.get("span_id")
    trace_ts = metadata.get("trace_timestamp")
    if trace_id and span_id and trace_ts:
        import json as _json
        related = base64.b64encode(
            _json.dumps({"type": "trace", "id": trace_id, "timestamp": trace_ts, "spanID": span_id}).encode()
        ).decode("ascii")
        trace_url = f"{LD_APP_URL}/projects/{LD_PROJECT_KEY}/traces?query={quote(f'trace_id={trace_id}')}&related_resource={quote(related)}"
        trace_label = "↗ View Trace Waterfall"
    elif trace_id:
        query_param = quote(f"trace_id={trace_id}")
        trace_url = f"{LD_APP_URL}/projects/{LD_PROJECT_KEY}/traces?query={query_param}"
        trace_label = "↗ View Trace in LaunchDarkly"
    else:
        trace_url = f"{LD_APP_URL}/projects/{LD_PROJECT_KEY}/traces"
        trace_label = "↗ Open Traces in LaunchDarkly"

    monitoring_url = f"{LD_APP_URL}/projects/{LD_PROJECT_KEY}/ai-configs/support-agent/monitoring"

    pii_html = ""
    if security.get("detected") and security.get("redacted"):
        escaped_redacted = html.escape(security["redacted"])
        pii_types = html.escape(", ".join(security.get("types") or []))
        pii_html = f'<div class="pii-note"><strong>PII redacted ({pii_types}):</strong> {escaped_redacted}</div>'

    summary = html.escape(f"{variation} ({model}){tools_summary}")
    st.markdown(
        f"""
        {pii_html}
        <div class="trace-bar">
            <span>Served: <code>{summary}</code></span>
            <span class="trace-links">
                <a class="trace-link" href="{trace_url}" target="_blank" rel="noopener">{trace_label}</a>
                <a class="trace-link" href="{monitoring_url}" target="_blank" rel="noopener">↗ Monitoring &amp; Metrics</a>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

EXAMPLE_QUERIES = [
    ("basic", "Basic Search", "How does Q-learning differ from SARSA in your knowledge base?"),
    ("rerank", "RAG + Reranking", "In our textbook, how do multi-armed bandits balance exploration and exploitation? Search and rerank the passages."),
    ("security", "Security Check", SECURITY_CHECK_QUERY),
    ("arxiv", "ArXiv Research", "Find recent ArXiv papers on offline reinforcement learning"),
    ("openalex", "OpenAlex Research", "Search OpenAlex for highly cited papers on reinforcement learning from human feedback"),
    ("full", "Full Research Stack", "Compare how our textbook defines policy gradient methods with recent academic research papers"),
]

st.markdown('<p class="queries-label">Example queries</p>', unsafe_allow_html=True)
for start in (0, 3):
    columns = st.columns(3)
    for column, (key, title, prompt) in zip(columns, EXAMPLE_QUERIES[start:start + 3]):
        with column:
            if st.button(title, key=f"ask-{key}", use_container_width=True):
                st.session_state.example_query = prompt

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
    with st.chat_message(message["role"], avatar=str(USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATAR)):
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

            show_observability_links(message["metadata"])

# Handle input sources
prompt = None

# Check for example query first
if st.session_state.get("example_query"):
    prompt = st.session_state.example_query

# Always show chat input - it should never disappear
user_text = st.chat_input(f"Ask about {KB_SUMMARY}, test PII redaction, or search ArXiv & OpenAlex...")
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
    with st.chat_message("user", avatar=str(USER_AVATAR)):
        st.write(prompt)

    # Get agent response inside the assistant bubble so a live spinner shows immediately
    with st.chat_message("assistant", avatar=str(ASSISTANT_AVATAR)):
        try:
            user_context = get_user_context(st.session_state.user_id, sample_users)

            with st.spinner("Running multi-agent workflow (Supervisor → Security → Support + RAG/MCP tools)..."):
                # SECURITY BOUNDARY: Send only sanitized conversation history to API
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
                    "trace_id": data.get("trace_id"),
                    "span_id": data.get("span_id"),
                    "trace_timestamp": data.get("trace_timestamp"),
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

                show_observability_links(metadata)

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
