import { useState, useRef, useEffect } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import "./App.css";

const API = "https://argus-research-system.onrender.com";

const MODELS = [
  { label: "Groq — Llama 3.3 70B  ✦ Recommended", value: "Groq — Llama 3.3 70B",   free: true  },
  { label: "Gemini — 2.0 Flash",                   value: "Gemini — 2.0 Flash",      free: false },
  { label: "Cerebras — Llama 3.1 8B",              value: "Cerebras — Llama 3.1 8B", free: false },
  { label: "Local — Ollama Llama 3",               value: "Local — Ollama Llama 3",  free: false },
  { label: "Local — Qwen 2.5 7B",                  value: "Local — Qwen 2.5 7B",     free: false },
  { label: "Local — Qwen 3.5",                     value: "Local — Qwen 3.5",         free: false },
];

const STAGES = [
  { id: "search",   label: "Search Agent",    sub: "Tavily web search",    icon: "01" },
  { id: "scrape",   label: "Reader Agent",    sub: "URL content scraper",  icon: "02" },
  { id: "write",    label: "Writer Chain",    sub: "Report generation",    icon: "03" },
  { id: "critic",   label: "Critic Chain",    sub: "Quality evaluation",   icon: "04" },
  { id: "followup", label: "Follow-up Chain", sub: "Research questions",   icon: "05" },
];

const SAMPLE_TOPICS = [
  "Future of AGI",
  "Quantum Computing",
  "AI in Cybersecurity",
  "Climate Technologies",
  "Space Colonisation",
];


