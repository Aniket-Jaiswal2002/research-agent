import { useState, useRef, useEffect } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";

const API = "https://research-agent-production-3bc9.up.railway.app";

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hi! I'm **ResearchMind** 🔬\n\nUpload a PDF and ask me anything about it. I can also search the web for latest information!",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pdfs, setPdfs] = useState([]);
  const [activePdf, setActivePdf] = useState(null);
  const bottomRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    fetchPdfs();
  }, []);

  const fetchPdfs = async () => {
    try {
      const res = await axios.get(`${API}/status`);
      setPdfs(res.data.pdfs || []);
      setActivePdf(res.data.active_pdf);
    } catch (err) {
      console.log("Backend not ready yet");
    }
  };

  const selectPdf = async (pdfName) => {
    try {
      await axios.post(`${API}/select-pdf`, { pdf_name: pdfName });
      setActivePdf(pdfName);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `📄 Switched to **${pdfName}**. Ask me anything about it!`,
        },
      ]);
    } catch (err) {
      console.error("Failed to select PDF");
    }
  };

  const uploadPDF = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await axios.post(`${API}/upload`, formData);
      setActivePdf(res.data.pdf_name);
      setPdfs((prev) =>
        prev.includes(res.data.pdf_name) ? prev : [...prev, res.data.pdf_name]
      );
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `✅ **${file.name}** uploaded!\n\n${res.data.chunks} chunks indexed. Ask me anything about it!`,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "❌ Failed to upload PDF. Please try again." },
      ]);
    } finally {
      setUploading(false);
      fetchPdfs();
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    try {
      const res = await axios.post(`${API}/ask`, { question });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.data.answer },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "❌ Something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={styles.root}>
      {/* Sidebar */}
      <div style={styles.sidebar}>
        <div style={styles.logo}>
          <span style={styles.logoIcon}>🔬</span>
          <span style={styles.logoText}>ResearchMind</span>
        </div>

        <p style={styles.sidebarDesc}>
          Your AI research assistant. Upload PDFs and ask anything.
        </p>

        {/* Upload button */}
        <div style={styles.uploadBox} onClick={() => fileRef.current.click()}>
          <input
            type="file"
            accept=".pdf"
            ref={fileRef}
            onChange={uploadPDF}
            style={{ display: "none" }}
          />
          {uploading ? (
            <div style={styles.uploadInner}>
              <div style={styles.spinner} />
              <span style={{ color: "#c4b5fd", fontSize: 13 }}>Processing PDF...</span>
              <span style={{ color: "#4b5563", fontSize: 11 }}>This may take 10-15 seconds</span>
            </div>
          ) : (
            <div style={styles.uploadInner}>
              <span style={{ fontSize: 28 }}>📄</span>
              <span style={styles.uploadText}>Click to upload PDF</span>
              <span style={styles.uploadSub}>Supports any PDF up to 500 pages</span>
            </div>
          )}
        </div>

        {/* PDF Library */}
        {pdfs.length > 0 && (
          <div style={styles.pdfLibrary}>
            <div style={styles.libraryLabel}>📚 Your PDFs ({pdfs.length})</div>
            {pdfs.map((pdf) => (
              <div
                key={pdf}
                style={styles.pdfItem(pdf === activePdf)}
                onClick={() => selectPdf(pdf)}
              >
                <span style={{ fontSize: 14 }}>📄</span>
                <span style={styles.pdfName}>{pdf}</span>
                {pdf === activePdf && <span style={styles.activeTag}>active</span>}
              </div>
            ))}
          </div>
        )}

        <div style={styles.features}>
          <div style={styles.feature}>🔍 Semantic PDF search</div>
          <div style={styles.feature}>🌐 Live web search</div>
          <div style={styles.feature}>📌 Cited answers</div>
          <div style={styles.feature}>⚡ Powered by LLaMA 3.3</div>
        </div>

        <div style={styles.sidebarFooter}>Built by Aniket Jaiswal</div>
      </div>

      {/* Chat */}
      <div style={styles.chat}>
        <div style={styles.header}>
          <div>
            <div style={styles.headerTitle}>ResearchMind</div>
            <div style={styles.headerSub}>
              {activePdf ? `📄 ${activePdf} — active` : "No PDF loaded — web search available"}
            </div>
          </div>
          <div style={styles.statusDot(!!activePdf)} />
        </div>

        <div style={styles.messages}>
          {messages.map((msg, i) => (
            <div key={i} style={styles.msgRow(msg.role)}>
              <div style={styles.avatar(msg.role)}>
                {msg.role === "assistant" ? "🔬" : "👤"}
              </div>
              <div style={styles.bubble(msg.role)}>
                <ReactMarkdown
                  components={{
                   a: ({node, ...props}) => (
                     <a {...props} target="_blank" rel="noopener noreferrer" style={{color: "#a5b4fc", textDecoration: "underline"}}>
                      {props.children}
                     </a>
                    )
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              </div>
            </div>
          ))}

          {loading && (
            <div style={styles.msgRow("assistant")}>
              <div style={styles.avatar("assistant")}>🔬</div>
              <div style={styles.bubble("assistant")}>
                <div style={styles.typing}>
                  <span style={styles.dot(0)} />
                  <span style={styles.dot(1)} />
                  <span style={styles.dot(2)} />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div style={styles.inputArea}>
          <textarea
            style={styles.textarea}
            placeholder="Ask anything about your PDF or any research topic..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            rows={1}
          />
          <button
            style={styles.sendBtn(loading || !input.trim())}
            onClick={sendMessage}
            disabled={loading || !input.trim()}
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
        <div style={styles.inputHint}>Press Enter to send · Shift+Enter for new line</div>
      </div>
    </div>
  );
}

const styles = {
  root: {
    display: "flex",
    height: "100vh",
    background: "#0f1117",
    color: "#e8eaf6",
    fontFamily: "'Inter', sans-serif",
    overflow: "hidden",
  },
  sidebar: {
    width: 280,
    minWidth: 280,
    background: "#161b27",
    borderRight: "1px solid #1e2535",
    display: "flex",
    flexDirection: "column",
    padding: "24px 20px",
    gap: 16,
    overflowY: "auto",
  },
  logo: { display: "flex", alignItems: "center", gap: 10 },
  logoIcon: { fontSize: 28 },
  logoText: {
    fontSize: 20,
    fontWeight: 700,
    background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
  },
  sidebarDesc: { fontSize: 13, color: "#6b7280", lineHeight: 1.6, margin: 0 },
  uploadBox: {
    border: "1.5px dashed #2d3748",
    borderRadius: 12,
    padding: "16px",
    cursor: "pointer",
  },
  uploadInner: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 6,
  },
  uploadText: { fontSize: 13, fontWeight: 500, color: "#c4b5fd", textAlign: "center" },
  uploadSub: { fontSize: 11, color: "#4b5563", textAlign: "center" },
  spinner: {
    width: 24,
    height: 24,
    border: "3px solid #2d3748",
    borderTop: "3px solid #6366f1",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  pdfLibrary: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  libraryLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: "#6b7280",
    letterSpacing: "0.05em",
    marginBottom: 4,
  },
  pdfItem: (active) => ({
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 10px",
    borderRadius: 8,
    cursor: "pointer",
    background: active ? "#1e2d45" : "transparent",
    border: active ? "1px solid #3b4fd8" : "1px solid transparent",
    transition: "all 0.15s",
  }),
  pdfName: {
    fontSize: 12,
    color: "#c4b5fd",
    flex: 1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  activeTag: {
    fontSize: 10,
    background: "#312e81",
    color: "#a5b4fc",
    padding: "2px 6px",
    borderRadius: 4,
  },
  features: { display: "flex", flexDirection: "column", gap: 8 },
  feature: { fontSize: 12, color: "#6b7280" },
  sidebarFooter: { marginTop: "auto", fontSize: 11, color: "#374151", textAlign: "center" },
  chat: { flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" },
  header: {
    padding: "16px 24px",
    borderBottom: "1px solid #1e2535",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    background: "#161b27",
  },
  headerTitle: { fontWeight: 600, fontSize: 16 },
  headerSub: { fontSize: 12, color: "#6b7280", marginTop: 2 },
  statusDot: (active) => ({
    width: 10,
    height: 10,
    borderRadius: "50%",
    background: active ? "#10b981" : "#374151",
    boxShadow: active ? "0 0 8px #10b981" : "none",
  }),
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  msgRow: (role) => ({
    display: "flex",
    gap: 12,
    flexDirection: role === "user" ? "row-reverse" : "row",
    alignItems: "flex-start",
  }),
  avatar: (role) => ({
    width: 36,
    height: 36,
    borderRadius: "50%",
    background: role === "assistant" ? "#1e2535" : "#312e81",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 16,
    flexShrink: 0,
  }),
  bubble: (role) => ({
    maxWidth: "70%",
    background: role === "assistant" ? "#161b27" : "#312e81",
    border: role === "assistant" ? "1px solid #1e2535" : "none",
    borderRadius: role === "assistant" ? "4px 16px 16px 16px" : "16px 4px 16px 16px",
    padding: "12px 16px",
    fontSize: 14,
    lineHeight: 1.7,
    color: "#e8eaf6",
  }),
  typing: { display: "flex", gap: 4, alignItems: "center", padding: "4px 0" },
  dot: (i) => ({
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: "#6366f1",
    animation: `bounce 1s ease-in-out ${i * 0.15}s infinite`,
  }),
  inputArea: {
    padding: "16px 24px 8px",
    display: "flex",
    gap: 12,
    alignItems: "flex-end",
    borderTop: "1px solid #1e2535",
  },
  textarea: {
    flex: 1,
    background: "#161b27",
    border: "1px solid #2d3748",
    borderRadius: 12,
    padding: "12px 16px",
    color: "#e8eaf6",
    fontSize: 14,
    resize: "none",
    outline: "none",
    fontFamily: "inherit",
    lineHeight: 1.5,
  },
  sendBtn: (disabled) => ({
    background: disabled ? "#1e2535" : "linear-gradient(135deg, #6366f1, #8b5cf6)",
    color: disabled ? "#4b5563" : "white",
    border: "none",
    borderRadius: 12,
    padding: "12px 20px",
    fontSize: 14,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
  }),
  inputHint: { fontSize: 11, color: "#374151", textAlign: "center", paddingBottom: 12 },
};
