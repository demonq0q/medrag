import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./icons";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const LOCAL_HISTORY_KEY = "medrag:xiaohe:conversation-history:v1";
const MAX_LOCAL_CONVERSATIONS = 30;

const suggestions = [
  { title: "药物相互作用", text: "华法林和阿司匹林能否同时服用" },
  { title: "检查指标解读", text: "糖化血红蛋白的参考范围和影响因素是什么" },
  { title: "循证问答", text: "2型糖尿病合并肾功能异常如何评估用药" },
];

function readLocalConversations() {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(LOCAL_HISTORY_KEY);
    if (!raw) return [];
    const payload = JSON.parse(raw);
    const records = Array.isArray(payload) ? payload : payload?.version === 1 ? payload.conversations : [];
    if (!Array.isArray(records)) return [];
    return records
      .filter((item) => item && typeof item.conversation_id === "string" && Array.isArray(item.messages))
      .slice(0, MAX_LOCAL_CONVERSATIONS);
  } catch {
    return [];
  }
}

function writeLocalConversations(conversations) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LOCAL_HISTORY_KEY, JSON.stringify({ version: 1, conversations }));
  } catch {
    // Storage can be disabled or full; the current conversation still works in memory.
  }
}

function upsertLocalConversation(current, conversation) {
  const existing = current.find((item) => item.conversation_id === conversation.conversation_id);
  const record = {
    ...existing,
    ...conversation,
    title: existing?.title || conversation.title,
  };
  return [record, ...current.filter((item) => item.conversation_id !== record.conversation_id)].slice(0, MAX_LOCAL_CONVERSATIONS);
}

function BrandMark() {
  return (
    <div className="brand-mark" aria-hidden="true">
      <Icon name="sparkle" size={24} strokeWidth={1.7} />
    </div>
  );
}

function CitationMark({ id, onClick }) {
  return (
    <button className="citation-mark" onClick={() => onClick(id)} type="button">
      [{id}]
    </button>
  );
}

function AnswerText({ text, onCitation }) {
  const renderInline = (value, keyPrefix) => value.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    const match = part.match(/^\*\*(.+)\*\*$/);
    return match ? <strong key={`${keyPrefix}-bold-${index}`}>{match[1]}</strong> : <span key={`${keyPrefix}-text-${index}`}>{part}</span>;
  });
  return (
    <div className="answer-text">
      {text.split("\n").map((line, lineIndex) => {
        const parts = line.split(/(\[C\d+\])/g);
        const isHeading = line.startsWith("## ");
        const isBullet = line.startsWith("- ");
        return (
          <div className={isHeading ? "answer-heading" : isBullet ? "answer-line answer-bullet" : "answer-line"} key={`${lineIndex}-${line}`}>
            {parts.map((part, index) => {
              const match = part.match(/^\[C(\d+)\]$/);
              if (match) return <CitationMark id={`C${match[1]}`} key={`${part}-${index}`} onClick={onCitation} />;
              return <span key={`${part}-${index}`}>{renderInline(isHeading && index === 0 ? part.slice(3) : part, `${lineIndex}-${index}`)}</span>;
            })}
          </div>
        );
      })}
    </div>
  );
}

