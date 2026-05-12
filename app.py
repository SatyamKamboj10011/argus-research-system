# //ONLY WHEN USING STREAMLIT FOR THE FRONTEND. NOT A TRUE BACKEND SERVER.


import streamlit as st
from agents import get_llm, build_search_agent, build_read_agent, build_writer_chain, build_critic_chain
from datetime import datetime

st.set_page_config(
    page_title="ARGUS — Research Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── DESIGN SYSTEM ─────────────────────────────────────────────────────────────
# Aesthetic: Brutalist editorial. Hard edges. Print grid. Amber accent.
# Fonts: Playfair Display (editorial) + JetBrains Mono (terminal)
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400;1,700&family=JetBrains+Mono:wght@300;400;500;700&family=Barlow:wght@300;400;500;600&display=swap');

/* ── Reset & Base ── */
:root {
    --ink:      #0A0A08;
    --paper:    #111110;
    --surface:  #161614;
    --rule:     #262622;
    --rule-hi:  #3A3A34;
    --text:     #E8E6DF;
    --muted:    #5C5C54;
    --amber:    #E8A020;
    --amber-lo: rgba(232,160,32,0.08);
    --amber-md: rgba(232,160,32,0.18);
    --red:      #D94F3D;
    --green:    #4CA66B;
    --blue:     #4A8FD4;
}

html, body, [class*="css"], .stApp {
    font-family: 'Barlow', sans-serif !important;
    background: var(--ink) !important;
    color: var(--text) !important;
}

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 2rem 4rem !important; max-width: 100% !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--paper) !important;
    border-right: 1px solid var(--rule) !important;
    padding-top: 0 !important;
}
[data-testid="stSidebar"] > div { padding: 0 !important; }
[data-testid="stSidebar"] * { color: var(--text) !important; }

.sb-masthead {
    border-bottom: 1px solid var(--rule);
    padding: 1.5rem 1.4rem 1.2rem;
    margin-bottom: 0;
}

.sb-logo {
    font-family: 'Playfair Display', serif;
    font-size: 1.5rem;
    font-weight: 900;
    letter-spacing: -0.02em;
    color: var(--text) !important;
    line-height: 1;
    margin-bottom: 0.25rem;
}

.sb-tagline {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: var(--muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.14em;
}

.sb-section {
    padding: 1.2rem 1.4rem;
    border-bottom: 1px solid var(--rule);
}

.sb-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--muted) !important;
    margin-bottom: 0.6rem;
    display: block;
}

.sb-model-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: var(--amber-lo);
    border: 1px solid rgba(232,160,32,0.25);
    color: var(--amber) !important;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    padding: 0.3rem 0.7rem;
    margin-bottom: 0.8rem;
    letter-spacing: 0.04em;
}

.topic-list { list-style: none; padding: 0; margin: 0; }
.topic-list li {
    font-size: 0.8rem;
    color: var(--muted) !important;
    padding: 0.3rem 0;
    border-bottom: 1px solid var(--rule);
    cursor: default;
    font-family: 'Barlow', sans-serif;
    font-weight: 300;
    transition: color 0.1s;
}
.topic-list li:last-child { border-bottom: none; }
.topic-list li::before { content: "→ "; color: var(--amber); font-size: 0.7rem; }

/* ── Selectbox ── */
.stSelectbox label { display: none !important; }
.stSelectbox > div > div {
    background: var(--surface) !important;
    border: 1px solid var(--rule-hi) !important;
    border-radius: 0 !important;
    color: var(--text) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
}
.stSelectbox > div > div:focus-within {
    border-color: var(--amber) !important;
    box-shadow: none !important;
}

/* ── Text inputs ── */
.stTextInput label { display: none !important; }
.stTextInput > div > div > input {
    background: var(--surface) !important;
    border: 1px solid var(--rule-hi) !important;
    border-radius: 0 !important;
    color: var(--text) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
    padding: 0.75rem 1rem !important;
    transition: border-color 0.1s !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--amber) !important;
    box-shadow: 2px 2px 0 var(--amber-lo) !important;
    outline: none !important;
}
.stTextInput > div > div > input::placeholder { color: var(--muted) !important; }