export default function App() {
  const [topic, setTopic]         = useState("");
  const [model, setModel]         = useState(MODELS[0].value);
  const [apiKey, setApiKey]       = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [status, setStatus]       = useState("idle"); // idle | waking | running | done | error
  const [activeStage, setActive]  = useState(-1);
  const [doneStages, setDone]     = useState([]);
  const [progress, setProgress]   = useState(0);
  const [result, setResult]       = useState(null);
  const [error, setError]         = useState("");
  const [sidebarOpen, setSidebar] = useState(true);
  const [activeTab, setTab]       = useState("report");
  const [logs, setLogs]           = useState([]);
  const [copied, setCopied]       = useState(false);
  const reportRef                 = useRef(null);

  // Ping backend on page load to start Render cold boot early
  useEffect(() => {
    axios.get(`${API}/`, { timeout: 5000 }).catch(() => {});
  }, []);

  const addLog = (msg, type = "info") => {
    const ts = new Date().toLocaleTimeString("en-US", { hour12: false });
    setLogs(l => [...l, { msg, type, ts }]);
  };

  const run = async () => {
    if (!topic.trim()) return;
    setStatus("running");
    setActive(-1);
    setDone([]);
    setProgress(0);
    setResult(null);
    setError("");
    setLogs([]);
    setTab("report");

    addLog("Pipeline initialised", "system");
    addLog(`Model: ${model}`, "system");
    addLog(`Topic: ${topic}`, "system");

    // After 40s with no response, assume server was sleeping and update the log
    const wakeNotice = setTimeout(() => {
      addLog("Server is waking up (free tier cold start ~60s)...", "info");
      setProgress(8);
    }, 40000);

    try {
      setStatus("waking");
      addLog("Connecting to server...", "system");
      setProgress(3);

      const res = await axios.post(`${API}/research`, {
        topic,
        model,
        api_key: apiKey || null,
      }, { timeout: 300000 });

      clearTimeout(wakeNotice);
      setStatus("running");
      setActive(0);
      addLog("Server ready — pipeline running", "agent");
      addLog("Search Agent activated", "agent");
      setProgress(5);

      // Animate stage progression for UX
      setDone([0]); setActive(1); setProgress(20);
      addLog("Search complete — sources found", "success");
      addLog("Reader Agent activated", "agent");
      addLog("Selecting top URL for scraping...", "info");

      await delay(500);
      setDone([0,1]); setActive(2); setProgress(40);
      addLog("Scraping complete", "success");
      addLog("Writer Chain activated", "agent");
      addLog("Generating structured report...", "info");

      await delay(500);
      setDone([0,1,2]); setActive(3); setProgress(60);
      addLog("Report generated", "success");
      addLog("Critic Chain activated", "agent");
      addLog("Evaluating report quality...", "info");

      await delay(400);
      setDone([0,1,2,3]); setActive(4); setProgress(80);
      addLog("Critic evaluation complete", "success");
      addLog("Follow-up Chain activated", "agent");
      addLog("Generating research questions...", "info");

      await delay(400);
      setDone([0,1,2,3,4]); setActive(-1); setProgress(100);
      addLog("Follow-up questions ready", "success");
      addLog("Pipeline finished ✓", "system");

      setResult(res.data);
      setStatus("done");
    } catch (e) {
      clearTimeout(wakeNotice);
      let msg;
      if (e.code === "ECONNABORTED" || e.message?.includes("timeout")) {
        msg = "Request timed out. The pipeline took too long — try a shorter or more specific topic.";
      } else if (!e.response) {
        msg = "Server unavailable. Check that the API keys are set on Render, then try again.";
      } else if (e.response.status === 504) {
        msg = e.response.data?.detail || "Pipeline timed out on the server.";
      } else {
        msg = e.response?.data?.detail || e.message || "Unknown error";
      }
      setError(msg);
      setStatus("error");
      addLog(`Error: ${msg}`, "error");
    }
  };

  const delay = ms => new Promise(r => setTimeout(r, ms));

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const parseFollowupQuestions = (text) => {
    if (!text) return [];
    return text
      .split('\n')
      .map(l => l.trim())
      .filter(l => /^\d+[\.\)]/.test(l))
      .map(l => l.replace(/^\d+[\.\)]\s*/, '').trim())
      .filter(Boolean);
  };

  const downloadFile = (content, filename) => {
    const blob = new Blob([content], { type: "text/plain" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  const now = new Date();
  const dateStr = now.toLocaleDateString("en-GB", { weekday:"long", day:"2-digit", month:"long", year:"numeric" });

  return (
    <div className="app">

      {/* ── TOP BAR ─────────────────────────────────────────── */}
      <header className="topbar">
        <div className="topbar-left">
          <button className="sidebar-toggle" onClick={() => setSidebar(s => !s)}>
            <span /><span /><span />
          </button>
          <div className="topbar-logo">
            <span className="topbar-logo-dot" />
            <span className="topbar-logo-name">ARGUS</span>
            <span className="topbar-logo-sub">Research</span>
          </div>
        </div>
        <div className="topbar-center">
          <div className={`sys-health ${(status === "running" || status === "waking") ? "pulse" : ""}`}>
            <span className={`health-dot ${status === "error" ? "red" : status === "done" ? "green" : (status === "running" || status === "waking") ? "amber" : "dim"}`} />
            {status === "idle"    && "SYSTEM READY"}
            {status === "waking"  && "WAKING SERVER"}
            {status === "running" && "PIPELINE RUNNING"}
            {status === "done"    && "COMPLETE"}
            {status === "error"   && "ERROR"}
          </div>
        </div>
        <div className="topbar-right">
          <span className="topbar-date">{dateStr}</span>
        </div>
      </header>

      <div className="layout">

        {/* ── SIDEBAR ───────────────────────────────────────── */}
        <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>

          <div className="sb-block">
            <div className="sb-label">Model</div>
            <select
              className="sb-select"
              value={model}
              onChange={e => setModel(e.target.value)}
            >
              {MODELS.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          <div className="sb-block">
            {model.startsWith("Local") ? (
              <div className="sb-caption">Ollama must be running on localhost:11434</div>
            ) : (
              <>
                {MODELS.find(m => m.value === model)?.free && (
                  <div className="sb-free-badge">✓ Free — no key required</div>
                )}
                <button
                  className="sb-toggle-link"
                  style={{ marginTop: MODELS.find(m => m.value === model)?.free ? "0.5rem" : "0" }}
                  onClick={() => setShowApiKey(s => !s)}
                >
                  {showApiKey ? "▾ Hide API key" : "▸ Use your own API key"}
                </button>
                {showApiKey && (
                  <>
                    <input
                      className="sb-input"
                      type="password"
                      placeholder="Paste your Groq / Gemini key..."
                      value={apiKey}
                      onChange={e => setApiKey(e.target.value)}
                      style={{ marginTop: "0.5rem" }}
                    />
                    <div className="sb-caption">Your key overrides the default. Get one free at console.groq.com</div>
                  </>
                )}
              </>
            )}
          </div>

          <div className="sb-block">
            <div className="sb-label">Pipeline Stages</div>
            <div className="stage-tracker">
              {STAGES.map((s, i) => {
                const isDone   = doneStages.includes(i);
                const isActive = activeStage === i;
                return (
                  <div key={s.id} className={`tracker-row ${isDone ? "done" : isActive ? "active" : ""}`}>
                    <div className={`tracker-dot ${isDone ? "done" : isActive ? "active" : ""}`} />
                    <div className="tracker-info">
                      <div className="tracker-name">{s.icon} · {s.label}</div>
                      <div className="tracker-sub">{s.sub}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="sb-block">
            <div className="sb-label">Quick Topics</div>
            <div className="topic-list">
              {SAMPLE_TOPICS.map(t => (
                <div
                  key={t}
                  className="topic-item"
                  onClick={() => setTopic(t)}
                >
                  → {t}
                </div>
              ))}
            </div>
          </div>

          <div className="sb-block sb-stack">
            <div className="sb-label">Stack</div>
            <div className="stack-tags">
              {["Tavily","BeautifulSoup","LangGraph","LangChain","Groq","FastAPI","React"].map(t => (
                <span key={t} className="stack-tag">{t}</span>
              ))}
            </div>
          </div>

          <div className="sb-credit">
            <span className="sb-credit-label">Developed by</span>
            <span className="sb-credit-name">Satyam Kamboj</span>
          </div>

        </aside>

        {/* ── MAIN ──────────────────────────────────────────── */}
        <main className="main">

          {/* Masthead — Sentinel AI style */}
          <div className="masthead">
            <div className="masthead-eyebrow">Multi-Agent Research Intelligence</div>
            <h1 className="masthead-title">
              ARGUS<em> RESEARCH</em>
            </h1>
            <p className="masthead-sub">Deep research, on demand.</p>
            <p className="masthead-desc">
              Enter any topic. ARGUS dispatches a multi-agent pipeline — live web search,
              source scraping, structured writing, and quality critique — delivering a
              comprehensive report in minutes, not hours.
            </p>
          </div>

          {/* Progress bar */}
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>

          {/* Input */}
          <div className="input-section">
            <div className="input-label-row">
              <span className="field-label">Research Topic</span>
              {status === "waking"  && <span className="running-badge">● WAKING UP</span>}
              {status === "running" && <span className="running-badge">● RUNNING</span>}
            </div>
            <div className="input-row">
              <input
                className="topic-input"
                type="text"
                placeholder="Enter any topic — e.g. The geopolitics of rare earth minerals..."
                value={topic}
                onChange={e => setTopic(e.target.value)}
                onKeyDown={e => e.key === "Enter" && status !== "running" && status !== "waking" && run()}
                disabled={status === "running" || status === "waking"}
              />
              <button
                className={`run-btn ${(status === "running" || status === "waking") ? "loading" : ""}`}
                onClick={run}
                disabled={status === "running" || status === "waking" || !topic.trim()}
              >
                {status === "waking"  ? (<><span className="spinner" /> Waking up…</>) :
                 status === "running" ? (<><span className="spinner" /> Running…</>) :
                 "Run Research →"}
              </button>
            </div>
            {error && <div className="error-bar">✕ {error}</div>}
          </div>

          {/* Results */}
          {result && (
            <div className="results">

              {/* Done strip */}
              <div className="done-strip">
                <span className="done-left">Research complete — all 5 stages finished</span>
                <span className="done-right">{new Date().toLocaleTimeString()} · {model}</span>
              </div>

              {/* Tabs */}
              <div className="tabs">
                {[
                  { id: "report",   label: "Report"          },
                  { id: "followup", label: "Follow-up"        },
                  { id: "critic",   label: "Critic"           },
                  { id: "sources",  label: "Sources"          },
                  { id: "scraped",  label: "Scraped"          },
                ].map(t => (
                  <button
                    key={t.id}
                    className={`tab ${activeTab === t.id ? "active" : ""}`}
                    onClick={() => setTab(t.id)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              <div className="tab-content" ref={reportRef}>
                {activeTab === "report" && (
                  <div className="report-card">
                    <div className="report-card-header">
                      <span className="report-kicker">Research Report · {result.topic}</span>
                      <button
                        className={`copy-btn ${copied ? "copied" : ""}`}
                        onClick={() => copyToClipboard(result.report)}
                      >
                        {copied ? "✓ Copied" : "Copy"}
                      </button>
                    </div>
                    <div className="report-body">
                      <ReactMarkdown>{result.report}</ReactMarkdown>
                    </div>
                  </div>
                )}
                {activeTab === "followup" && (
                  <div className="followup-card">
                    <div className="followup-header">
                      5 Follow-up Research Questions
                    </div>
                    {parseFollowupQuestions(result.followup_questions).length > 0 ? (
                      <>
                        {parseFollowupQuestions(result.followup_questions).map((q, i) => (
                          <div
                            key={i}
                            className="followup-item"
                            onClick={() => { setTopic(q); setResult(null); setStatus("idle"); }}
                          >
                            <span className="followup-num">{i + 1}</span>
                            <span className="followup-q">{q}</span>
                            <span className="followup-arrow">→</span>
                          </div>
                        ))}
                        <div className="followup-hint">Click any question to research it</div>
                      </>
                    ) : (
                      <pre className="raw-body" style={{ padding: "1.5rem" }}>{result.followup_questions}</pre>
                    )}
                  </div>
                )}
                {activeTab === "critic" && (
                  <div className="critic-card">
                    <pre className="critic-body">{result.feedback}</pre>
                  </div>
                )}
                {activeTab === "sources" && (
                  <div className="raw-card">
                    <pre className="raw-body">{result.search_results}</pre>
                  </div>
                )}
                {activeTab === "scraped" && (
                  <div className="raw-card">
                    <pre className="raw-body">{result.scraped_content}</pre>
                  </div>
                )}
              </div>

              {/* Export */}
              <div className="export-row">
                <div className="export-label">Export</div>
                <div className="export-btns">
                  <button className="export-btn" onClick={() => downloadFile(
                    `TOPIC: ${result.topic}\n\n${"=".repeat(60)}\n\nREPORT:\n${result.report}\n\n${"=".repeat(60)}\n\nCRITIC:\n${result.feedback}\n\n${"=".repeat(60)}\n\nSOURCES:\n${result.search_results}`,
                    `argus_full_${result.topic.slice(0,20).replace(/ /g,"_")}.txt`
                  )}>↓ Full Report</button>
                  <button className="export-btn" onClick={() => downloadFile(
                    result.report,
                    `argus_report_${result.topic.slice(0,20).replace(/ /g,"_")}.txt`
                  )}>↓ Report Only</button>
                  <button className="export-btn" onClick={() => downloadFile(
                    result.feedback,
                    `argus_critic_${result.topic.slice(0,20).replace(/ /g,"_")}.txt`
                  )}>↓ Critic Only</button>
                </div>
              </div>

            </div>
          )}

        </main>

        {/* ── AGENT LOG DRAWER ──────────────────────────────── */}
        <aside className="log-drawer">
          <div className="log-header">
            <span className="log-title">AGENT LOG</span>
            <span className="log-count">{logs.length}</span>
          </div>
          <div className="log-feed">
            {logs.length === 0 && (
              <div className="log-empty">Waiting for pipeline...</div>
            )}
            {logs.map((l, i) => (
              <div key={i} className={`log-entry log-${l.type}`}>
                <span className="log-ts">{l.ts}</span>
                <span className="log-msg">{l.msg}</span>
              </div>
            ))}
          </div>
        </aside>

      </div>
    </div>
  );
}