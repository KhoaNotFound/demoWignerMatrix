import { useRef, useCallback, useMemo, useState, useEffect } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';

interface GraphNode {
  id: string;
  label: number;
}

interface GraphEdge {
  source: string;
  target: string;
}

interface NetworkGraph3DProps {
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

// Shared cache and drastically optimized geometry to boost performance for thousands of custom nodes
const sphereGeo = new THREE.SphereGeometry(1, 8, 8);
const materialCache = new Map<string, THREE.Material>();

export default function NetworkGraph3D({ nodes, edges, hasCommunity }: NetworkGraph3DProps) {
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

    // Orbit to clicked node
    if (graphRef.current) {
      const distance = 200;
      const distRatio = 1 + distance / Math.hypot(node.x || 0, node.y || 0, node.z || 0);
      graphRef.current.cameraPosition(
        { x: (node.x || 0) * distRatio, y: (node.y || 0) * distRatio, z: (node.z || 0) * distRatio },
        node,
        1500
      );
    }
  }, []);

  // Performance: adjust based on graph size
  const isLargeGraph = nodes.length > 500;
  const nodeResolution = isLargeGraph ? 6 : 12;
  const warmupTicks = isLargeGraph ? 80 : 30;
  const cooldownTime = isLargeGraph ? 5000 : 15000;

  // Node size based on degree
  const nodeRelSize = useMemo(() => {
    if (nodes.length > 2000) return 2;
    if (nodes.length > 500) return 3;
    return 4;
  }, [nodes.length]);

  const [physicsEnabled, setPhysicsEnabled] = useState(true);

  return (
    <div className="graph3d-card">
      <div className="chart-header">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <h3 className="chart-title">3D Network Visualization</h3>
          <p className="chart-subtitle" style={{ margin: 0 }}>
            Pan: drag background • Zoom: scroll • Orbit: click node
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.875rem', cursor: 'pointer', background: 'var(--bg-secondary)', padding: '6px 12px', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <input 
              type="checkbox" 
              checked={physicsEnabled} 
              onChange={(e) => setPhysicsEnabled(e.target.checked)} 
              style={{ cursor: 'pointer' }}
            />
            <b>Live Physics</b>
          </label>
          <span className="chart-badge chart-badge--info">
            {nodes.length.toLocaleString()} nodes • {edges.length.toLocaleString()} edges
          </span>
        </div>
      </div>
      <div className="graph3d-container" ref={containerRef}>
        <ForceGraph3D
          ref={graphRef}
          graphData={graphData}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="rgba(0,0,0,0)"
          nodeRelSize={nodeRelSize}
          nodeVal={(node: any) => 1.5 + node.normalizedDegree * 4}
          nodeThreeObject={(node: any) => {
            const colorStr = node.color || NEUTRAL_COLOR;
            const opacityLevel = 1.0; // Remove dimming effect entirely
            
            // Generate a cache key that includes opacity state
            const cacheKey = `${colorStr}_${opacityLevel}`;
            
            let material = materialCache.get(cacheKey);
            if (!material) {
              material = new THREE.MeshPhysicalMaterial({
                color: colorStr,
                transparent: false,
                opacity: opacityLevel,
                metalness: 0.15,
                roughness: 0.15, 
                clearcoat: 1.0, 
                clearcoatRoughness: 0.1,
              });
              materialCache.set(cacheKey, material);
            }

            const size = 1.5 + (node.normalizedDegree * 4);
            const scale = nodeRelSize * Math.cbrt(size); 
            
            const mesh = new THREE.Mesh(sphereGeo, material);
            mesh.scale.set(scale, scale, scale);
            return mesh;
          }}
          linkColor={(link: any) => {
            if (selectedNode || hoveredNode) {
              const srcId = link.source.id || link.source;
              const tgtId = link.target.id || link.target;
              if (isHighlighted(srcId) && isHighlighted(tgtId)) {
                return '#4f46e5'; // bold indigo for highlighted connections
              }
              return 'rgba(148, 163, 184, 0.4)'; // Do not fade out other links
            }
            return 'rgba(148, 163, 184, 0.4)'; // default link color
          }}
          linkWidth={(link: any) => {
            if (selectedNode || hoveredNode) {
              const srcId = link.source.id || link.source;
              const tgtId = link.target.id || link.target;
              return isHighlighted(srcId) && isHighlighted(tgtId) ? 1.0 : 0.6; // No shrinkage
            }
            return 0.6; // default link width
          }}
          rendererConfig={{ powerPreference: "high-performance", antialias: false }}
          linkOpacity={0.8}
          onNodeHover={(node: any) => {
            setHoveredNode(node?.id || null);
            setHoveredNodeObj(node || null);
          }}
          onNodeClick={handleNodeClick}
          warmupTicks={isLargeGraph ? 150 : 50}
          cooldownTime={physicsEnabled ? 15000 : 0} // Support live toggle
          cooldownTicks={physicsEnabled ? Infinity : 0} 
          enableNodeDrag={physicsEnabled}
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
