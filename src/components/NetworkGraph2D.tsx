import { useRef, useCallback, useMemo, useState, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

interface GraphNode {
  id: string;
  label: number;
}

interface GraphEdge {
  source: string;
  target: string;
}

interface NetworkGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  hasCommunity: boolean;
}

// Curated color palette for communities
const COMMUNITY_COLORS = [
  '#6366f1', // Indigo
  '#f43f5e', // Rose
  '#10b981', // Emerald
  '#f59e0b', // Amber
  '#3b82f6', // Blue
  '#ec4899', // Pink
  '#14b8a6', // Teal
  '#8b5cf6', // Violet
  '#ef4444', // Red
  '#06b6d4', // Cyan
  '#84cc16', // Lime
  '#d946ef', // Fuchsia
];

const NEUTRAL_COLOR = '#64748b'; // Slate

// Shared drawing parameters for canvas to boost performance
const LIGHT_MODE_BG = '#f8fafc';

export default function NetworkGraph2D({ nodes, edges, hasCommunity }: NetworkGraphProps) {
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 500 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredNodeObj, setHoveredNodeObj] = useState<any | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  // Observe container size
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width: Math.floor(width), height: Math.floor(Math.max(height, 400)) });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Build graph data for force-graph
  const graphData = useMemo(() => {
    // Calculate degree for each node
    const degreeMap = new Map<string, number>();
    edges.forEach(e => {
      degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1);
      degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1);
    });

    const maxDegree = Math.max(...Array.from(degreeMap.values()), 1);

    return {
      nodes: nodes.map(n => ({
        id: n.id,
        label: n.label,
        degree: degreeMap.get(n.id) || 0,
        normalizedDegree: (degreeMap.get(n.id) || 0) / maxDegree,
        color: hasCommunity
          ? COMMUNITY_COLORS[n.label % COMMUNITY_COLORS.length]
          : NEUTRAL_COLOR,
      })),
      links: edges.map(e => ({
        source: e.source,
        target: e.target,
      })),
    };
  }, [nodes, edges, hasCommunity]);

  // Build neighbor lookup for highlight
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

  const isHighlighted = useCallback((nodeId: string) => {
    if (!selectedNode && !hoveredNode) return true;
    const focusNode = selectedNode || hoveredNode;
    if (nodeId === focusNode) return true;
    return neighborSet.get(focusNode!)?.has(nodeId) || false;
  }, [selectedNode, hoveredNode, neighborSet]);

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(prev => prev === node.id ? null : node.id);

    // Zoom to clicked node smoothly
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 1000);
      graphRef.current.zoom(8, 2000);
    }
  }, []);

  // Optimize physics and appearance based on graph size
  const isLargeGraph = nodes.length > 500;
  
  // Base node size scaler
  const nodeRelSize = useMemo(() => {
    if (nodes.length > 2000) return 2.5;
    if (nodes.length > 500) return 3.5;
    return 5;
  }, [nodes.length]);

  return (
    <div className="graph3d-card">
      <div className="chart-header">
        <h3 className="chart-title">2D Interactive Network</h3>
        <span className="chart-badge chart-badge--info">
          {nodes.length.toLocaleString()} nodes • {edges.length.toLocaleString()} edges
        </span>
      </div>
      <p className="chart-subtitle">
        Pan: drag background • Zoom: scroll • Physics: drag node • Click node to focus
      </p>
      <div className="graph3d-container" ref={containerRef}>
        <ForceGraph2D
          ref={graphRef}
          graphData={graphData}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="rgba(0,0,0,0)"
          
          // Re-enabled physics simulations!
          warmupTicks={isLargeGraph ? 50 : 20}
          cooldownTime={isLargeGraph ? 10000 : 15000}
          enableNodeDrag={true} // Allow users to drag vectors and watch them spring!
          d3AlphaDecay={0.03} // Slower physics settling for better 'spring' visualization

          nodeRelSize={nodeRelSize}
          nodeVal={(node: any) => 1.5 + node.normalizedDegree * 4}
          
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const size = nodeRelSize * Math.cbrt(1.5 + (node.normalizedDegree * 4));
            
            ctx.globalAlpha = 1.0;
            
            // Draw Node Circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = node.color || NEUTRAL_COLOR;
            ctx.fill();

            // Draw polished stroke for nodes
            ctx.lineWidth = 1 / globalScale;
            ctx.strokeStyle = '#ffffff';
            ctx.stroke();
          }}

          linkColor={(link: any) => {
            if (selectedNode || hoveredNode) {
              const srcId = link.source.id || link.source;
              const tgtId = link.target.id || link.target;
              if (isHighlighted(srcId) && isHighlighted(tgtId)) {
                return '#4f46e5'; // bold indigo for highlighted connections
              }
              return 'rgba(148, 163, 184, 0.4)'; // do not dim other links
            }
            return 'rgba(148, 163, 184, 0.4)'; // default link color
          }}
          linkWidth={(link: any) => {
            if (selectedNode || hoveredNode) {
              const srcId = link.source.id || link.source;
              const tgtId = link.target.id || link.target;
              return isHighlighted(srcId) && isHighlighted(tgtId) ? 1.5 : 0.8; // do not shrink other links
            }
            return 0.8; // default link width
          }}
          
          onNodeHover={(node: any) => {
            setHoveredNode(node?.id || null);
            setHoveredNodeObj(node || null);
          }}
          onNodeClick={handleNodeClick}
        />

        {/* Fixed Dashboard Tooltip */}
        {(hoveredNodeObj || selectedNode) && (
          <div style={{
            position: 'absolute',
            bottom: '20px',
            right: '20px',
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(8px)',
            padding: '12px 16px',
            borderRadius: '12px',
            color: '#0f172a',
            fontFamily: "'Inter', sans-serif",
            fontSize: '13px',
            border: '1px solid #e2e8f0',
            boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
            lineHeight: 1.6,
            minWidth: '180px',
            pointerEvents: 'none',
            zIndex: 10
          }}>
            <div style={{ fontWeight: 700, color: hoveredNodeObj?.color || NEUTRAL_COLOR, marginBottom: '6px', fontSize: '14px' }}>
              Node {hoveredNodeObj?.id || selectedNode}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>Community</span>
              <b>{hoveredNodeObj?.label ?? 'N/A'}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748b' }}>Degree</span>
              <b>{hoveredNodeObj?.degree ?? 'N/A'}</b>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      {hasCommunity && (
        <div className="graph3d-legend">
          {Array.from(new Set(nodes.map(n => n.label))).sort().map(label => (
            <div key={label} className="graph3d-legend-item">
              <span
                className="graph3d-legend-dot"
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