function Sidebar({ collapsed, mobileOpen, activeView, onNavigate, onNewChat, onOpenConversation, conversations, onToggle }) {
  const primary = [
    ["chat", "问答", "message"],
    ["knowledge", "知识库", "book"],
    ["evaluation", "评估", "chart"],
  ];
  return (
    <aside className={`sidebar ${collapsed ? "is-collapsed" : ""} ${mobileOpen ? "is-mobile-open" : ""}`}>
      <div className="sidebar-top">
        <div className="brand-lockup">
          <BrandMark />
          {!collapsed && <div><div className="brand-name">小荷</div><div className="brand-subtitle">MedRAG</div></div>}
        </div>
        <button className="icon-button collapse-button" onClick={onToggle} aria-label={collapsed ? "展开侧栏" : "收起侧栏"} type="button">
          <Icon name={collapsed ? "chevron" : "panel"} size={18} />
        </button>
      </div>

      <button className={`new-chat-button ${collapsed ? "compact" : ""}`} onClick={onNewChat} type="button">
        <Icon name="plus" size={19} />
        {!collapsed && <span>新建对话</span>}
      </button>

      <nav className="primary-nav" aria-label="主导航">
        {primary.map(([key, label, icon]) => (
          <button className={`nav-item ${activeView === key ? "active" : ""}`} key={key} onClick={() => onNavigate(key)} type="button">
            <Icon name={icon} size={19} />
            {!collapsed && <span>{label}</span>}
          </button>
        ))}
      </nav>

      {!collapsed && (
        <div className="history-block">
          <div className="history-heading"><span>历史对话</span><Icon name="search" size={16} /></div>
          <div className="history-section-label">最近</div>
          {conversations.length === 0 ? (
            <div className="empty-history">完成一次问答后，对话会显示在这里</div>
          ) : conversations.slice(0, 8).map((conversation) => (
            <button className="history-item" key={conversation.conversation_id} onClick={() => onOpenConversation(conversation)} type="button" title={conversation.title}>
              <span>{conversation.title}</span><time>{formatTime(conversation.updated_at)}</time>
            </button>
          ))}
        </div>
      )}

      <div className="sidebar-bottom">
        {!collapsed && <div className="workspace-status"><span className="status-dot" />本地知识库已连接</div>}
        <button className="profile-button" type="button">
          <span className="avatar"><Icon name="user" size={17} /></span>
          {!collapsed && <span className="profile-copy"><strong>医学助手</strong><small>循证模式</small></span>}
          {!collapsed && <Icon name="down" size={15} className="profile-chevron" />}
        </button>
      </div>
    </aside>
  );
}

function TopBar({ activeView, onMenu, onEvidence, showEvidence }) {
  const titles = { chat: "问答", knowledge: "知识库", evaluation: "评估" };
  return (
    <header className="topbar">
      <button className="mobile-menu-button icon-button" onClick={onMenu} aria-label="打开导航" type="button"><Icon name="menu" size={20} /></button>
      <div className="mode-selector"><span className="mode-icon"><Icon name="shield" size={15} /></span><span>循证优先</span><Icon name="down" size={14} /></div>
      <div className="topbar-spacer" />
      <div className="topbar-actions">
        <button className="topbar-action" type="button"><Icon name="clock" size={17} /><span>对话记录</span></button>
        <button className="topbar-action" type="button"><Icon name="bookmark" size={17} /><span>收藏</span></button>
        {activeView === "chat" && <button className={`topbar-action evidence-toggle ${showEvidence ? "active" : ""}`} onClick={onEvidence} type="button"><Icon name="panel" size={17} /><span>引用来源</span></button>}
        <button className="topbar-action" type="button"><Icon name="settings" size={17} /><span>设置</span></button>
      </div>
    </header>
  );
}

function Composer({ value, onChange, onSubmit, loading, onAttach }) {
  const ref = useRef(null);
  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  };
  useEffect(() => {
    if (!loading && ref.current) ref.current.focus();
  }, [loading]);
  return (
    <div className="composer-dock">
      <div className="composer">
        <textarea ref={ref} value={value} onChange={(event) => onChange(event.target.value)} onKeyDown={handleKeyDown} placeholder="请输入您的医学问题…" rows={1} aria-label="医学问题输入框" />
        <div className="composer-toolbar">
          <button className="composer-tool" onClick={onAttach} type="button"><Icon name="paperclip" size={17} />附件</button>
          <div className="composer-actions">
            <span className="composer-mode">循证回答 <Icon name="down" size={13} /></span>
            <button className="send-button" onClick={onSubmit} disabled={loading || !value.trim()} type="button"><Icon name="send" size={17} />{loading ? "检索中" : "发送"}</button>
          </div>
        </div>
      </div>
      <div className="composer-disclaimer"><Icon name="alert" size={14} />本平台提供的信息仅供参考，不能替代医生的诊断和治疗建议。急症请立即就医。</div>
    </div>
  );
}