/* ── Button ── */
.stButton > button {
    background: var(--amber) !important;
    color: var(--ink) !important;
    border: 2px solid var(--amber) !important;
    border-radius: 0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    padding: 0.7rem 1.5rem !important;
    width: 100% !important;
    transition: all 0.1s !important;
}
.stButton > button:hover {
    background: transparent !important;
    color: var(--amber) !important;
}

/* ── Download button ── */
.stDownloadButton > button {
    background: transparent !important;
    border: 1px solid var(--rule-hi) !important;
    border-radius: 0 !important;
    color: var(--muted) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    width: 100% !important;
    transition: all 0.1s !important;
}
.stDownloadButton > button:hover {
    border-color: var(--amber) !important;
    color: var(--amber) !important;
}

/* ── Progress ── */
.stProgress { margin: 0 !important; }
.stProgress > div {
    background: var(--rule) !important;
    border-radius: 0 !important;
    height: 2px !important;
}
.stProgress > div > div > div {
    background: var(--amber) !important;
    border-radius: 0 !important;
    transition: width 0.4s ease !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--rule) !important;
    border-radius: 0 !important;
}
[data-testid="stExpander"] summary {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--muted) !important;
}

/* ── Page masthead ── */
.page-masthead {
    border-bottom: 3px solid var(--text);
    padding: 2rem 0 1rem;
    margin-bottom: 0;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
}

.masthead-left {}

.masthead-vol {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--muted);
    margin-bottom: 0.3rem;
}

.masthead-title {
    font-family: 'Playfair Display', serif;
    font-size: clamp(2.4rem, 5vw, 4.2rem);
    font-weight: 900;
    line-height: 0.95;
    letter-spacing: -0.03em;
    color: var(--text);
    margin: 0;
}

.masthead-title em {
    font-style: italic;
    color: var(--amber);
}

.masthead-right {
    text-align: right;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: var(--muted);
    line-height: 1.8;
    padding-bottom: 0.2rem;
}

/* ── Ruled divider ── */
.rule-double {
    border: none;
    border-top: 3px double var(--rule-hi);
    margin: 0;
}

.rule-single {
    border: none;
    border-top: 1px solid var(--rule);
    margin: 1.5rem 0;
}

/* ── Input row ── */
.input-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--muted);
    margin-bottom: 0.4rem;
    display: block;
}

/* ── Stage tracker ── */
.tracker {
    display: flex;
    flex-direction: column;
    gap: 0;
    position: sticky;
    top: 2rem;
}

.tracker-step {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.9rem 0;
    border-bottom: 1px solid var(--rule);
    position: relative;
}

.tracker-step:last-child { border-bottom: none; }

.tracker-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: var(--muted);
    min-width: 1.2rem;
    padding-top: 0.1rem;
}

.tracker-info {}

.tracker-name {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin-bottom: 0.15rem;
}

.tracker-name.active { color: var(--amber); }
.tracker-name.done   { color: var(--green); }

.tracker-sub {
    font-size: 0.7rem;
    color: var(--muted);
    font-family: 'Barlow', sans-serif;
    font-weight: 300;
}

.tracker-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--rule-hi);
    margin-top: 0.35rem;
    flex-shrink: 0;
}

.tracker-dot.active { background: var(--amber); box-shadow: 0 0 6px var(--amber); }
.tracker-dot.done   { background: var(--green); }

/* ── Stage cards ── */
.stage-card {
    border: 1px solid var(--rule);
    background: var(--surface);
    margin-bottom: 1px;
    overflow: hidden;
}

.stage-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1.2rem;
    border-bottom: 1px solid var(--rule);
    background: var(--paper);
}

.stage-card-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--muted);
}

.stage-card-title.s-search { color: var(--blue); }
.stage-card-title.s-scrape { color: var(--green); }
.stage-card-title.s-writer { color: var(--amber); }
.stage-card-title.s-critic { color: var(--red); }

.stage-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 0.2rem 0.6rem;
    border: 1px solid var(--rule-hi);
    color: var(--muted);
}

.stage-pill.running {
    border-color: var(--amber);
    color: var(--amber);
    background: var(--amber-lo);
}

.stage-pill.done {
    border-color: rgba(76,166,107,0.4);
    color: var(--green);
    background: rgba(76,166,107,0.06);
}

.stage-body {
    padding: 1rem 1.2rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    line-height: 1.7;
    color: var(--muted);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 200px;
    overflow-y: auto;
}

