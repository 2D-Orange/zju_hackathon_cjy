import { ChangeEvent, DragEvent, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  BarChart3,
  BookOpenText,
  Bot,
  CheckCircle2,
  Database,
  GitBranch,
  GitMerge,
  Loader2,
  MessageSquareText,
  MousePointerClick,
  Network,
  RefreshCw,
  Send,
  UploadCloud,
} from "lucide-react";
import * as echarts from "echarts";

type TextbookStatus = "parsing" | "parsed" | "failed";

type Chapter = {
  chapter_id: string;
  title: string;
  page_start: number;
  page_end: number;
  content: string;
  char_count: number;
};

type TextbookSummary = {
  textbook_id: string;
  filename: string;
  title: string;
  format: string;
  size_bytes: number;
  size_label: string;
  status: TextbookStatus;
  message: string;
  total_pages: number;
  total_chars: number;
  chapter_count: number;
  uploaded_at: string;
};

type TextbookDetail = TextbookSummary & {
  chapters: Chapter[];
};

type UploadResponse = {
  textbooks: TextbookSummary[];
};

type GraphRelationType = "prerequisite" | "parallel" | "contains" | "applies_to";

type KnowledgeOccurrence = {
  chapter_id: string;
  chapter: string;
  page: number;
  source_text: string;
};

type KnowledgeNode = {
  id: string;
  name: string;
  definition: string;
  category: string;
  textbook_id: string;
  textbook_title: string;
  chapter_id: string;
  chapter: string;
  page: number;
  source_text: string;
  frequency: number;
  occurrences: KnowledgeOccurrence[];
};

type KnowledgeEdge = {
  id: string;
  source: string;
  target: string;
  relation_type: GraphRelationType;
  label: string;
  weight: number;
  textbook_id: string;
  textbook_title: string;
  chapter: string;
  page: number;
  source_text: string;
};

type GraphResponse = {
  graph_id: string;
  textbook_ids: string[];
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
  stats: {
    textbook_count: number;
    node_count: number;
    edge_count: number;
    relation_types: GraphRelationType[];
  };
  build_mode: "auto" | "llm" | "mock";
  generated_at: string;
};

type IntegrationAction = "merge" | "keep" | "remove";
type ConceptRelationType = "same_concept" | "broader_narrower" | "related";

type IntegratedKnowledgeNode = {
  id: string;
  name: string;
  definition: string;
  category: string;
  source_nodes: string[];
  textbook_titles: string[];
  chapters: string[];
  pages: number[];
  source_text: string;
  char_count: number;
};

type IntegrationDecision = {
  decision_id: string;
  action: IntegrationAction;
  concept_relation: ConceptRelationType;
  reason: string;
  confidence: number;
  affected_nodes: string[];
  result_node: IntegratedKnowledgeNode;
  original_chars: number;
  compressed_chars: number;
  editable: boolean;
  manually_edited: boolean;
  created_at: string;
  updated_at: string;
};

type IntegrationResponse = {
  textbook_ids: string[];
  decisions: IntegrationDecision[];
  stats: {
    textbook_count: number;
    decision_count: number;
    merge_count: number;
    keep_count: number;
    remove_count: number;
    original_chars: number;
    compressed_chars: number;
    compression_ratio: number;
  };
  generated_at: string;
};

type RagIndexStatus = {
  indexed: boolean;
  textbook_ids: string[];
  chunk_count: number;
  embedding_mode: "local" | "online";
  updated_at: string | null;
};

type RagCitation = {
  textbook: string;
  chapter: string;
  page: number;
  page_start: number;
  page_end: number;
  relevance_score: number;
};

type RagSourceChunk = {
  chunk_id: string;
  textbook_id: string;
  textbook: string;
  chapter: string;
  page_start: number;
  page_end: number;
  text: string;
  relevance_score: number;
};

type RagQueryResponse = {
  answer: string;
  citations: RagCitation[];
  source_chunks: RagSourceChunk[];
  generated_at: string;
};

type ChatMessage = {
  message_id: string;
  role: "teacher" | "assistant";
  content: string;
  decision_id: string | null;
  created_at: string;
};

type TeacherFeedbackResponse = {
  session_id: string;
  intent: "explain" | "modify" | "clarify";
  answer: string;
  history: ChatMessage[];
  updated_decision: IntegrationDecision | null;
};

type ReportSummary = {
  textbook_count: number;
  parsed_textbook_count: number;
  total_chapters: number;
  total_chars: number;
  graph_node_count: number;
  graph_edge_count: number;
  graph_textbook_count: number;
  integration_decision_count: number;
  integration_merge_count: number;
  integration_keep_count: number;
  integration_remove_count: number;
  compression_ratio: number;
  original_chars: number;
  compressed_chars: number;
  rag_indexed: boolean;
  rag_chunk_count: number;
  rag_embedding_mode: string;
  chat_session_count: number;
};

type TabKey = "integration" | "rag" | "chat" | "report";

const API_BASE_URL = normalizeApiBase(import.meta.env.VITE_API_BASE_URL || "/api");
const textbookPalette = ["#0f766e", "#2563eb", "#b45309", "#be123c", "#6d28d9", "#15803d", "#0f4c81"];
const relationPalette: Record<GraphRelationType, string> = {
  contains: "#64748b",
  prerequisite: "#0f766e",
  parallel: "#7c3aed",
  applies_to: "#b45309",
};

const tabs: Array<{ key: TabKey; label: string; icon: typeof GitMerge }> = [
  { key: "integration", label: "整合", icon: GitMerge },
  { key: "rag", label: "RAG", icon: Bot },
  { key: "chat", label: "对话", icon: MessageSquareText },
  { key: "report", label: "报告", icon: BarChart3 },
];