function Welcome({ onSuggestion }) {
  return (
    <section className="welcome-state">
      <div className="welcome-icon"><BrandMark /></div>
      <h1>今天想了解什么医学问题？</h1>
      <p>小荷会从指南、药品说明书和结构化知识库中检索依据，并为每个结论提供来源。</p>
      <div className="suggestion-grid">
        {suggestions.map((suggestion) => (
          <button className="suggestion-card" key={suggestion.text} onClick={() => onSuggestion(suggestion.text)} type="button">
            <span className="suggestion-label">{suggestion.title}</span><span>{suggestion.text}</span><Icon name="chevron" size={15} />
          </button>
        ))}
      </div>
    </section>
  );
}

function MessageBubble({ message, onCitation }) {
  const isUser = message.role === "user";
  return (
    <article className={`message-row ${isUser ? "user-row" : "assistant-row"}`}>
      {!isUser && <div className="assistant-avatar"><BrandMark /></div>}
      <div className={`message-content ${isUser ? "user-message" : "assistant-message"}`}>
        {isUser ? <p>{message.content}</p> : <AnswerText text={message.content} onCitation={onCitation} />}
        {!isUser && message.meta && (
          <div className="message-meta">
            <div className="message-tools"><button type="button" title="复制"><Icon name="copy" size={15} /></button><button type="button" title="有帮助"><Icon name="like" size={15} /></button><button type="button" title="没帮助"><Icon name="dislike" size={15} /></button></div>
            <span className={`answer-status ${message.meta.risk_level}`}><span className="status-dot" />{message.meta.risk_level === "high" ? "需要重点核对" : message.meta.risk_level === "critical" ? "建议立即就医" : "已完成审核"}</span>
          </div>
        )}
      </div>
      {isUser && <div className="user-avatar"><Icon name="user" size={16} /></div>}
    </article>
  );
}

function EvidencePanel({ citations, selectedCitation, onClose, onSelect, riskLevel }) {
  return (
    <aside className="evidence-panel">
      <div className="evidence-header"><div><span className="eyebrow">答案溯源</span><h2>引用来源</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭引用来源" type="button"><Icon name="x" size={18} /></button></div>
      <div className="evidence-summary"><div className="summary-heading"><span>证据等级分布</span><span>共 {citations.length} 篇</span></div><div className="evidence-distribution"><strong>{citations.filter((item) => item.evidence_level === "A").length}<small>A 级</small></strong><strong>{citations.filter((item) => item.evidence_level === "B").length}<small>B 级</small></strong><strong>{citations.filter((item) => item.evidence_level === "C").length}<small>C 级</small></strong><strong>{citations.filter((item) => !["A", "B", "C"].includes(item.evidence_level)).length}<small>其他</small></strong></div></div>
      <div className="citation-list">
        {citations.length === 0 ? <div className="empty-evidence"><Icon name="book" size={25} /><p>完成一次问答后，这里会显示可核验的来源。</p></div> : citations.map((citation, index) => (
          <button className={`citation-card ${selectedCitation === citation.citation_id ? "selected" : ""}`} key={citation.citation_id} onClick={() => onSelect(citation.citation_id)} type="button">
            <div className="citation-number">{index + 1}</div><div className="citation-copy"><strong>{citation.source.split("/").pop()}</strong><span>{citation.doc_type}{citation.section ? ` · ${citation.section}` : ""}</span><small>{citation.evidence_level ? `${citation.evidence_level} 级证据` : "知识库来源"}{citation.page_number ? ` · 第 ${citation.page_number} 页` : ""}</small></div>
          </button>
        ))}
      </div>
      <div className={`risk-card ${riskLevel}`}><div className="risk-icon"><Icon name={riskLevel === "low" ? "check" : "alert"} size={17} /></div><div><strong>风险状态</strong><span>{riskLevel === "critical" ? "发现急症提示" : riskLevel === "high" ? "存在高风险用药提示" : "当前问题未发现高风险信号"}</span></div></div>
      <p className="evidence-footnote">风险评估基于对话内容和知识库规则，不替代临床判断。</p>
    </aside>
  );
}

