import { useRef, useCallback, useMemo, useState, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

interface GraphNode { id: string; label: number; }
interface GraphEdge { source: string; target: string; }
interface Props { nodes: GraphNode[]; edges: GraphEdge[]; hasCommunity: boolean; }

const COMMUNITY_COLORS = [
  '#6366f1', '#f43f5e', '#10b981', '#f59e0b',
  '#3b82f6', '#ec4899', '#14b8a6', '#8b5cf6',
  '#ef4444', '#06b6d4', '#84cc16', '#d946ef',
];
const NEUTRAL = '#64748b';

export default function NetworkGraph({ nodes, edges, hasCommunity }: Props) {
  const graphRef     = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ width: 600, height: 500 });
  const [hoveredNode,    setHoveredNode]    = useState<string | null>(null);
  const [hoveredNodeObj, setHoveredNodeObj] = useState<any | null>(null);
  const [selectedNode,   setSelectedNode]   = useState<string | null>(null);

  // Responsive sizing
  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(entries => {
      for (const e of entries) {
        const { width, height } = e.contentRect;
        setDims({ width: Math.floor(width), height: Math.floor(Math.max(height, 400)) });
      }
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  const graphData = useMemo(() => {
    const deg = new Map<string, number>();
    edges.forEach(e => {
      deg.set(e.source, (deg.get(e.source) || 0) + 1);
      deg.set(e.target, (deg.get(e.target) || 0) + 1);
    });
    const maxDeg = Math.max(...Array.from(deg.values()), 1);
    return {
      nodes: nodes.map(n => ({
        id: n.id, label: n.label,
        degree: deg.get(n.id) || 0,
        normDeg: (deg.get(n.id) || 0) / maxDeg,
        color: hasCommunity ? COMMUNITY_COLORS[n.label % COMMUNITY_COLORS.length] : NEUTRAL,
      })),
      links: edges.map(e => ({ source: e.source, target: e.target })),
    };
  }, [nodes, edges, hasCommunity]);

  const neighborSet = useMemo(() => {
    const map = new Map<string, Set<string>>();
    edges.forEach(({ source, target }) => {
      if (!map.has(source)) map.set(source, new Set());
      if (!map.has(target)) map.set(target, new Set());
      map.get(source)!.add(target);
      map.get(target)!.add(source);
    });
    return map;
  }, [edges]);

  const isHighlighted = useCallback((id: string) => {
    const focus = selectedNode || hoveredNode;
    if (!focus) return true;
    return id === focus || (neighborSet.get(focus)?.has(id) ?? false);
  }, [selectedNode, hoveredNode, neighborSet]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(prev => prev === node.id ? null : node.id);
    graphRef.current?.centerAt(node.x, node.y, 800);
    graphRef.current?.zoom(8, 1500);
  }, []);

  const nodeRelSize = nodes.length > 2000 ? 2.5 : nodes.length > 500 ? 3.5 : 5;
  const isLarge = nodes.length > 500;

  return (
    <div className="graph-card">
      <div className="chart-header">
        <h3 className="chart-title">Network Graph</h3>
        <span className="chart-badge chart-badge--info">
          {nodes.length.toLocaleString()} nodes · {edges.length.toLocaleString()} edges
        </span>
      </div>
      <p className="chart-subtitle">
        Pan: drag background · Zoom: scroll · Click node to focus
      </p>

      <div className="graph-container" ref={containerRef}>
        <ForceGraph2D
          ref={graphRef}
          graphData={graphData}
          width={dims.width}
          height={dims.height}
          backgroundColor="rgba(0,0,0,0)"
          warmupTicks={isLarge ? 50 : 20}
          cooldownTime={isLarge ? 10000 : 15000}
          enableNodeDrag={true}
          d3AlphaDecay={0.03}
          nodeRelSize={nodeRelSize}
          nodeVal={(n: any) => 1.5 + n.normDeg * 4}
          nodeCanvasObject={(node: any, ctx, gs) => {
            const size = nodeRelSize * Math.cbrt(1.5 + node.normDeg * 4);
            ctx.globalAlpha = 1.0;
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
            ctx.fillStyle = node.color || NEUTRAL;
            ctx.fill();
            ctx.lineWidth = 1 / gs;
            ctx.strokeStyle = '#fff';
            ctx.stroke();
          }}
          linkColor={(link: any) => {
            const s = link.source.id || link.source;
            const t = link.target.id || link.target;
            if ((selectedNode || hoveredNode) && isHighlighted(s) && isHighlighted(t))
              return '#4f46e5';
            return 'rgba(148,163,184,0.4)';
          }}
          linkWidth={(link: any) => {
            const s = link.source.id || link.source;
            const t = link.target.id || link.target;
            return (selectedNode || hoveredNode) && isHighlighted(s) && isHighlighted(t) ? 1.5 : 0.8;
          }}
          onNodeHover={(node: any) => {
            setHoveredNode(node?.id ?? null);
            setHoveredNodeObj(node ?? null);
          }}
          onNodeClick={handleNodeClick}
        />

        {/* Node tooltip */}
        {(hoveredNodeObj || selectedNode) && (
          <div className="graph-tooltip">
            <div className="graph-tooltip-title" style={{ color: hoveredNodeObj?.color || NEUTRAL }}>
              Node {hoveredNodeObj?.id || selectedNode}
            </div>
            <div className="graph-tooltip-row">
              <span>Community</span>
              <b>{hoveredNodeObj?.label ?? '—'}</b>
            </div>
            <div className="graph-tooltip-row">
              <span>Degree</span>
              <b>{hoveredNodeObj?.degree ?? '—'}</b>
            </div>
          </div>
        )}
      </div>

      {/* Community legend */}
      {hasCommunity && (
        <div className="graph-legend">
          {Array.from(new Set(nodes.map(n => n.label))).sort().map(label => (
            <div key={label} className="graph-legend-item">
              <span
                className="graph-legend-dot"
                style={{ background: COMMUNITY_COLORS[label % COMMUNITY_COLORS.length] }}
              />
              <span>Community {label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
