import { useCallback, useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

type KnowledgeNode = {
  id: string;
  name: string;
  definition: string;
  category: string;
  textbook_id: string;
  textbook_title: string;
  chapter: string;
  page: number;
  source_text: string;
  frequency: number;
};

type KnowledgeEdge = {
  id: string;
  source: string;
  target: string;
  relation_type: string;
  confidence: number;
};

type GraphData = {
  textbook_id: string;
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
  total_nodes: number;
  total_edges: number;
};

const CATEGORY_COLORS: Record<string, string> = {
  解剖结构: "#5470C8",
  生理功能: "#91CC75",
  病理变化: "#EE6666",
  微生物: "#FAC858",
  核心概念: "#73C0DE",
};

const RELATION_LABELS: Record<string, string> = {
  prerequisite: "先修",
  parallel: "并行",
  contains: "包含",
  applies_to: "应用于",
};

interface KnowledgeGraphProps {
  textbookId: string | null;
  API_BASE_URL: string;
}

// Normalize base URL by stripping trailing slashes
function normalizeApiBase(baseUrl: string) {
  return baseUrl.replace(/\/+$/, "");
}

export function KnowledgeGraph({ textbookId, API_BASE_URL }: KnowledgeGraphProps) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);

  useEffect(() => {
    if (!textbookId) {
      setGraphData(null);
      setSelectedNode(null);
      return;
    }
    void buildGraph(textbookId);
  }, [textbookId]);

  async function buildGraph(tid: string) {
    setIsLoading(true);
    setError(null);
    setSelectedNode(null);
    try {
      const base = normalizeApiBase(API_BASE_URL);
      const resp = await fetch(`${base}/graph/build?textbook_id=${tid}`, {
        method: "POST",
      });
      if (!resp.ok) {
        throw new Error(`图谱构建失败: ${resp.status}`);
      }
      const data: GraphData = await resp.json();
      setGraphData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "图谱加载失败");
    } finally {
      setIsLoading(false);
    }
  }

  const option = useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) {
      return {};
    }

    const nodes = graphData.nodes.map((n, idx) => {
      const color = CATEGORY_COLORS[n.category] || CATEGORY_COLORS["核心概念"];
      return {
        id: n.id,
        name: n.name,
        category: n.category,
        value: [0, 0, n.frequency],
        x: (idx % 5) * 120 + Math.random() * 60,
        y: Math.floor(idx / 5) * 100 + Math.random() * 40,
        symbolSize: Math.max(30, Math.min(70, n.frequency * 20 + 30)),
        itemStyle: { color },
        label: {
          show: true,
          formatter: n.name.length > 8 ? n.name.slice(0, 7) + "…" : n.name,
          fontSize: 11,
        },
        definition: n.definition,
        source_text: n.source_text,
        textbook_title: n.textbook_title,
        chapter: n.chapter,
        page: n.page,
      };
    });

    const edges = graphData.edges.map((e) => ({
      source: e.source,
      target: e.target,
      label: {
        show: false,
        formatter: RELATION_LABELS[e.relation_type] || e.relation_type,
        fontSize: 9,
      },
      lineStyle: {
        color: "#aaa",
        opacity: 0.6,
        width: 1,
        type: "dotted" as const,
      },
    }));

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const p = params as { data?: { name?: string; definition?: string }; name?: string };
          if (p.data && "definition" in p.data) {
            const d = p.data as { name: string; definition: string };
            return `<b>${d.name}</b><br/>${(d.definition || "").slice(0, 80)}…`;
          }
          return p.name || "";
        },
      },
      animation: true,
      legend: [
        {
          data: Object.keys(CATEGORY_COLORS),
          bottom: 0,
          textStyle: { fontSize: 10 },
        },
      ],
      series: [
        {
          type: "graph",
          layout: "force",
          initLayout: "circular",
          roam: true,
          draggable: true,
          nodeScaleRatio: 0.8,
          label: { show: true, position: "bottom", fontSize: 10 },
          data: nodes,
          links: edges,
          categories: Object.keys(CATEGORY_COLORS).map((name) => ({ name })),
          force: {
            repulsion: { strength: 120, minHeight: 200, maxHeight: 500 },
            edgeLength: [60, 150],
            layoutAnimation: true,
            gravity: 0.1,
          },
          edgeLabel: { show: false },
          lineStyle: { opacity: 0.6, width: 1, type: "dotted" },
        },
      ],
    };
  }, [graphData]);

  const onChartClick = useCallback(
    (params: { data?: Record<string, unknown> }) => {
      if (params.data && "definition" in params.data) {
        setSelectedNode(params.data as unknown as KnowledgeNode);
      }
    },
    [],
  );

  const onChartEvents = {
    click: onChartClick,
  };

  return (
    <div className="knowledge-graph">
      <div className="graph-toolbar">
        <span className="graph-title">知识图谱</span>
        {textbookId && (
          <button
            type="button"
            className="graph-build-btn"
            onClick={() => void buildGraph(textbookId)}
            disabled={isLoading}
          >
            {isLoading ? "构建中…" : "重新构建"}
          </button>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {isLoading && !graphData && (
        <div className="graph-loading">
          <span>知识图谱构建中…</span>
        </div>
      )}

      {graphData && graphData.nodes.length === 0 && (
        <div className="graph-empty">
          <span>当前教材无可视化节点</span>
        </div>
      )}

      {graphData && graphData.nodes.length > 0 && (
        <>
          <div className="graph-stats">
            <span>节点 {graphData.total_nodes}</span>
            <span>边 {graphData.total_edges}</span>
          </div>
          <div className="graph-chart">
            <ReactECharts
              option={option as object}
              style={{ height: "100%", width: "100%" }}
              onEvents={onChartEvents as Record<string, (event: unknown) => void>}
            />
          </div>
        </>
      )}

      {!textbookId && (
        <div className="graph-empty">
          <span>请先选择教材</span>
        </div>
      )}

      {selectedNode && (
        <div className="node-detail">
          <div className="node-detail-header">
            <strong>{selectedNode.name}</strong>
            <span className="node-category">{selectedNode.category}</span>
          </div>
          <p className="node-definition">{selectedNode.definition}</p>
          <div className="node-meta">
            <span>{selectedNode.textbook_title}</span>
            <span>{selectedNode.chapter}</span>
            <span>第 {selectedNode.page} 页</span>
          </div>
          {selectedNode.source_text && (
            <blockquote className="node-source">{selectedNode.source_text.slice(0, 200)}…</blockquote>
          )}
          <button
            type="button"
            className="node-close-btn"
            onClick={() => setSelectedNode(null)}
          >
            关闭
          </button>
        </div>
      )}
    </div>
  );
}