.stage-body::-webkit-scrollbar { width: 3px; }
.stage-body::-webkit-scrollbar-thumb { background: var(--rule-hi); }

/* ── Report section ── */
.report-header {
    border-top: 3px solid var(--text);
    border-bottom: 1px solid var(--rule);
    padding: 1rem 0;
    margin-bottom: 0;
    display: flex;
    align-items: baseline;
    gap: 1.5rem;
}

.report-kicker {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--amber);
}

.report-slug {
    font-family: 'Playfair Display', serif;
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--text);
    font-style: italic;
}

.report-card {
    border: 1px solid var(--rule);
    background: var(--surface);
    padding: 2rem 2.2rem;
    margin-bottom: 1px;
}

.report-body {
    font-family: 'Barlow', sans-serif;
    font-size: 0.95rem;
    font-weight: 300;
    line-height: 1.9;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-word;
    column-gap: 2rem;
}

.critic-card {
    border: 1px solid rgba(217,79,61,0.3);
    background: var(--surface);
    padding: 2rem 2.2rem;
    position: relative;
}

.critic-card::before {
    content: 'CRITIC';
    position: absolute;
    top: -0.6rem;
    left: 1.2rem;
    background: var(--surface);
    padding: 0 0.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    letter-spacing: 0.16em;
    color: var(--red);
}

.critic-body {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    line-height: 1.8;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-word;
}

/* ── Done state ── */
.done-strip {
    border: 1px solid rgba(76,166,107,0.3);
    background: rgba(76,166,107,0.04);
    padding: 0.75rem 1.4rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 2rem;
}

.done-strip-left {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: var(--green);
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

.done-strip-right {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: var(--muted);
}

/* ── Export row ── */
.export-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.58rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--muted);
    margin-bottom: 0.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--rule);
    display: block;
}

/* ── Warning ── */
.stAlert { border-radius: 0 !important; }