function KnowledgeView({ metrics, onRefresh }) {
  const cards = [
    ["documents", "来源文档", "份"], ["chunks", "可检索片段", "条"], ["faq_count", "FAQ 问答", "条"], ["interactions", "相互作用", "组"],
  ];
  return <main className="content-view"><div className="view-heading"><div><span className="eyebrow">知识资产</span><h1>知识库概览</h1><p>所有回答都从本地医学资料中检索，并保留来源和版本信息。</p></div><button className="secondary-button" onClick={onRefresh} type="button"><Icon name="refresh" size={16} />刷新指标</button></div><div className="metric-grid">{cards.map(([key, label, unit]) => <div className="metric-card" key={key}><span>{label}</span><strong>{metrics?.[key] ?? "—"}<small>{unit}</small></strong></div>)}</div><div className="knowledge-section"><div className="section-heading"><h2>当前索引能力</h2><span>运行中</span></div><div className="capability-list"><div><Icon name="search" size={19} /><span><strong>混合检索</strong><small>FTS5 关键词 · FAQ · 图谱关系 · 结构化检验值</small></span></div><div><Icon name="shield" size={19} /><span><strong>安全审核</strong><small>急症识别 · 相互作用 · 无证据阻断 · 医疗免责声明</small></span></div><div><Icon name="book" size={19} /><span><strong>循证溯源</strong><small>指南、说明书和知识条目均保留 section / page 信息</small></span></div></div></div></main>;
}

