import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  BarChart3,
  BookOpenText,
  Bot,
  CheckCircle2,
  GitMerge,
  Loader2,
  MessageSquareText,
  Network,
  UploadCloud,
} from "lucide-react";
import { KnowledgeGraph } from "./KnowledgeGraph";

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

type TabKey = "integration" | "rag" | "chat" | "report";

const API_BASE_URL = normalizeApiBase(import.meta.env.VITE_API_BASE_URL || "/api");

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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshTextbooks().then((items) => {
      const firstParsed = items.find((item) => item.status === "parsed");
      if (firstParsed) {
        void selectTextbook(firstParsed.textbook_id);
      }
    });
  }, []);

  const uploadedCount = textbooks.filter((item) => item.status === "parsed").length;
  const failedCount = textbooks.filter((item) => item.status === "failed").length;

  const totalSize = useMemo(
    () => textbooks.reduce((sum, item) => sum + item.size_bytes, 0),
    [textbooks],
  );

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
            <h2>{selectedTextbook ? selectedTextbook.title : "知识图谱"}</h2>
          </div>
          <div className="mock-badge">Stage 3</div>
        </div>

        <KnowledgeGraph textbookId={selectedTextbookId} API_BASE_URL={API_BASE_URL} />
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

function ParserStage({
  textbook,
  isLoading,
}: {
  textbook: TextbookDetail | null;
  isLoading: boolean;
}) {
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
        <span>上传 PDF、Markdown 或 TXT 后，这里会展示章节列表。</span>
      </div>
    );
  }

  return (
    <div className="parser-result">
      <section className="detail-summary" aria-label="解析统计">
        <div>
          <span>解析状态</span>
          <strong>{statusLabel(textbook.status)}</strong>
        </div>
        <div>
          <span>总页数</span>
          <strong>{textbook.total_pages || "-"}</strong>
        </div>
        <div>
          <span>总字数</span>
          <strong>{textbook.total_chars}</strong>
        </div>
        <div>
          <span>章节数</span>
          <strong>{textbook.chapter_count}</strong>
        </div>
      </section>

      {textbook.status === "failed" ? (
        <div className="error-banner">{textbook.message}</div>
      ) : (
        <section className="chapter-list" aria-label="章节列表">
          {textbook.chapters.length === 0 ? (
            <div className="empty-list">暂无章节</div>
          ) : (
            textbook.chapters.map((chapter) => (
              <article className="chapter-card" key={chapter.chapter_id}>
                <header>
                  <div>
                    <span>{chapter.chapter_id}</span>
                    <h3>{chapter.title}</h3>
                  </div>
                  <strong>
                    {chapter.page_start === chapter.page_end
                      ? `第 ${chapter.page_start} 页`
                      : `第 ${chapter.page_start}-${chapter.page_end} 页`}
                  </strong>
                </header>
                <p>{chapter.content ? chapter.content.slice(0, 260) : "未提取到正文"}</p>
                <footer>{chapter.char_count} 字</footer>
              </article>
            ))
          )}
        </section>
      )}
    </div>
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