function App() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [textbooks, setTextbooks] = useState<TextbookSummary[]>([]);
  const [activeTab, setActiveTab] = useState<TabKey>("integration");
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [selectedTextbookId, setSelectedTextbookId] = useState<string | null>(null);
  const [selectedTextbook, setSelectedTextbook] = useState<TextbookDetail | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [integration, setIntegration] = useState<IntegrationResponse | null>(null);
  const [isIntegrationLoading, setIsIntegrationLoading] = useState(false);
  const [integrationError, setIntegrationError] = useState<string | null>(null);
  const [ragStatus, setRagStatus] = useState<RagIndexStatus | null>(null);
  const [ragResponse, setRagResponse] = useState<RagQueryResponse | null>(null);
  const [isRagIndexing, setIsRagIndexing] = useState(false);
  const [isRagQuerying, setIsRagQuerying] = useState(false);
  const [ragError, setRagError] = useState<string | null>(null);
  const [chatSessionId, setChatSessionId] = useState(() => getStoredChatSessionId());
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>(() => getStoredChatHistory());
  const [isChatSending, setIsChatSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshTextbooks().then((items) => {
      const firstParsed = items.find((item) => item.status === "parsed");
      if (firstParsed) {
        void selectTextbook(firstParsed.textbook_id);
      }
    });
    void refreshIntegrationDecisions();
    void refreshRagStatus();
  }, []);

  const uploadedCount = textbooks.filter((item) => item.status === "parsed").length;
  const failedCount = textbooks.filter((item) => item.status === "failed").length;

  const totalSize = useMemo(
    () => textbooks.reduce((sum, item) => sum + item.size_bytes, 0),
    [textbooks],
  );

  const handleGraphLoaded = useCallback((nextGraph: GraphResponse | null) => {
    setGraph(nextGraph);
    setSelectedNode((currentNode) => {
      if (!nextGraph) {
        return null;
      }
      if (currentNode && nextGraph.nodes.some((node) => node.id === currentNode.id)) {
        return currentNode;
      }
      return nextGraph.nodes[0] ?? null;
    });
  }, []);

  async function refreshTextbooks() {
    try {
      const response = await fetch(`${API_BASE_URL}/textbooks`);
      if (!response.ok) {
        throw new Error("教材列表读取失败");
      }
      const items: TextbookSummary[] = await response.json();
      setTextbooks(items);
      return items;
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法连接后端服务");
      return [];
    }
  }

  async function selectTextbook(textbookId: string) {
    setSelectedTextbookId(textbookId);
    setIsDetailLoading(true);
    setGraph(null);
    setSelectedNode(null);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/textbooks/${textbookId}`);
      if (!response.ok) {
        throw new Error("教材详情读取失败");
      }
      setSelectedTextbook(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "教材详情读取失败");
      setSelectedTextbook(null);
    } finally {
      setIsDetailLoading(false);
    }
  }

  async function refreshIntegrationDecisions() {
    try {
      const response = await fetch(`${API_BASE_URL}/integration/decisions`);
      if (!response.ok) {
        throw new Error(await readApiError(response, "整合决策读取失败"));
      }
      const result: IntegrationResponse = await response.json();
      setIntegration(result.decisions.length > 0 ? result : null);
      setIntegrationError(null);
    } catch (err) {
      setIntegrationError(err instanceof Error ? err.message : "整合决策读取失败");
    }
  }

  async function runIntegration() {
    const textbookIds = textbooks
      .filter((item) => item.status === "parsed")
      .map((item) => item.textbook_id);
    if (textbookIds.length < 2) {
      setIntegrationError("跨教材整合至少需要两本已解析教材");
      return;
    }

    setIsIntegrationLoading(true);
    setIntegrationError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/integration/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ textbook_ids: textbookIds }),
      });
      if (!response.ok) {
        throw new Error(await readApiError(response, "整合运行失败"));
      }
      setIntegration(await response.json());
    } catch (err) {
      setIntegrationError(err instanceof Error ? err.message : "整合运行失败");
    } finally {
      setIsIntegrationLoading(false);
    }
  }

  async function patchIntegrationDecision(decisionId: string, patch: { action: IntegrationAction }) {
    setIntegrationError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/integration/decisions/${decisionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!response.ok) {
        throw new Error(await readApiError(response, "决策修改失败"));
      }
      const updatedDecision: IntegrationDecision = await response.json();
      setIntegration((current) => {
        if (!current) {
          return current;
        }
        const decisions = current.decisions.map((decision) =>
          decision.decision_id === decisionId ? updatedDecision : decision,
        );
        return {
          ...current,
          decisions,
          stats: summarizeIntegrationStats(current.stats, decisions),
        };
      });
      await refreshIntegrationDecisions();
    } catch (err) {
      setIntegrationError(err instanceof Error ? err.message : "决策修改失败");
    }
  }

  async function refreshRagStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/rag/status`);
      if (!response.ok) {
        throw new Error(await readApiError(response, "RAG 索引状态读取失败"));
      }
      setRagStatus(await response.json());
      setRagError(null);
    } catch (err) {
      setRagError(err instanceof Error ? err.message : "RAG 索引状态读取失败");
    }
  }

  async function buildRagIndex() {
    const textbookIds = textbooks
      .filter((item) => item.status === "parsed")
      .map((item) => item.textbook_id);
    if (textbookIds.length === 0) {
      setRagError("请先上传并解析教材");
      return;
    }

    setIsRagIndexing(true);
    setRagError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/rag/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ textbook_ids: textbookIds, chunk_size: 700, overlap: 80 }),
      });
      if (!response.ok) {
        throw new Error(await readApiError(response, "RAG 索引建立失败"));
      }
      setRagStatus(await response.json());
      setRagResponse(null);
    } catch (err) {
      setRagError(err instanceof Error ? err.message : "RAG 索引建立失败");
    } finally {
      setIsRagIndexing(false);
    }
  }

  async function queryRag(question: string) {
    if (!question.trim()) {
      return;
    }

    setIsRagQuerying(true);
    setRagError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/rag/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim(), top_k: 5 }),
      });
      if (!response.ok) {
        throw new Error(await readApiError(response, "RAG 问答失败"));
      }
      setRagResponse(await response.json());
    } catch (err) {
      setRagError(err instanceof Error ? err.message : "RAG 问答失败");
    } finally {
      setIsRagQuerying(false);
    }
  }

  async function sendTeacherFeedback(message: string, decisionId: string | null) {
    if (!message.trim()) {
      return;
    }

    setIsChatSending(true);
    setChatError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: chatSessionId,
          message: message.trim(),
          decision_id: decisionId,
          history: chatHistory,
        }),
      });
      if (!response.ok) {
        throw new Error(await readApiError(response, "教师反馈处理失败"));
      }
      const result: TeacherFeedbackResponse = await response.json();
      setChatSessionId(result.session_id);
      storeChatSessionId(result.session_id);
      setChatHistory(result.history);
      storeChatHistory(result.history);
      if (result.updated_decision) {
        const updatedDecision = result.updated_decision;
        setIntegration((current) => {
          if (!current) {
            return current;
          }
          const decisions = current.decisions.map((decision) =>
            decision.decision_id === updatedDecision.decision_id ? updatedDecision : decision,
          );
          return {
            ...current,
            decisions,
            stats: summarizeIntegrationStats(current.stats, decisions),
          };
        });
        await refreshIntegrationDecisions();
      }
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "教师反馈处理失败");
    } finally {
      setIsChatSending(false);
    }
  }

  async function uploadFiles(files: FileList | File[]) {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) {
      return;
    }

    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    fileArray.forEach((file) => formData.append("files", file));

    try {
      const response = await fetch(`${API_BASE_URL}/textbooks/upload`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error("上传接口返回异常");
      }
      const result: UploadResponse = await response.json();
      const items = await refreshTextbooks();
      const firstUploaded = result.textbooks[0] ?? items[0];
      if (firstUploaded) {
        await selectTextbook(firstUploaded.textbook_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    void uploadFiles(event.dataTransfer.files);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) {
      void uploadFiles(event.target.files);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Network size={22} aria-hidden="true" />
          </div>
          <div>
            <h1>医学教材整合</h1>
            <p>AI 全栈极速黑客松</p>
          </div>
        </div>

        <div
          className={`upload-zone ${isDragging ? "is-dragging" : ""}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          role="button"
          tabIndex={0}
        >
          <input
            ref={fileInputRef}
            className="file-input"
            type="file"
            multiple
            accept=".pdf,.md,.markdown,.txt"
            onChange={handleFileChange}
          />
          <UploadCloud size={34} aria-hidden="true" />
          <strong>{isUploading ? "上传/解析中..." : "拖拽或点击上传"}</strong>
          <span>PDF / Markdown / TXT</span>
        </div>

        {error ? <div className="error-banner">{error}</div> : null}

        <section className="stats-strip" aria-label="教材统计">
          <div>
            <strong>{uploadedCount}</strong>
            <span>已接收</span>
          </div>
          <div>
            <strong>{failedCount}</strong>
            <span>失败</span>
          </div>
          <div>
            <strong>{formatSize(totalSize)}</strong>
            <span>总大小</span>
          </div>
        </section>

        <section className="file-list" aria-label="教材列表">
          <header>
            <h2>教材列表</h2>
            {isUploading ? <Loader2 className="spin" size={18} aria-hidden="true" /> : null}
          </header>

          {textbooks.length === 0 ? (
            <div className="empty-list">暂无教材</div>
          ) : (
            textbooks.map((item) => (
              <TextbookCard
                key={item.textbook_id}
                item={item}
                isSelected={item.textbook_id === selectedTextbookId}
                onSelect={() => void selectTextbook(item.textbook_id)}
              />
            ))
          )}
        </section>
      </aside>

      <section className="graph-stage">
        <div className="stage-toolbar">
          <div>
            <span className="eyebrow">Knowledge Graph</span>
            <h2>{selectedTextbook ? selectedTextbook.title : "教材知识图谱"}</h2>
          </div>
          <div className="mock-badge">
            {graph ? `${graph.stats.node_count} 节点 · ${graph.stats.edge_count} 边` : "Stage 3 Graph"}
          </div>
        </div>

        <GraphStage
          textbook={selectedTextbook}
          isLoading={isDetailLoading || isUploading}
          selectedNode={selectedNode}
          onGraphLoaded={handleGraphLoaded}
          onNodeSelect={setSelectedNode}
        />
      </section>

      <aside className="right-panel">
        <nav className="tab-list" aria-label="功能面板">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                className={activeTab === tab.key ? "active" : ""}
                onClick={() => setActiveTab(tab.key)}
                type="button"
              >
                <Icon size={17} aria-hidden="true" />
                {tab.label}
              </button>
            );
          })}
        </nav>

        <NodeDetail node={selectedNode} graph={graph} />
        <PanelContent
          activeTab={activeTab}
          textbooks={textbooks}
          graph={graph}
          integration={integration}
          isIntegrationLoading={isIntegrationLoading}
          integrationError={integrationError}
          ragStatus={ragStatus}
          ragResponse={ragResponse}
          isRagIndexing={isRagIndexing}
          isRagQuerying={isRagQuerying}
          ragError={ragError}
          chatHistory={chatHistory}
          isChatSending={isChatSending}
          chatError={chatError}
          onRunIntegration={() => void runIntegration()}
          onPatchDecision={(decisionId, patch) => void patchIntegrationDecision(decisionId, patch)}
          onBuildRagIndex={() => void buildRagIndex()}
          onQueryRag={(question) => void queryRag(question)}
          onSendTeacherFeedback={(message, decisionId) => void sendTeacherFeedback(message, decisionId)}
        />
      </aside>
    </main>
  );
}

function TextbookCard({
  item,
  isSelected,
  onSelect,
}: {
  item: TextbookSummary;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const isFailed = item.status === "failed";
  const isParsing = item.status === "parsing";

  return (
    <button
      className={`textbook-card ${isFailed ? "failed" : ""} ${isSelected ? "selected" : ""}`}
      onClick={onSelect}
      type="button"
    >
      <div className="file-icon">
        {isFailed ? <AlertCircle size={18} aria-hidden="true" /> : null}
        {isParsing ? <Loader2 className="spin" size={18} aria-hidden="true" /> : null}
        {!isFailed && !isParsing ? <CheckCircle2 size={18} aria-hidden="true" /> : null}
      </div>
      <div className="file-meta">
        <strong title={item.filename}>{item.filename}</strong>
        <span>
          {item.format} · {item.size_label}
        </span>
        <span>
          {item.total_pages > 0 ? `${item.total_pages} 页 · ` : ""}
          {item.total_chars} 字 · {item.chapter_count} 章
        </span>
        <small>{item.message}</small>
      </div>
      <span className={`status-pill ${isFailed ? "failed" : isParsing ? "parsing" : "done"}`}>
        {statusLabel(item.status)}
      </span>
    </button>
  );
}

function GraphStage({
  textbook,
  isLoading,
  selectedNode,
  onGraphLoaded,
  onNodeSelect,
}: {
  textbook: TextbookDetail | null;
  isLoading: boolean;
  selectedNode: KnowledgeNode | null;
  onGraphLoaded: (graph: GraphResponse | null) => void;
  onNodeSelect: (node: KnowledgeNode) => void;
}) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [isGraphLoading, setIsGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) {
      return;
    }
    const chart = echarts.init(chartContainerRef.current);
    chartRef.current = chart;
    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!textbook || textbook.status !== "parsed") {
      setGraph(null);
      onGraphLoaded(null);
      return;
    }
    let isCancelled = false;
    void requestGraph(false, () => isCancelled);
    return () => {
      isCancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textbook?.textbook_id, textbook?.status]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !graph) {
      return;
    }
    chart.setOption(createGraphOption(graph, selectedNode?.id), true);
    window.setTimeout(() => chart.resize(), 0);
  }, [graph, selectedNode?.id]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !graph) {
      return;
    }
    const handleClick = (params: { dataType?: string; data?: unknown }) => {
      if (params.dataType !== "node") {
        return;
      }
      const data = params.data as { node?: KnowledgeNode };
      if (data.node) {
        onNodeSelect(data.node);
      }
    };
    chart.on("click", handleClick);
    return () => {
      chart.off("click", handleClick);
    };
  }, [graph, onNodeSelect]);

  async function requestGraph(useBuild: boolean, isCancelled: () => boolean = () => false) {
    if (!textbook) {
      return;
    }
    setIsGraphLoading(true);
    setGraphError(null);
    try {
      const response = await fetch(
        useBuild ? `${API_BASE_URL}/graph/build` : `${API_BASE_URL}/graph/${textbook.textbook_id}`,
        useBuild
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ textbook_ids: [textbook.textbook_id], mode: "auto" }),
            }
          : undefined,
      );
      if (!response.ok) {
        throw new Error(await readApiError(response, "图谱生成失败"));
      }
      const nextGraph: GraphResponse = await response.json();
      if (isCancelled()) {
        return;
      }
      setGraph(nextGraph);
      onGraphLoaded(nextGraph);
    } catch (err) {
      if (isCancelled()) {
        return;
      }
      setGraph(null);
      onGraphLoaded(null);
      setGraphError(err instanceof Error ? err.message : "图谱生成失败");
    } finally {
      if (!isCancelled()) {
        setIsGraphLoading(false);
      }
    }
  }

  if (isLoading && !textbook) {
    return (
      <div className="parser-empty">
        <Loader2 className="spin" size={28} aria-hidden="true" />
        <strong>解析中</strong>
        <span>正在读取文件并识别章节结构</span>
      </div>
    );
  }

  if (!textbook) {
    return (
      <div className="parser-empty">
        <BookOpenText size={34} aria-hidden="true" />
        <strong>等待上传教材</strong>
        <span>上传 PDF、Markdown 或 TXT 后，这里会生成可追溯的知识图谱。</span>
      </div>
    );
  }

  if (textbook.status === "failed") {
    return (
      <div className="parser-empty">
        <AlertCircle size={34} aria-hidden="true" />
        <strong>教材解析失败</strong>
        <span>{textbook.message}</span>
      </div>
    );
  }

  return (
    <div className="graph-result">
      <section className="detail-summary graph-summary" aria-label="图谱统计">
        <div>
          <span>节点</span>
          <strong>{graph?.stats.node_count ?? "-"}</strong>
        </div>
        <div>
          <span>关系</span>
          <strong>{graph?.stats.edge_count ?? "-"}</strong>
        </div>
        <div>
          <span>关系类型</span>
          <strong>{graph ? graph.stats.relation_types.length : "-"}</strong>
        </div>
        <div>
          <span>提取模式</span>
          <strong>{graph?.build_mode ?? "auto"}</strong>
        </div>
      </section>

      <div className="graph-actions">
        <div>
          <GitBranch size={17} aria-hidden="true" />
          {graph ? (
            <span>{graph.stats.relation_types.map(relationLabel).join(" / ") || "暂无关系"}</span>
          ) : (
            <span>等待图谱生成</span>
          )}
        </div>
        <button type="button" onClick={() => void requestGraph(true)} disabled={isGraphLoading}>
          {isGraphLoading ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <RefreshCw size={16} />}
          重建图谱
        </button>
      </div>

      <div className="graph-canvas-shell">
        <div ref={chartContainerRef} className="graph-canvas" aria-label="知识图谱" />
        {isGraphLoading ? (
          <div className="graph-overlay">
            <Loader2 className="spin" size={26} aria-hidden="true" />
            <strong>生成图谱中</strong>
          </div>
        ) : null}
        {graphError ? (
          <div className="graph-overlay">
            <AlertCircle size={26} aria-hidden="true" />
            <strong>{graphError}</strong>
          </div>
        ) : null}
        {!isGraphLoading && graph && graph.nodes.length === 0 ? (
          <div className="graph-overlay">
            <BookOpenText size={26} aria-hidden="true" />
            <strong>未从章节原文中提取到可追溯知识点</strong>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function NodeDetail({ node, graph }: { node: KnowledgeNode | null; graph: GraphResponse | null }) {
  if (!node) {
    return (
      <section className="node-detail empty-detail">
        <MousePointerClick size={22} aria-hidden="true" />
        <strong>节点详情</strong>
        <span>{graph ? "点击图谱节点查看定义、页码与原文出处。" : "生成图谱后可查看节点出处。"}</span>
      </section>
    );
  }

  return (
    <section className="node-detail">
      <header>
        <div>
          <span>{node.category}</span>
          <h2>{node.name}</h2>
        </div>
        <strong>{node.frequency} 次</strong>
      </header>
      <dl>
        <div>
          <dt>定义</dt>
          <dd>{node.definition}</dd>
        </div>
        <div>
          <dt>教材</dt>
          <dd>{node.textbook_title}</dd>
        </div>
        <div>
          <dt>章节</dt>
          <dd>{node.chapter}</dd>
        </div>
        <div>
          <dt>页码</dt>
          <dd>第 {node.page} 页</dd>
        </div>
        <div>
          <dt>原文出处</dt>
          <dd className="source-text">{node.source_text}</dd>
        </div>
      </dl>
    </section>
  );
}

function PanelContent({
  activeTab,
  textbooks,
  graph,
  integration,
  isIntegrationLoading,
  integrationError,
  ragStatus,
  ragResponse,
  isRagIndexing,
  isRagQuerying,
  ragError,
  chatHistory,
  isChatSending,
  chatError,
  onRunIntegration,
  onPatchDecision,
  onBuildRagIndex,
  onQueryRag,
  onSendTeacherFeedback,
}: {
  activeTab: TabKey;
  textbooks: TextbookSummary[];
  graph: GraphResponse | null;
  integration: IntegrationResponse | null;
  isIntegrationLoading: boolean;
  integrationError: string | null;
  ragStatus: RagIndexStatus | null;
  ragResponse: RagQueryResponse | null;
  isRagIndexing: boolean;
  isRagQuerying: boolean;
  ragError: string | null;
  chatHistory: ChatMessage[];
  isChatSending: boolean;
  chatError: string | null;
  onRunIntegration: () => void;
  onPatchDecision: (decisionId: string, patch: { action: IntegrationAction }) => void;
  onBuildRagIndex: () => void;
  onQueryRag: (question: string) => void;
  onSendTeacherFeedback: (message: string, decisionId: string | null) => void;
}) {
  const validBooks = textbooks.filter((item) => item.status !== "failed");
  const parsedBookCount = validBooks.filter((item) => item.status === "parsed").length;

  if (activeTab === "integration") {
    return (
      <IntegrationPanel
        parsedBookCount={parsedBookCount}
        currentNodeCount={graph?.stats.node_count ?? 0}
        integration={integration}
        isLoading={isIntegrationLoading}
        error={integrationError}
        onRun={onRunIntegration}
        onPatchDecision={onPatchDecision}
      />
    );
  }

  if (activeTab === "rag") {
    return (
      <RagPanel
        parsedBookCount={parsedBookCount}
        status={ragStatus}
        response={ragResponse}
        isIndexing={isRagIndexing}
        isQuerying={isRagQuerying}
        error={ragError}
        onBuildIndex={onBuildRagIndex}
        onQuery={onQueryRag}
      />
    );
  }

  if (activeTab === "chat") {
    return (
      <TeacherChatPanel
        integration={integration}
        history={chatHistory}
        isSending={isChatSending}
        error={chatError}
        onSend={onSendTeacherFeedback}
      />
    );
  }

  return <ReportPanel textbooks={textbooks} />;
}

function TeacherChatPanel({
  integration,
  history,
  isSending,
  error,
  onSend,
}: {
  integration: IntegrationResponse | null;
  history: ChatMessage[];
  isSending: boolean;
  error: string | null;
  onSend: (message: string, decisionId: string | null) => void;
}) {
  const [message, setMessage] = useState("");
  const [decisionId, setDecisionId] = useState<string>("");
  const decisions = integration?.decisions ?? [];

  useEffect(() => {
    if (!decisionId && decisions[0]) {
      setDecisionId(decisions[0].decision_id);
    }
    if (decisionId && !decisions.some((decision) => decision.decision_id === decisionId)) {
      setDecisionId(decisions[0]?.decision_id ?? "");
    }
  }, [decisionId, decisions]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSend(message, decisionId || null);
    setMessage("");
  }

  return (
    <section className="panel-body teacher-chat-panel">
      <h2>教师对话</h2>

      {error ? <div className="error-banner">{error}</div> : null}

      <label className="chat-decision-picker">
        <span>关联决策</span>
        <select
          value={decisionId}
          onChange={(event) => setDecisionId(event.target.value)}
          disabled={decisions.length === 0}
        >
          {decisions.length === 0 ? (
            <option value="">暂无整合决策</option>
          ) : (
            decisions.map((decision) => (
              <option key={decision.decision_id} value={decision.decision_id}>
                {actionLabel(decision.action)} · {decision.result_node.name}
              </option>
            ))
          )}
        </select>
      </label>

      <div className="chat-shell">
        {history.length === 0 ? (
          <div className="chat-message empty">等待教师反馈。</div>
        ) : (
          history.map((item) => (
            <article className={`chat-message ${item.role}`} key={item.message_id}>
              <strong>{item.role === "teacher" ? "教师" : "系统"}</strong>
              <p>{item.content}</p>
            </article>
          ))
        )}
      </div>

      <form className="teacher-chat-form" onSubmit={handleSubmit}>
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="询问整合原因，或输入“把这个合并改为保留”"
          disabled={isSending || decisions.length === 0}
        />
        <button type="submit" disabled={isSending || decisions.length === 0 || !message.trim()}>
          {isSending ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Send size={16} />}
          发送反馈
        </button>
      </form>
    </section>
  );
}

function RagPanel({
  parsedBookCount,
  status,
  response,
  isIndexing,
  isQuerying,
  error,
  onBuildIndex,
  onQuery,
}: {
  parsedBookCount: number;
  status: RagIndexStatus | null;
  response: RagQueryResponse | null;
  isIndexing: boolean;
  isQuerying: boolean;
  error: string | null;
  onBuildIndex: () => void;
  onQuery: (question: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const indexed = status?.indexed ?? false;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onQuery(question);
  }

  return (
    <section className="panel-body rag-panel">
      <div className="panel-title-row">
        <h2>RAG 问答</h2>
        <button type="button" onClick={onBuildIndex} disabled={isIndexing || parsedBookCount === 0}>
          {isIndexing ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Database size={16} />}
          建索引
        </button>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="rag-status-grid">
        <div>
          <span>索引</span>
          <strong>{indexed ? "已建立" : "未建立"}</strong>
        </div>
        <div>
          <span>Chunk</span>
          <strong>{status?.chunk_count ?? 0}</strong>
        </div>
        <div>
          <span>教材</span>
          <strong>{status?.textbook_ids.length ?? parsedBookCount}</strong>
        </div>
        <div>
          <span>Embedding</span>
          <strong>{status?.embedding_mode ?? "local"}</strong>
        </div>
      </div>

      <form className="rag-question-form" onSubmit={handleSubmit}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="输入教材内问题"
          disabled={!indexed || isQuerying}
        />
        <button type="submit" disabled={!indexed || isQuerying || !question.trim()}>
          {isQuerying ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Send size={16} />}
          提问
        </button>
      </form>

      {response ? (
        <div className="rag-result">
          <article className="rag-answer">
            <span>回答</span>
            <p>{response.answer}</p>
          </article>

          {response.citations.length > 0 ? (
            <section className="rag-citations" aria-label="引用">
              {response.citations.map((citation, index) => (
                <div key={`${citation.textbook}-${citation.chapter}-${citation.page}-${index}`}>
                  <strong>{citationText(citation)}</strong>
                  <span>{formatPercent(citation.relevance_score)}</span>
                </div>
              ))}
            </section>
          ) : null}

          {response.source_chunks.length > 0 ? (
            <section className="rag-source-list" aria-label="来源 chunk">
              {response.source_chunks.map((chunk, index) => (
                <details key={chunk.chunk_id} className="rag-source-chunk" open={index === 0}>
                  <summary>
                    <span>{sourceChunkTitle(chunk)}</span>
                    <strong>{formatPercent(chunk.relevance_score)}</strong>
                  </summary>
                  <p>{chunk.text}</p>
                </details>
              ))}
            </section>
          ) : null}
        </div>
      ) : (
        <div className="placeholder-block">等待提问。</div>
      )}
    </section>
  );
}

function IntegrationPanel({
  parsedBookCount,
  currentNodeCount,
  integration,
  isLoading,
  error,
  onRun,
  onPatchDecision,
}: {
  parsedBookCount: number;
  currentNodeCount: number;
  integration: IntegrationResponse | null;
  isLoading: boolean;
  error: string | null;
  onRun: () => void;
  onPatchDecision: (decisionId: string, patch: { action: IntegrationAction }) => void;
}) {
  const stats = integration?.stats;

  return (
    <section className="panel-body integration-panel">
      <div className="panel-title-row">
        <h2>跨教材整合</h2>
        <button type="button" onClick={onRun} disabled={isLoading || parsedBookCount < 2}>
          {isLoading ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <GitMerge size={16} />}
          运行
        </button>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="integration-metrics">
        <div>
          <span>教材</span>
          <strong>{stats?.textbook_count ?? parsedBookCount}</strong>
        </div>
        <div>
          <span>节点</span>
          <strong>{currentNodeCount}</strong>
        </div>
        <div>
          <span>决策</span>
          <strong>{stats?.decision_count ?? 0}</strong>
        </div>
        <div>
          <span>压缩比</span>
          <strong>{stats ? formatPercent(stats.compression_ratio) : "-"}</strong>
        </div>
      </div>

      {stats ? (
        <div className="compression-bar" aria-label="压缩比">
          <span style={{ width: `${Math.min(100, stats.compression_ratio * 100)}%` }} />
          <strong>
            {stats.compressed_chars} / {stats.original_chars} 字
          </strong>
        </div>
      ) : null}

      <div className="decision-counts">
        <span>Merge {stats?.merge_count ?? 0}</span>
        <span>Keep {stats?.keep_count ?? 0}</span>
        <span>Remove {stats?.remove_count ?? 0}</span>
      </div>

      {!integration || integration.decisions.length === 0 ? (
        <div className="placeholder-block">暂无整合决策。</div>
      ) : (
        <div className="decision-list">
          {integration.decisions.map((decision) => (
            <article className="decision-card" key={decision.decision_id}>
              <header>
                <div>
                  <span className={`action-pill ${decision.action}`}>{actionLabel(decision.action)}</span>
                  <strong>{decision.result_node.name}</strong>
                </div>
                <select
                  value={decision.action}
                  disabled={!decision.editable}
                  onChange={(event) =>
                    onPatchDecision(decision.decision_id, {
                      action: event.target.value as IntegrationAction,
                    })
                  }
                  aria-label="修改整合决策"
                >
                  <option value="merge">merge</option>
                  <option value="keep">keep</option>
                  <option value="remove">remove</option>
                </select>
              </header>
              <div className="confidence-row">
                <span>{conceptRelationLabel(decision.concept_relation)}</span>
                <strong>{formatPercent(decision.confidence)}</strong>
              </div>
              <p>{decision.reason}</p>
              <dl>
                <div>
                  <dt>影响节点</dt>
                  <dd>{decision.affected_nodes.length}</dd>
                </div>
                <div>
                  <dt>来源</dt>
                  <dd>{decision.result_node.textbook_titles.join(" / ")}</dd>
                </div>
                <div>
                  <dt>章节</dt>
                  <dd>{decision.result_node.chapters.slice(0, 2).join(" / ")}</dd>
                </div>
              </dl>
              {decision.result_node.source_text ? (
                <blockquote>{decision.result_node.source_text}</blockquote>
              ) : null}
              {decision.manually_edited ? <footer>已人工修改</footer> : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ReportPanel({ textbooks }: { textbooks: TextbookSummary[] }) {
  const [report, setReport] = useState<ReportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API_BASE_URL}/report/summary`)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(await readApiError(res, "报告获取失败"));
        }
        return res.json() as Promise<ReportSummary>;
      })
      .then((data) => {
        if (!cancelled) {
          setReport(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "报告获取失败");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [textbooks]);

  if (loading) {
    return (
      <section className="panel-body report-panel">
        <h2>整合报告</h2>
        <div className="placeholder-block">
          <Loader2 className="spin" size={24} aria-hidden="true" />
          正在汇总系统统计...
        </div>
      </section>
    );
  }

  if (error || !report) {
    return (
      <section className="panel-body report-panel">
        <h2>整合报告</h2>
        <div className="placeholder-block">{error || "暂无可用的报告数据"}</div>
      </section>
    );
  }

  return (
    <section className="panel-body report-panel">
      <h2>整合报告</h2>

      <div className="report-section">
        <h3>教材概览</h3>
        <div className="metric-grid">
          <div className="metric-card">
            <strong>{report.textbook_count}</strong>
            <span>上传教材</span>
          </div>
          <div className="metric-card">
            <strong>{report.parsed_textbook_count}</strong>
            <span>已解析</span>
          </div>
          <div className="metric-card">
            <strong>{report.total_chapters}</strong>
            <span>章节总数</span>
          </div>
          <div className="metric-card">
            <strong>{formatSize(report.total_chars * 3)}</strong>
            <span>总字符数</span>
          </div>
        </div>
      </div>

      <div className="report-section">
        <h3>知识图谱</h3>
        <div className="metric-grid">
          <div className="metric-card">
            <strong>{report.graph_node_count}</strong>
            <span>知识节点</span>
          </div>
          <div className="metric-card">
            <strong>{report.graph_edge_count}</strong>
            <span>关系边</span>
          </div>
          <div className="metric-card">
            <strong>{report.graph_textbook_count}</strong>
            <span>覆盖教材</span>
          </div>
          <div className="metric-card">
            <strong>{report.graph_textbook_count > 0 ? Math.round(report.graph_node_count / Math.max(1, report.graph_textbook_count)) : 0}</strong>
            <span>平均每本节点</span>
          </div>
        </div>
      </div>

      <div className="report-section">
        <h3>跨教材整合</h3>
        <div className="metric-grid">
          <div className="metric-card">
            <strong>{report.integration_decision_count}</strong>
            <span>整合决策</span>
          </div>
          <div className="metric-card action-merge">
            <strong>{report.integration_merge_count}</strong>
            <span>合并</span>
          </div>
          <div className="metric-card action-keep">
            <strong>{report.integration_keep_count}</strong>
            <span>保留</span>
          </div>
          <div className="metric-card action-remove">
            <strong>{report.integration_remove_count}</strong>
            <span>移除</span>
          </div>
        </div>
        {report.integration_decision_count > 0 ? (
          <div className="compression-bar" style={{ marginTop: 12 }}>
            <div className="compression-label">
              <span>压缩比</span>
              <strong>{formatPercent(report.compression_ratio)}</strong>
            </div>
            <div className="compression-track">
              <div
                className="compression-fill"
                style={{ width: `${Math.min(100, Math.round(report.compression_ratio * 100))}%` }}
              />
            </div>
            <div className="compression-hint" style={{ marginTop: 6 }}>
              {report.original_chars > 0 && report.compressed_chars > 0
                ? `原始 ${Math.round(report.original_chars)} 字 → 整合 ${Math.round(report.compressed_chars)} 字`
                : null}
            </div>
          </div>
        ) : null}
      </div>

      <div className="report-section">
        <h3>RAG 问答状态</h3>
        <div className="metric-grid">
          <div className="metric-card">
            <strong>{report.rag_indexed ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}</strong>
            <span>{report.rag_indexed ? "已索引" : "未索引"}</span>
          </div>
          <div className="metric-card">
            <strong>{report.rag_chunk_count}</strong>
            <span>检索分块</span>
          </div>
          <div className="metric-card">
            <strong>{report.rag_embedding_mode || "—"}</strong>
            <span>嵌入模式</span>
          </div>
        </div>
      </div>

      <div className="report-section">
        <h3>教师反馈</h3>
        <div className="metric-grid">
          <div className="metric-card">
            <strong>{report.chat_session_count}</strong>
            <span>对话会话</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function createGraphOption(graph: GraphResponse, selectedNodeId?: string) {
  const textbookTitles = Array.from(new Set(graph.nodes.map((node) => node.textbook_title)));
  const textbookColor = new Map(
    textbookTitles.map((title, index) => [title, textbookPalette[index % textbookPalette.length]]),
  );
  const maxFrequency = Math.max(1, ...graph.nodes.map((node) => node.frequency));

  return {
    backgroundColor: "#f8fafc",
    tooltip: {
      trigger: "item",
      confine: true,
      formatter: (params: { dataType?: string; data?: unknown }) => {
        const data = params.data as { node?: KnowledgeNode; edge?: KnowledgeEdge };
        if (params.dataType === "node" && data.node) {
          return [
            `<strong>${escapeHtml(data.node.name)}</strong>`,
            escapeHtml(data.node.category),
            `${escapeHtml(data.node.chapter)} · 第 ${data.node.page} 页`,
            `出现 ${data.node.frequency} 次`,
          ].join("<br/>");
        }
        if (data.edge) {
          return [
            `<strong>${escapeHtml(relationLabel(data.edge.relation_type))}</strong>`,
            escapeHtml(data.edge.source_text),
          ].join("<br/>");
        }
        return "";
      },
    },
    legend: {
      top: 12,
      left: 12,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: "#475467", fontSize: 12 },
      data: textbookTitles,
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        categories: textbookTitles.map((title) => ({
          name: title,
          itemStyle: { color: textbookColor.get(title) },
        })),
        data: graph.nodes.map((node) => {
          const baseColor = textbookColor.get(node.textbook_title) ?? textbookPalette[0];
          return {
            id: node.id,
            name: node.name,
            value: node.frequency,
            category: textbookTitles.indexOf(node.textbook_title),
            symbolSize: 32 + Math.min(28, (node.frequency / maxFrequency) * 28),
            itemStyle: {
              color: colorByFrequency(baseColor, node.frequency, maxFrequency),
              borderColor: node.id === selectedNodeId ? "#111827" : "#ffffff",
              borderWidth: node.id === selectedNodeId ? 4 : 2,
              shadowColor: "rgba(15, 23, 42, 0.22)",
              shadowBlur: node.id === selectedNodeId ? 18 : 8,
            },
            label: {
              show: true,
              color: "#172033",
              fontSize: 12,
              width: 108,
              overflow: "truncate",
            },
            node,
          };
        }),
        links: graph.edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          value: edge.weight,
          label: {
            show: true,
            formatter: edge.label,
            color: relationPalette[edge.relation_type],
            fontSize: 11,
          },
          lineStyle: {
            color: relationPalette[edge.relation_type],
            width: 1.7,
            opacity: 0.62,
            curveness: edge.relation_type === "parallel" ? 0.2 : 0.08,
          },
          edge,
        })),
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [0, 8],
        force: {
          repulsion: 260,
          edgeLength: [86, 170],
          gravity: 0.08,
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: { width: 3, opacity: 0.9 },
        },
      },
    ],
  };
}

