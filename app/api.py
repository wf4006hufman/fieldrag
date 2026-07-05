"""FastAPI app.  Local:  uvicorn app.api:app --reload
Swagger UI at /docs ."""
import logging

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from . import config
from . import rag

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("fieldrag.api")

app = FastAPI(title="FieldRAG", version="1.0")


HOME_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FieldRAG</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f7f9;
      --panel: #ffffff;
      --panel-soft: #f8fafc;
      --text: #17212b;
      --muted: #647383;
      --line: #d8e1ea;
      --line-strong: #bcc9d6;
      --teal: #008a91;
      --teal-dark: #00656b;
      --blue: #315fbd;
      --amber: #a86500;
      --green: #247a4d;
      --shadow: 0 18px 45px rgba(23, 33, 43, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.92), rgba(244,247,249,0.98)),
        repeating-linear-gradient(90deg, rgba(49,95,189,0.055) 0, rgba(49,95,189,0.055) 1px, transparent 1px, transparent 96px),
        repeating-linear-gradient(0deg, rgba(0,138,145,0.045) 0, rgba(0,138,145,0.045) 1px, transparent 1px, transparent 96px);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    button,
    textarea,
    input {
      font: inherit;
    }

    button {
      cursor: pointer;
    }

    .shell {
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 22px;
    }

    .topbar {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
      padding: 12px 0 22px;
    }

    .eyebrow {
      margin: 0 0 10px;
      color: var(--teal-dark);
      font-size: 12px;
      font-weight: 760;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    .header-actions {
      display: flex;
      align-items: flex-end;
      flex-direction: column;
      gap: 10px;
    }

    h1 {
      margin: 0;
      font-size: clamp(38px, 5vw, 68px);
      line-height: 0.92;
      letter-spacing: 0;
    }

    .subtitle {
      margin: 14px 0 0;
      color: var(--muted);
      font-size: 17px;
      max-width: 620px;
    }

    .system-badge {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      min-width: max-content;
      padding: 9px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.78);
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }

    .pulse {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--green);
      box-shadow: 0 0 0 4px rgba(36,122,77,0.13);
    }

    .stack-details {
      position: relative;
      width: min(100%, 300px);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,0.82);
      color: var(--muted);
      font-size: 13px;
    }

    .stack-details summary {
      list-style: none;
      cursor: pointer;
      padding: 9px 12px;
      background: transparent;
      color: var(--teal-dark);
      font-size: 13px;
      font-weight: 760;
      text-transform: none;
    }

    .stack-details summary::-webkit-details-marker {
      display: none;
    }

    .stack-details summary::after {
      content: "+";
      float: right;
      color: var(--muted);
      font-weight: 760;
    }

    .stack-details[open] summary::after {
      content: "-";
    }

    .stack-grid {
      display: grid;
      gap: 1px;
      border-top: 1px solid var(--line);
      background: var(--line);
    }

    .stack-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 9px 12px;
      background: #fff;
    }

    .stack-label {
      color: var(--muted);
      font-weight: 680;
    }

    .stack-value {
      color: var(--text);
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-weight: 760;
      text-align: right;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(320px, 0.85fr) minmax(0, 1.15fr);
      gap: 18px;
      align-items: start;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,0.9);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      background: rgba(248,250,252,0.88);
    }

    .panel-title {
      margin: 0;
      font-size: 14px;
      font-weight: 780;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    .panel-note {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }

    .query-body {
      padding: 18px;
    }

    .field-label {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    textarea {
      width: 100%;
      min-height: 168px;
      resize: vertical;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      padding: 14px 15px;
      background: #ffffff;
      color: var(--text);
      line-height: 1.48;
      outline: none;
      transition: border-color 140ms ease, box-shadow 140ms ease;
    }

    textarea:focus,
    input:focus {
      border-color: var(--teal);
      box-shadow: 0 0 0 4px rgba(0,138,145,0.12);
    }

    .api-key-group {
      margin-top: 14px;
    }

    .api-key-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 8px;
    }

    .api-key-row input {
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      padding: 0 12px;
      background: #fff;
      color: var(--text);
      outline: none;
    }

    .privacy-note {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }

    .privacy-note a {
      color: var(--teal-dark);
      font-weight: 720;
      text-decoration: none;
    }

    .privacy-note a:hover {
      text-decoration: underline;
    }

    .controls {
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 10px;
      align-items: center;
      margin-top: 14px;
    }

    .segmented {
      display: grid;
      grid-template-columns: 1fr 1fr;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      overflow: hidden;
      background: #fff;
    }

    .segmented button {
      min-height: 42px;
      border: 0;
      border-right: 1px solid var(--line);
      background: transparent;
      color: var(--muted);
      font-weight: 740;
    }

    .segmented button:last-child {
      border-right: 0;
    }

    .segmented button.active {
      background: #e7f6f6;
      color: var(--teal-dark);
    }

    .top-k {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 42px;
      padding: 0 10px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background: #fff;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }

    .top-k input {
      width: 52px;
      border: 0;
      border-left: 1px solid var(--line);
      padding: 4px 0 4px 10px;
      color: var(--text);
      outline: none;
    }

    .primary {
      min-height: 42px;
      border: 1px solid var(--teal-dark);
      border-radius: 8px;
      padding: 0 18px;
      background: var(--teal);
      color: #fff;
      font-weight: 780;
      box-shadow: 0 10px 20px rgba(0,101,107,0.18);
    }

    .primary:hover {
      background: var(--teal-dark);
    }

    .primary:disabled {
      cursor: wait;
      opacity: 0.68;
    }

    .samples {
      display: grid;
      gap: 8px;
      margin-top: 16px;
    }

    .sample-button {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 11px;
      background: var(--panel-soft);
      color: #304050;
      text-align: left;
      line-height: 1.35;
    }

    .sample-button:hover {
      border-color: var(--line-strong);
      background: #eef4f8;
    }

    .mode-help {
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .response-body {
      min-height: 520px;
      padding: 18px;
    }

    .status-line {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 13px;
    }

    .mode-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
      background: var(--panel-soft);
      color: var(--muted);
      font-weight: 720;
    }

    .empty-state {
      display: grid;
      place-items: center;
      min-height: 412px;
      border: 1px dashed var(--line-strong);
      border-radius: 8px;
      background: rgba(248,250,252,0.72);
      text-align: center;
      padding: 34px;
    }

    .empty-state h2 {
      margin: 0 0 10px;
      font-size: 24px;
      letter-spacing: 0;
    }

    .empty-state p {
      margin: 0;
      max-width: 470px;
      color: var(--muted);
      line-height: 1.55;
    }

    .section {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }

    .section + .section {
      margin-top: 12px;
    }

    .section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-soft);
      color: #2c3947;
      font-size: 13px;
      font-weight: 780;
      text-transform: uppercase;
    }

    .answer {
      padding: 16px;
      white-space: pre-wrap;
      line-height: 1.62;
      color: #1d2a36;
    }

    .source-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 14px;
    }

    .source-chip {
      max-width: 100%;
      border: 1px solid rgba(49,95,189,0.24);
      border-radius: 999px;
      padding: 7px 10px;
      background: rgba(49,95,189,0.08);
      color: var(--blue);
      font-size: 13px;
      font-weight: 720;
      overflow-wrap: anywhere;
    }

    .diagnostics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      background: var(--line);
    }

    .metric {
      min-height: 82px;
      padding: 13px;
      background: #fff;
    }

    .metric-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      text-transform: uppercase;
    }

    .metric-value {
      margin-top: 8px;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 15px;
      color: var(--text);
      overflow-wrap: anywhere;
    }

    details {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      margin-top: 12px;
      overflow: hidden;
    }

    summary {
      cursor: pointer;
      padding: 12px 14px;
      background: var(--panel-soft);
      color: #2c3947;
      font-size: 13px;
      font-weight: 780;
      text-transform: uppercase;
    }

    pre {
      margin: 0;
      max-height: 320px;
      overflow: auto;
      padding: 14px;
      background: #101820;
      color: #d6edf0;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      line-height: 1.55;
    }

    .error {
      border-color: rgba(168,101,0,0.34);
      background: #fff8ed;
      color: var(--amber);
    }

    .footer {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
      color: var(--muted);
      font-size: 13px;
    }

    .footer span {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }

    @media (max-width: 860px) {
      .topbar {
        align-items: flex-start;
        flex-direction: column;
      }

      .header-actions {
        align-items: stretch;
        width: 100%;
      }

      .stack-details {
        width: 100%;
      }

      .workspace {
        grid-template-columns: 1fr;
      }

      .controls {
        grid-template-columns: 1fr;
      }

      .top-k {
        justify-content: space-between;
      }

      .primary {
        width: 100%;
      }

      .diagnostics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 520px) {
      .shell {
        width: min(100vw - 20px, 1180px);
        padding-top: 16px;
      }

      h1 {
        font-size: 42px;
      }

      .panel-header {
        align-items: flex-start;
        flex-direction: column;
      }

      .diagnostics {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div>
        <h1>FieldRAG</h1>
        <p class="subtitle">Grounded NGS Support Assistant</p>
      </div>
      <div class="header-actions">
        <div class="system-badge" aria-label="System status">
          <span class="pulse" aria-hidden="true"></span>
          Local API Ready
        </div>
        <details class="stack-details">
          <summary>More info...</summary>
          <div class="stack-grid">
            <div class="stack-item">
              <span class="stack-label">Pipeline</span>
              <span class="stack-value">RAG</span>
            </div>
            <div class="stack-item">
              <span class="stack-label">Vector type</span>
              <span class="stack-value">pgvector</span>
            </div>
            <div class="stack-item">
              <span class="stack-label">Model</span>
              <span class="stack-value">Gemini 2.5 Pro</span>
            </div>
          </div>
        </details>
      </div>
    </header>

    <main class="workspace">
      <section class="panel" aria-labelledby="query-title">
        <div class="panel-header">
          <div>
            <h2 class="panel-title" id="query-title">Query Console</h2>
            <p class="panel-note">Ask against curated public technical documents.</p>
          </div>
        </div>
        <div class="query-body">
          <label class="field-label" for="question">Question</label>
          <textarea id="question" placeholder="Ask about DRAGEN, Nextflow, nf-core, samtools, bcftools, or NGS QC evidence..."></textarea>

          <div class="api-key-group">
            <label class="field-label" for="apiKey">Personal Gemini API key</label>
            <div class="api-key-row">
              <input id="apiKey" type="password" placeholder="Required for free-tier RAG" autocomplete="off" spellcheck="false" />
            </div>
            <p class="privacy-note">
              Required for Gemini API free-tier mode. Used only for this request and never stored or logged by FieldRAG. Use a restricted Gemini API key from
              <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer">Google AI Studio</a>.
            </p>
          </div>

          <div class="controls" aria-label="Query controls">
            <div class="segmented" aria-label="Mode">
              <button type="button" class="active" data-mode="rag">RAG</button>
              <button type="button" data-mode="agent">Agent</button>
            </div>

            <label class="top-k" for="topK">
              Top K
              <input id="topK" type="number" min="1" max="10" value="5" />
            </label>

            <button class="primary" id="askButton" type="button">Ask</button>
          </div>
          <p class="mode-help" id="modeHelp">RAG performs one retrieval pass and one grounded generation call.</p>

          <div class="samples" aria-label="Sample questions">
            <button class="sample-button" type="button">How to filter records in a specific condition from a VCF file using bcftools?</button>
            <button class="sample-button" type="button">Why does a high duplicate rate matter?</button>
            <button class="sample-button" type="button">How to run DRAGEN WGS Germline in a DRAGEN server?</button>
          </div>
        </div>
      </section>

      <section class="panel" aria-labelledby="response-title">
        <div class="panel-header">
          <div>
            <h2 class="panel-title" id="response-title">Evidence Workspace</h2>
            <p class="panel-note">Answer, citations, and retrieval diagnostics.</p>
          </div>
        </div>
        <div class="response-body">
          <div class="status-line">
            <span id="statusText">Waiting for a question.</span>
            <span class="mode-chip" id="modeChip">Mode: RAG</span>
          </div>

          <div class="empty-state" id="emptyState">
            <div>
              <h2>Ready for evidence retrieval.</h2>
              <p>Submit a question to retrieve relevant passages, generate a grounded answer, and inspect the operational signals behind the response.</p>
            </div>
          </div>

          <div id="result" hidden>
            <section class="section" id="answerSection">
              <div class="section-title">
                <span>Answer</span>
              </div>
              <div class="answer" id="answerText"></div>
            </section>

            <section class="section">
              <div class="section-title">
                <span>Sources</span>
                <span id="sourceCount">0</span>
              </div>
              <div class="source-list" id="sources"></div>
            </section>

            <section class="section">
              <div class="section-title">
                <span>Diagnostics</span>
              </div>
              <div class="diagnostics">
                <div class="metric">
                  <div class="metric-label">Mode</div>
                  <div class="metric-value" id="metricMode">rag</div>
                </div>
                <div class="metric">
                  <div class="metric-label">Latency</div>
                  <div class="metric-value" id="metricLatency">-</div>
                </div>
                <div class="metric">
                  <div class="metric-label">Retrieved IDs</div>
                  <div class="metric-value" id="metricIds">-</div>
                </div>
                <div class="metric">
                  <div class="metric-label">Source Count</div>
                  <div class="metric-value" id="metricSources">0</div>
                </div>
              </div>
            </section>

            <details>
              <summary>Raw JSON</summary>
              <pre id="rawJson"></pre>
            </details>
          </div>
        </div>
      </section>
    </main>

    <footer class="footer">
      <span>FastAPI service</span>
      <span>Cloud Run ready</span>
      <span>Public corpus only</span>
    </footer>
  </div>

  <script>
    const question = document.querySelector("#question");
    const apiKey = document.querySelector("#apiKey");
    const topK = document.querySelector("#topK");
    const askButton = document.querySelector("#askButton");
    const modeButtons = Array.from(document.querySelectorAll("[data-mode]"));
    const sampleButtons = Array.from(document.querySelectorAll(".sample-button"));
    const modeHelp = document.querySelector("#modeHelp");
    const emptyState = document.querySelector("#emptyState");
    const result = document.querySelector("#result");
    const statusText = document.querySelector("#statusText");
    const modeChip = document.querySelector("#modeChip");
    const answerText = document.querySelector("#answerText");
    const sources = document.querySelector("#sources");
    const sourceCount = document.querySelector("#sourceCount");
    const metricMode = document.querySelector("#metricMode");
    const metricLatency = document.querySelector("#metricLatency");
    const metricIds = document.querySelector("#metricIds");
    const metricSources = document.querySelector("#metricSources");
    const rawJson = document.querySelector("#rawJson");
    const answerSection = document.querySelector("#answerSection");

    let activeMode = "rag";

    function setMode(mode) {
      activeMode = mode;
      modeButtons.forEach((button) => {
        button.classList.toggle("active", button.dataset.mode === mode);
      });
      modeChip.textContent = `Mode: ${mode.toUpperCase()}`;
      topK.disabled = mode === "agent";
      modeHelp.textContent = mode === "agent"
        ? "Agent uses server-side Vertex/LangGraph credentials and is disabled in the free-tier BYOK deployment."
        : "RAG performs one retrieval pass and one grounded generation call using your Gemini API key.";
    }

    function setLoading(isLoading) {
      askButton.disabled = isLoading;
      askButton.textContent = isLoading ? "Retrieving..." : "Ask";
      if (isLoading) {
        statusText.textContent = "Retrieving evidence...";
      }
    }

    function normalizeArray(value) {
      return Array.isArray(value) ? value : [];
    }

    function renderSources(items) {
      sources.textContent = "";
      if (!items.length) {
        const empty = document.createElement("span");
        empty.className = "source-chip";
        empty.textContent = "No explicit citations returned";
        sources.appendChild(empty);
        return;
      }

      items.forEach((item) => {
        const chip = document.createElement("span");
        chip.className = "source-chip";
        chip.textContent = item;
        sources.appendChild(chip);
      });
    }

    function renderResponse(data) {
      const citations = normalizeArray(data.citations);
      const retrievedIds = normalizeArray(data.retrieved_ids);
      const latency = Number.isFinite(data.latency_ms) ? `${data.latency_ms} ms` : "-";
      const mode = data.mode || activeMode;

      emptyState.hidden = true;
      result.hidden = false;
      answerSection.classList.remove("error");

      answerText.textContent = data.answer || "No answer returned.";
      renderSources(citations);
      sourceCount.textContent = String(citations.length);
      metricMode.textContent = mode;
      metricLatency.textContent = latency;
      metricIds.textContent = retrievedIds.length ? retrievedIds.join(", ") : "-";
      metricSources.textContent = String(citations.length);
      rawJson.textContent = JSON.stringify(data, null, 2);
      statusText.textContent = "Response ready.";
    }

    function renderError(error) {
      emptyState.hidden = true;
      result.hidden = false;
      answerSection.classList.add("error");
      answerText.textContent = error.message || "Request failed.";
      renderSources([]);
      sourceCount.textContent = "0";
      metricMode.textContent = activeMode;
      metricLatency.textContent = "-";
      metricIds.textContent = "-";
      metricSources.textContent = "0";
      rawJson.textContent = JSON.stringify({ error: error.message }, null, 2);
      statusText.textContent = "Request failed.";
    }

    async function ask() {
      const text = question.value.trim();
      if (!text) {
        question.focus();
        statusText.textContent = "Enter a question first.";
        return;
      }

      const key = apiKey.value.trim();
      if (activeMode === "agent" && key) {
        statusText.textContent = "Personal API key mode is available for RAG mode only.";
        renderError(new Error("Agent mode uses server-side Vertex/LangGraph credentials. Switch to RAG mode to use your personal Gemini API key."));
        return;
      }

      setLoading(true);

      try {
        const payload = {
          question: text,
          agent: activeMode === "agent"
        };

        if (key) {
          payload.api_key = key;
        }

        if (activeMode !== "agent") {
          payload.k = Number(topK.value || 5);
        }

        const response = await fetch("/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const contentType = response.headers.get("content-type") || "";
        const data = contentType.includes("application/json")
          ? await response.json()
          : { detail: await response.text() };

        if (!response.ok) {
          throw new Error(data.detail || response.statusText);
        }

        renderResponse(data);
      } catch (error) {
        renderError(error);
      } finally {
        setLoading(false);
      }
    }

    modeButtons.forEach((button) => {
      button.addEventListener("click", () => setMode(button.dataset.mode));
    });

    sampleButtons.forEach((button) => {
      button.addEventListener("click", () => {
        question.value = button.textContent.trim();
        question.focus();
      });
    });

    askButton.addEventListener("click", ask);
    question.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        ask();
      }
    });

    setMode("rag");
  </script>
