import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  Bot,
  CheckCircle2,
  FileText,
  GitMerge,
  Loader2,
  MessageSquareText,
  Network,
  UploadCloud,
} from "lucide-react";

type TextbookStatus = "uploaded" | "mock_parsed" | "failed";

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

type TabKey = "integration" | "rag" | "chat" | "report";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshTextbooks();
  }, []);

  const uploadedCount = textbooks.filter((item) => item.status !== "failed").length;
  const failedCount = textbooks.filter((item) => item.status === "failed").length;

  const totalSize = useMemo(
    () => textbooks.reduce((sum, item) => sum + item.size_bytes, 0),
    [textbooks],
  );

  async function refreshTextbooks() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/textbooks`);
      if (!response.ok) {
        throw new Error("教材列表读取失败");
      }
      setTextbooks(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法连接后端服务");
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
      const response = await fetch(`${API_BASE_URL}/api/textbooks/upload`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error("上传接口返回异常");
      }
      await refreshTextbooks();
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
          <strong>{isUploading ? "上传中..." : "拖拽或点击上传"}</strong>
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
            textbooks.map((item) => <TextbookCard key={item.textbook_id} item={item} />)
          )}
        </section>
      </aside>

      <section className="graph-stage">
        <div className="stage-toolbar">
          <div>
            <span className="eyebrow">Knowledge Graph</span>
            <h2>知识图谱主视图</h2>
          </div>
          <div className="mock-badge">Stage 1 Mock</div>
        </div>

        <div className="graph-placeholder">
          <div className="graph-grid" />
          <div className="node node-a">教材</div>
          <div className="node node-b">章节</div>
          <div className="node node-c">知识点</div>
          <div className="node node-d">引用</div>
          <svg className="edges" viewBox="0 0 640 420" aria-hidden="true">
            <path d="M170 180 C250 105 340 105 430 170" />
            <path d="M170 180 C265 250 360 265 478 292" />
            <path d="M430 170 C470 200 485 245 478 292" />
          </svg>
        </div>
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

        <PanelContent activeTab={activeTab} textbooks={textbooks} />
      </aside>
    </main>
  );
}

function TextbookCard({ item }: { item: TextbookSummary }) {
  const isFailed = item.status === "failed";

  return (
    <article className={`textbook-card ${isFailed ? "failed" : ""}`}>
      <div className="file-icon">
        {isFailed ? <FileText size={18} aria-hidden="true" /> : <CheckCircle2 size={18} aria-hidden="true" />}
      </div>
      <div className="file-meta">
        <strong title={item.filename}>{item.filename}</strong>
        <span>
          {item.format} · {item.size_label}
        </span>
        <small>{item.message}</small>
      </div>
      <span className={`status-pill ${isFailed ? "failed" : "done"}`}>
        {isFailed ? "失败" : "已解析"}
      </span>
    </article>
  );
}

function PanelContent({
  activeTab,
  textbooks,
}: {
  activeTab: TabKey;
  textbooks: TextbookSummary[];
}) {
  const validBooks = textbooks.filter((item) => item.status !== "failed");

  if (activeTab === "integration") {
    return (
      <section className="panel-body">
        <h2>跨教材整合</h2>
        <div className="metric-row">
          <span>待整合教材</span>
          <strong>{validBooks.length}</strong>
        </div>
        <div className="placeholder-block">整合决策列表将在下一阶段接入。</div>
      </section>
    );
  }

  if (activeTab === "rag") {
    return (
      <section className="panel-body">
        <h2>RAG 问答</h2>
        <div className="status-line">索引状态：未建立</div>
        <textarea placeholder="输入医学教材问题" disabled />
        <button type="button" disabled>
          发送问题
        </button>
      </section>
    );
  }

  if (activeTab === "chat") {
    return (
      <section className="panel-body">
        <h2>教师对话</h2>
        <div className="chat-shell">
          <div className="chat-message">等待整合决策生成后开启反馈。</div>
        </div>
      </section>
    );
  }

  return (
    <section className="panel-body">
      <h2>整合报告</h2>
      <div className="metric-row">
        <span>已上传教材</span>
        <strong>{validBooks.length}</strong>
      </div>
      <div className="placeholder-block">报告统计将在系统完成解析后自动汇总。</div>
    </section>
  );
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

export default App;