function relationLabel(relation: GraphRelationType) {
  if (relation === "prerequisite") {
    return "先修";
  }
  if (relation === "parallel") {
    return "并列";
  }
  if (relation === "contains") {
    return "包含";
  }
  return "应用于";
}

function actionLabel(action: IntegrationAction) {
  if (action === "merge") {
    return "合并";
  }
  if (action === "remove") {
    return "移除";
  }
  return "保留";
}

function conceptRelationLabel(relation: ConceptRelationType) {
  if (relation === "same_concept") {
    return "同一概念";
  }
  if (relation === "broader_narrower") {
    return "上下位概念";
  }
  return "相关但不等价";
}

function summarizeIntegrationStats(
  currentStats: IntegrationResponse["stats"],
  decisions: IntegrationDecision[],
): IntegrationResponse["stats"] {
  return {
    ...currentStats,
    decision_count: decisions.length,
    merge_count: decisions.filter((decision) => decision.action === "merge").length,
    keep_count: decisions.filter((decision) => decision.action === "keep").length,
    remove_count: decisions.filter((decision) => decision.action === "remove").length,
  };
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function citationText(citation: RagCitation) {
  return `[${citation.textbook}, ${citation.chapter}, 第 ${citation.page} 页]`;
}

function sourceChunkTitle(chunk: RagSourceChunk) {
  const pageLabel =
    chunk.page_start === chunk.page_end ? `第 ${chunk.page_start} 页` : `第 ${chunk.page_start}-${chunk.page_end} 页`;
  return `${chunk.textbook} · ${chunk.chapter} · ${pageLabel}`;
}

function colorByFrequency(baseColor: string, frequency: number, maxFrequency: number) {
  const ratio = Math.min(0.34, (frequency / Math.max(maxFrequency, 1)) * 0.34);
  return blendHex(baseColor, "#172033", ratio);
}

function blendHex(from: string, to: string, ratio: number) {
  const start = hexToRgb(from);
  const end = hexToRgb(to);
  if (!start || !end) {
    return from;
  }
  const mixed = start.map((value, index) =>
    Math.round(value + (end[index] - value) * ratio)
      .toString(16)
      .padStart(2, "0"),
  );
  return `#${mixed.join("")}`;
}

function hexToRgb(hex: string) {
  const normalized = hex.replace("#", "");
  if (normalized.length !== 6) {
    return null;
  }
  return [0, 2, 4].map((index) => Number.parseInt(normalized.slice(index, index + 2), 16));
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function readApiError(response: Response, fallback: string) {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (typeof payload.message === "string") {
      return payload.message;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

const CHAT_SESSION_STORAGE_KEY = "medical_knowledge_chat_session_id";
const CHAT_HISTORY_STORAGE_KEY = "medical_knowledge_chat_history";

function getStoredChatSessionId() {
  const stored = window.localStorage.getItem(CHAT_SESSION_STORAGE_KEY);
  if (stored) {
    return stored;
  }
  const sessionId = `session_${window.crypto?.randomUUID?.().replace(/-/g, "").slice(0, 12) ?? Date.now()}`;
  storeChatSessionId(sessionId);
  return sessionId;
}

function storeChatSessionId(sessionId: string) {
  window.localStorage.setItem(CHAT_SESSION_STORAGE_KEY, sessionId);
}

function getStoredChatHistory(): ChatMessage[] {
  const raw = window.localStorage.getItem(CHAT_HISTORY_STORAGE_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isChatMessage);
  } catch {
    return [];
  }
}

function storeChatHistory(history: ChatMessage[]) {
  window.localStorage.setItem(CHAT_HISTORY_STORAGE_KEY, JSON.stringify(history));
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") {
    return false;
  }
  const item = value as Partial<ChatMessage>;
  return (
    typeof item.message_id === "string" &&
    (item.role === "teacher" || item.role === "assistant") &&
    typeof item.content === "string" &&
    typeof item.created_at === "string"
  );
}

function statusLabel(status: TextbookStatus) {
  if (status === "parsing") {
    return "解析中";
  }
  if (status === "failed") {
    return "失败";
  }
  return "已完成";
}

function formatSize(sizeBytes: number) {
  if (sizeBytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = sizeBytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return index === 0 ? `${value} ${units[index]}` : `${value.toFixed(1)} ${units[index]}`;
}

function normalizeApiBase(baseUrl: string) {
  return baseUrl.replace(/\/+$/, "");
}

export default App;