function EvaluationView({ metrics }) {
  const checks = ["华法林 × 阿司匹林相互作用", "扑热息痛术语标准化", "检验指标参考范围", "无证据问题保守拒答", "PDF 页码与章节溯源"];
  return <main className="content-view"><div className="view-heading"><div><span className="eyebrow">质量与安全</span><h1>验收面板</h1><p>面向医疗问答的关键安全路径和知识覆盖概览。</p></div><div className="score-badge"><span>基础链路</span><strong>可运行</strong></div></div><div className="evaluation-layout"><div className="evaluation-card"><div className="section-heading"><h2>核心场景</h2><span>5 项</span></div>{checks.map((item) => <div className="check-row" key={item}><span className="check-icon"><Icon name="check" size={14} /></span><span>{item}</span><small>已覆盖</small></div>)}</div><div className="evaluation-card"><div className="section-heading"><h2>数据规模</h2><span>实时</span></div><div className="coverage-number"><strong>{metrics?.chunks ?? "—"}</strong><span>可检索 Chunk</span></div><div className="coverage-line"><span style={{ width: "78%" }} /></div><p>当前数据覆盖内分泌、心内、呼吸、消化、神经、精神、骨科和肾内等领域。</p></div></div></main>;
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export default function App() {
  const [activeView, setActiveView] = useState("chat");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showEvidence, setShowEvidence] = useState(true);
  const [selectedCitation, setSelectedCitation] = useState(null);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [citations, setCitations] = useState([]);
  const [riskLevel, setRiskLevel] = useState("low");
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState(() => readLocalConversations());
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    try {
      const metricsResponse = await fetch(`${API_BASE}/v1/metrics`);
      if (metricsResponse.ok) setMetrics(await metricsResponse.json());
    } catch {
      setError("暂时无法连接知识库服务，请确认 API 已启动。");
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { writeLocalConversations(conversations); }, [conversations]);

  const submitQuestion = useCallback(async (value = question) => {
    const text = value.trim();
    if (!text || loading) return;
    setQuestion("");
    setError("");
    setActiveView("chat");
    setMessages((current) => [...current, { role: "user", content: text }]);
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/v1/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: text, conversation_id: conversationId, top_k: 6 }) });
      if (!response.ok) throw new Error("query failed");
      const data = await response.json();
      setConversationId(data.conversation_id);
      setCitations(data.citations || []);
      setRiskLevel(data.risk_level || "low");
      const assistantMessage = { role: "assistant", content: data.answer, meta: data };
      const userMessage = { role: "user", content: text };
      setMessages((current) => [...current, assistantMessage]);
      setConversations((current) => {
        const previous = current.find((item) => item.conversation_id === data.conversation_id);
        return upsertLocalConversation(current, {
          conversation_id: data.conversation_id,
          title: text.slice(0, 40),
          updated_at: new Date().toISOString(),
          messages: [...(previous?.messages || []), userMessage, assistantMessage],
          citations: data.citations || [],
          risk_level: data.risk_level || "low",
        });
      });
    } catch {
      setError("问答服务暂时不可用，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }, [conversationId, loading, question]);

  const openConversation = useCallback((conversation) => {
    const restoredMessages = Array.isArray(conversation.messages) ? conversation.messages : [];
    const lastAssistant = [...restoredMessages].reverse().find((message) => message.role === "assistant");
    setMessages(restoredMessages);
    setCitations(conversation.citations || lastAssistant?.meta?.citations || []);
    setRiskLevel(conversation.risk_level || lastAssistant?.meta?.risk_level || "low");
    setConversationId(conversation.conversation_id);
    setQuestion("");
    setError("");
    setSelectedCitation(null);
    setActiveView("chat");
    setMobileOpen(false);
  }, []);

  const newChat = () => { setMessages([]); setCitations([]); setRiskLevel("low"); setConversationId(null); setQuestion(""); setError(""); setSelectedCitation(null); setActiveView("chat"); setMobileOpen(false); };
  const navigate = (view) => { setActiveView(view); setMobileOpen(false); };
  const activeCitationText = useMemo(() => citations.find((item) => item.citation_id === selectedCitation)?.snippet, [citations, selectedCitation]);

  return (
    <div className="app-shell">
      {mobileOpen && <button className="mobile-overlay" onClick={() => setMobileOpen(false)} aria-label="关闭导航" type="button" />}
      <Sidebar collapsed={collapsed} mobileOpen={mobileOpen} activeView={activeView} onNavigate={navigate} onNewChat={newChat} onOpenConversation={openConversation} conversations={conversations} onToggle={() => setCollapsed((value) => !value)} />
      <div className="main-stage">
        <TopBar activeView={activeView} onMenu={() => setMobileOpen(true)} onEvidence={() => setShowEvidence((value) => !value)} showEvidence={showEvidence} />
        {activeView === "knowledge" ? <KnowledgeView metrics={metrics} onRefresh={loadData} /> : activeView === "evaluation" ? <EvaluationView metrics={metrics} /> : (
          <div className="workspace">
            <main className="chat-column">
              <div className="chat-scroll">
                <div className={`chat-inner ${messages.length === 0 ? "is-welcome" : ""}`}>
                  {messages.length === 0 ? <Welcome onSuggestion={submitQuestion} /> : messages.map((message, index) => <MessageBubble key={`${message.role}-${index}`} message={message} onCitation={setSelectedCitation} />)}
                  {loading && <div className="typing-row"><div className="assistant-avatar"><BrandMark /></div><div className="typing-indicator"><span /><span /><span /><em>正在检索医学证据…</em></div></div>}
                  {error && <div className="error-notice"><Icon name="alert" size={16} />{error}</div>}
                </div>
              </div>
              <Composer value={question} onChange={setQuestion} onSubmit={() => submitQuestion()} loading={loading} onAttach={() => setError("文档预览入口将在下一步接入；当前支持 API 上传预览。")} />
            </main>
            {showEvidence && <EvidencePanel citations={citations} selectedCitation={selectedCitation} onClose={() => setShowEvidence(false)} onSelect={setSelectedCitation} riskLevel={riskLevel} />}
          </div>
        )}
      </div>
      {selectedCitation && activeCitationText && <div className="citation-popover"><div><strong>{selectedCitation} · 证据摘录</strong><button className="icon-button" onClick={() => setSelectedCitation(null)} type="button"><Icon name="x" size={15} /></button></div><p>{activeCitationText}</p></div>}
    </div>
  );
}