/* hide stray labels ── */
.stTextInput label, .stSelectbox label { 
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.6rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
    color: var(--muted) !important;
}
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sb-masthead">
        <div class="sb-logo">ARGUS</div>
        <div class="sb-tagline">Multi-Agent Research Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    # Model config
    st.markdown('<div class="sb-section">', unsafe_allow_html=True)
    st.markdown('<span class="sb-label">Model</span>', unsafe_allow_html=True)

    model_choice = st.selectbox(
        "Select model",
        options=[
            "Groq — Llama 3.3 70B",
            "Groq — Llama 3.1 8B",
            "Gemini — 2.0 Flash",
            "Cerebras — Llama 3.3 70B",
            "Local — Ollama Llama 3",
        ]
    )

    st.markdown('<span class="sb-label" style="margin-top:0.8rem;display:block">API Key</span>', unsafe_allow_html=True)

    if model_choice == "Local — Ollama Llama 3":
        st.info("Ollama must be running on localhost:11434")
        api_key = None
    else:
        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-...",
        )
        if not api_key:
            st.caption("Falls back to .env if blank")

    st.markdown('</div>', unsafe_allow_html=True)

    # Quick topics
    st.markdown("""
    <div class="sb-section">
        <span class="sb-label">Quick Topics</span>
        <ul class="topic-list">
            <li>Future of AGI</li>
            <li>Quantum Computing</li>
            <li>AI in Cybersecurity</li>
            <li>Climate Technologies</li>
            <li>Space Colonisation</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Stack info
    st.markdown("""
    <div class="sb-section">
        <span class="sb-label">Pipeline</span>
        <span style="font-family:'JetBrains Mono',monospace;font-size:0.65rem;color:#5C5C54;line-height:2;display:block">
            Tavily Search<br>
            BeautifulSoup<br>
            LangGraph ReAct<br>
            LangChain LCEL<br>
            Groq / Gemini / Cerebras
        </span>
    </div>
    """, unsafe_allow_html=True)


# ── PAGE MASTHEAD ─────────────────────────────────────────────────────────────
now = datetime.now()
st.markdown(f"""
<div class="page-masthead">
    <div class="masthead-left">
        <div class="masthead-vol">Research Intelligence System · Vol. I</div>
        <h1 class="masthead-title">ARGUS<br><em>Research.</em></h1>
    </div>
    <div class="masthead-right">
        {now.strftime("%A, %d %B %Y")}<br>
        {now.strftime("%H:%M")} LOCAL<br>
        Multi-Agent · LCEL Pipeline<br>
        {model_choice}
    </div>
</div>
""", unsafe_allow_html=True)

# ── PROGRESS BAR (always visible, fills as pipeline runs) ────────────────────
progress_bar = st.progress(0)

# ── INPUT ROW ─────────────────────────────────────────────────────────────────
st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
st.markdown('<span class="input-label">Research Topic</span>', unsafe_allow_html=True)

col_input, col_btn = st.columns([5, 1])
with col_input:
    topic = st.text_input(
        "Research topic",
        placeholder="Enter any topic — e.g. The geopolitics of rare earth minerals...",
        label_visibility="hidden"
    )
with col_btn:
    st.markdown("<div style='height:1.55rem'></div>", unsafe_allow_html=True)
    run = st.button("◈ EXECUTE")

st.markdown('<hr class="rule-single">', unsafe_allow_html=True)


# ── PIPELINE ──────────────────────────────────────────────────────────────────
if run:
    if not topic.strip():
        st.warning("A research topic is required.")
        st.stop()

    try:
        llm = get_llm(model_choice, api_key if api_key else None)
    except Exception as e:
        st.error(f"Model initialisation failed: {e}")
        st.stop()

    # Two-column layout: tracker left, stages right
    col_track, col_main = st.columns([1, 3])

    with col_track:
        tracker = st.empty()

    def render_tracker(active: int, done: list):
        steps = [
            ("01", "Search", "Tavily web search"),
            ("02", "Scrape", "URL content reader"),
            ("03", "Write",  "Report generation"),
            ("04", "Critic", "Quality evaluation"),
        ]
        html = '<div class="tracker">'
        for i, (num, name, sub) in enumerate(steps):
            if i in done:
                cls_name = "done"
                cls_dot  = "done"
            elif i == active:
                cls_name = "active"
                cls_dot  = "active"
            else:
                cls_name = ""
                cls_dot  = ""
            html += f"""
            <div class="tracker-step">
                <div class="tracker-dot {cls_dot}"></div>
                <div class="tracker-info">
                    <div class="tracker-name {cls_name}">{num} · {name}</div>
                    <div class="tracker-sub">{sub}</div>
                </div>
            </div>"""
        html += '</div>'
        tracker.markdown(html, unsafe_allow_html=True)

    done_steps = []

    with col_main:

        # ── STEP 1: Search ────────────────────────────────────────────────────
        render_tracker(active=0, done=done_steps)
        s1 = st.empty()
        s1.markdown("""
        <div class="stage-card">
            <div class="stage-card-head">
                <span class="stage-card-title s-search">01 · Search Agent</span>
                <span class="stage-pill running">RUNNING</span>
            </div>
            <div class="stage-body">Querying Tavily for live sources...</div>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner(""):
            search_agent = build_search_agent(llm)
            search_result = search_agent.invoke({
                "messages": [("user", f"Find the latest and most relevant information on the topic: {topic}")]
            })
            search_results = search_result['messages'][-1].content

        progress_bar.progress(25)
        done_steps.append(0)
        s1.markdown(f"""
        <div class="stage-card">
            <div class="stage-card-head">
                <span class="stage-card-title s-search">01 · Search Agent</span>
                <span class="stage-pill done">DONE</span>
            </div>
            <div class="stage-body">{search_results[:700]}...</div>
        </div>
        """, unsafe_allow_html=True)

        # ── STEP 2: Scrape ────────────────────────────────────────────────────
        render_tracker(active=1, done=done_steps)
        s2 = st.empty()
        s2.markdown("""
        <div class="stage-card">
            <div class="stage-card-head">
                <span class="stage-card-title s-scrape">02 · Reader Agent</span>
                <span class="stage-pill running">RUNNING</span>
            </div>
            <div class="stage-body">Selecting top URL and scraping content...</div>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner(""):
            reader_agent = build_read_agent(llm)
            reader_result = reader_agent.invoke({
                "messages": [("user",
                    f"Based on the following search results about '{topic}', "
                    f"pick the most relevant URL and scrape it for deeper content.\n\n"
                    f"Search Results:\n{search_results[:2000]}"
                )]
            })
            scraped_content = reader_result['messages'][-1].content

        progress_bar.progress(50)
        done_steps.append(1)
        s2.markdown(f"""
        <div class="stage-card">
            <div class="stage-card-head">
                <span class="stage-card-title s-scrape">02 · Reader Agent</span>
                <span class="stage-pill done">DONE</span>
            </div>
            <div class="stage-body">{scraped_content[:700]}...</div>
        </div>
        """, unsafe_allow_html=True)

        # ── STEP 3: Write ─────────────────────────────────────────────────────
        render_tracker(active=2, done=done_steps)
        s3 = st.empty()
        s3.markdown("""
        <div class="stage-card">
            <div class="stage-card-head">
                <span class="stage-card-title s-writer">03 · Writer Chain</span>
                <span class="stage-pill running">RUNNING</span>
            </div>
            <div class="stage-body">Generating structured research report...</div>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner(""):
            writer_chain = build_writer_chain(llm)
            research_combined = (
                f"Search Results:\n{search_results}\n\n"
                f"Scraped Content:\n{scraped_content}"
            )
            report = writer_chain.invoke({"topic": topic, "research": research_combined})

        progress_bar.progress(75)
        done_steps.append(2)
        s3.markdown("""
        <div class="stage-card">
            <div class="stage-card-head">
                <span class="stage-card-title s-writer">03 · Writer Chain</span>
                <span class="stage-pill done">DONE</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── STEP 4: Critic ────────────────────────────────────────────────────
        render_tracker(active=3, done=done_steps)
        s4 = st.empty()
        s4.markdown("""
        <div class="stage-card">
            <div class="stage-card-head">
                <span class="stage-card-title s-critic">04 · Critic Chain</span>
                <span class="stage-pill running">RUNNING</span>
            </div>
            <div class="stage-body">Evaluating report quality...</div>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner(""):
            critic_chain = build_critic_chain(llm)
            feedback = critic_chain.invoke({"report": report})

        progress_bar.progress(100)
        done_steps.append(3)
        render_tracker(active=-1, done=done_steps)
        s4.markdown("""
        <div class="stage-card">
            <div class="stage-card-head">
                <span class="stage-card-title s-critic">04 · Critic Chain</span>
                <span class="stage-pill done">DONE</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── DONE STRIP ────────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%d %b %Y · %H:%M")
    st.markdown(f"""
    <div class="done-strip">
        <span class="done-strip-left">◈ Pipeline complete — all 4 stages finished</span>
        <span class="done-strip-right">{ts} · {model_choice}</span>
    </div>
    """, unsafe_allow_html=True)

    # ── REPORT OUTPUT ─────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="report-header">
        <span class="report-kicker">Research Report</span>
        <span class="report-slug">{topic[:60]}</span>
    </div>
    <div class="report-card">
        <div class="report-body">{report}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── CRITIC OUTPUT ─────────────────────────────────────────────────────────
    st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="critic-card">
        <div class="critic-body">{feedback}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── RAW DATA ──────────────────────────────────────────────────────────────
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    with st.expander("RAW · Search Results"):
        st.text(search_results)
    with st.expander("RAW · Scraped Content"):
        st.text(scraped_content)

    # ── EXPORTS ───────────────────────────────────────────────────────────────
    st.markdown('<span class="export-label">Export</span>', unsafe_allow_html=True)

    full_output = f"""ARGUS RESEARCH REPORT
Topic: {topic}
Generated: {ts}
Model: {model_choice}
{'='*60}

{report}

{'='*60}
CRITIC EVALUATION
{'='*60}

{feedback}

{'='*60}
RAW SEARCH RESULTS
{'='*60}

{search_results}

{'='*60}
RAW SCRAPED CONTENT
{'='*60}

{scraped_content}
"""
    ec1, ec2, ec3 = st.columns(3)
    slug = topic[:25].replace(' ', '_').lower()
    with ec1:
        st.download_button("↓ Full Report + Data", data=full_output,
            file_name=f"argus_{slug}_full.txt", mime="text/plain")
    with ec2:
        st.download_button("↓ Report Only", data=report,
            file_name=f"argus_{slug}_report.txt", mime="text/plain")
    with ec3:
        st.download_button("↓ Critic Feedback", data=feedback,
            file_name=f"argus_{slug}_critic.txt", mime="text/plain")