</body>
</html>
"""


class Ask(BaseModel):
    question: str
    k: int | None = None
    agent: bool = False
    api_key: str | None = None


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/ask")
def ask(body: Ask):
    try:
        api_key = (body.api_key or "").strip()
        if body.agent:
            if config.REQUIRE_API_KEY_FOR_RAG:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": (
                            "Agent mode is disabled in this free-tier BYOK deployment. "
                            "Use RAG mode with a personal Gemini API key."
                        )
                    },
                )
            if api_key:
                return {
                    "answer": (
                        "Personal API key mode is supported for RAG mode only. "
                        "Agent mode uses the server-side Vertex/LangGraph configuration."
                    ),
                    "mode": "agent",
                    "latency_ms": 0,
                }
            from . import agent  # lazy import so core works without agent deps
            return agent.run(body.question)
        if config.REQUIRE_API_KEY_FOR_RAG and not api_key:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": (
                        "Enter a personal Gemini API key to use Gemini 2.5 Pro free-tier RAG mode."
                    )
                },
            )
        return rag.answer(body.question, body.k, api_key=api_key or None)
    except Exception as exc:
        log.exception("ask failed")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Request failed inside FieldRAG. Check Cloud Run logs for the stack trace.",
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            },
        )


@app.get("/", response_class=HTMLResponse)
def home():
    return HOME_HTML
