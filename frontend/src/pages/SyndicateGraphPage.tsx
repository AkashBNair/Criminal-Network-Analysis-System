import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import cytoscape from 'cytoscape'
import {
  Search, Filter, TrendingUp, Route, X, Target, Network,
  Layers, Download, ArrowLeft
} from 'lucide-react'

const NODE_COLORS: Record<string, string> = {
  Person: '#00e5ff',
  Phone: '#8b5cf6',
  Vehicle: '#f59e0b',
  Organization: '#ec4899',
  Location: '#22c55e',
  Event: '#6b7280',
}

const REL_COLORS: Record<string, string> = {
  Communication: '#00e5ff',
  'Financial Transaction': '#3de87a',
  Family: '#ffc23d',
  'Co-accused': '#ff3d71',
  Associate: '#8b5cf6',
  Employment: '#0891b2',
  Ownership: '#f97316',
  'Location Presence': '#22c55e',
}

export default function SyndicateGraphPage() {
  const navigate = useNavigate()
  const cyRef = useRef<HTMLDivElement>(null)
  const cyInstance = useRef<cytoscape.Core | null>(null)

  const [cases, setCases] = useState<any[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([])
  const [graphData, setGraphData] = useState<any>(null)
  const [centrality, setCentrality] = useState<any[]>([])
  const [selectedNode, setSelectedNode] = useState<any>(null)
  const [selectedEdge, setSelectedEdge] = useState<any>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [showTopInfluencers, setShowTopInfluencers] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [showPathFinder, setShowPathFinder] = useState(false)
  const [showCaseSelector, setShowCaseSelector] = useState(true)
  const [pathSource, setPathSource] = useState('')
  const [pathTarget, setPathTarget] = useState('')
  const [pathResult, setPathResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [exportingPng, setExportingPng] = useState(false)
  const [filters, setFilters] = useState({ entityType: '', relationshipType: '' })

  useEffect(() => { api.getCases().then(setCases).catch(console.error) }, [])

  const loadGraph = async () => {
    if (selectedCaseIds.length === 0) return
    try {
      setLoading(true)
      const params: Record<string, string> = {}
      if (filters.entityType) params.entity_type = filters.entityType
      if (filters.relationshipType) params.relationship_type = filters.relationshipType

      const [graph, cent] = await Promise.all([
        selectedCaseIds.length === 1
          ? api.getGraph(selectedCaseIds[0], params)
          : api.getMultiCaseGraph(selectedCaseIds, params),
        selectedCaseIds.length === 1
          ? api.getCentrality(selectedCaseIds[0])
          : api.getMultiCentrality(selectedCaseIds),
      ])
      setGraphData(graph)
      setCentrality(cent)
      setShowCaseSelector(false)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!cyRef.current || !graphData) return
    if (cyInstance.current) cyInstance.current.destroy()

    const elements: cytoscape.ElementDefinition[] = [
      ...graphData.nodes.map((n: any) => ({
        data: {
          id: n.data.id, label: n.data.label, entity_type: n.data.type,
          confidence: n.data.confidence, attributes: n.data.attributes,
        },
      })),
      ...graphData.edges.map((e: any) => ({
        data: {
          id: e.data.id, source: e.data.source, target: e.data.target,
          label: e.data.label, weight: e.data.weight,
        },
      })),
    ]

    const isCrossCase = (nodeId: string) => {
      const centData = centrality.find((c: any) => c.entity_id === nodeId)
      return centData && centData.cases_count > 1
    }

    const cy = cytoscape({
      container: cyRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: any) => NODE_COLORS[ele.data('entity_type')] || '#6b7280',
            label: 'data(label)',
            'font-size': '9px',
            "font-family": "'JetBrains Mono', monospace",
            color: '#e2e8f0',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            width: (ele: any) => {
              const isCross = isCrossCase(ele.id())
              if (ele.data('entity_type') === 'Person') return isCross ? 40 : 28
              return isCross ? 24 : 18
            },
            height: (ele: any) => {
              const isCross = isCrossCase(ele.id())
              if (ele.data('entity_type') === 'Person') return isCross ? 40 : 28
              return isCross ? 24 : 18
            },
            'border-width': (ele: any) => isCrossCase(ele.id()) ? 3 : 1.5,
            'border-color': (ele: any) => isCrossCase(ele.id()) ? '#ff8a3d' : 'rgba(0, 229, 255, 0.25)',
            'text-outline-width': 1.5,
            'text-outline-color': '#07090e',
            'z-index': (ele: any) => isCrossCase(ele.id()) ? 100 : 10,
          } as any,
        },
        {
          selector: 'node.cross-case',
          style: {
            'border-width': 3,
            'border-color': '#ff8a3d',
            'z-index': 100,
          },
        },
        { selector: 'node.highlighted', style: { width: 44, height: 44, 'border-width': 3, 'border-color': '#ffc23d', 'z-index': 999 } },
        { selector: 'node.path-node', style: { 'background-color': '#ff3d71', width: 36, height: 36, 'border-width': 3, 'border-color': '#ff6b91' } },
        { selector: 'node.dimmed', style: { opacity: 0.08 } },
        {
          selector: 'edge',
          style: {
            width: (ele: any) => Math.max(0.5, Math.min((ele.data('weight') || 1) * 0.8, 5)),
            'line-color': (ele: any) => REL_COLORS[ele.data('label')] || 'rgba(139, 148, 158, 0.2)',
            'target-arrow-color': (ele: any) => REL_COLORS[ele.data('label')] || 'rgba(139, 148, 158, 0.2)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            opacity: 0.35,
            label: '',
            'font-size': '8px',
            "font-family": "'JetBrains Mono', monospace",
            color: 'rgba(139, 148, 158, 0.6)',
          } as any,
        },
        {
          selector: 'edge:active',
          style: {
            opacity: 1,
            label: 'data(label)',
            'font-size': '9px',
          },
        },
        { selector: 'edge.path-edge', style: { width: 4, 'line-color': '#ff3d71', opacity: 1, 'z-index': 999 } },
        { selector: 'edge.dimmed', style: { opacity: 0.04 } },
      ],
      layout: {
        name: 'cose', animate: true, animationDuration: 1000,
        nodeRepulsion: () => 12000, idealEdgeLength: () => 160,
        gravity: 0.25, numIter: 400,
      } as any,
      minZoom: 0.05,
      maxZoom: 5,
    })

    cy.on('tap', 'node', (evt: any) => {
      const n = evt.target
      setSelectedNode({
        id: n.id(), label: n.data('label'), entity_type: n.data('entity_type'),
        confidence: n.data('confidence'), attributes: n.data('attributes'),
      })
      setSelectedEdge(null)
    })
    cy.on('tap', 'edge', (evt: any) => {
      const e = evt.target
      setSelectedEdge({
        id: e.id(), label: e.data('label'), weight: e.data('weight'),
        source: e.data('source'), target: e.data('target'),
      })
      setSelectedNode(null)
    })
    cy.on('tap', (evt: any) => { if (evt.target === cy) { setSelectedNode(null); setSelectedEdge(null) } })

    cyInstance.current = cy
    return () => { if (cyInstance.current) { cyInstance.current.destroy(); cyInstance.current = null } }
  }, [graphData, centrality])

  // Search
  useEffect(() => {
    if (!cyInstance.current || !searchTerm) { if (cyInstance.current) cyInstance.current.elements().removeClass('dimmed highlighted'); return }
    const cy = cyInstance.current
    cy.elements().addClass('dimmed')
    cy.nodes().forEach((node) => {
      if (node.data('label').toLowerCase().includes(searchTerm.toLowerCase())) {
        node.removeClass('dimmed').addClass('highlighted')
        node.connectedEdges().removeClass('dimmed')
        node.neighborhood('node').removeClass('dimmed')
      }
    })
  }, [searchTerm])

  // Top influencers
  useEffect(() => {
    if (!cyInstance.current) return
    const cy = cyInstance.current
    if (showTopInfluencers) {
      const topIds = new Set(centrality.slice(0, 10).map((c: any) => c.entity_id))
      cy.nodes().forEach((node) => { topIds.has(node.id()) ? node.addClass('highlighted') : node.addClass('dimmed') })
      cy.edges().addClass('dimmed')
    } else {
      cy.elements().removeClass('dimmed highlighted')
    }
  }, [showTopInfluencers, centrality])

  const handleFindPath = async () => {
    if (!pathSource || !pathTarget) return
    try {
      const sourceEntity = centrality.find((c: any) => c.name.toLowerCase().includes(pathSource.toLowerCase()))
      const targetEntity = centrality.find((c: any) => c.name.toLowerCase().includes(pathTarget.toLowerCase()))
      if (!sourceEntity || !targetEntity) { alert('Entity not found.'); return }
      const result = await api.findPath(sourceEntity.entity_id, targetEntity.entity_id)
      setPathResult(result)
      if (cyInstance.current) {
        const cy = cyInstance.current
        cy.elements().addClass('dimmed')
        const pathNodeIds = result.path.map((p: any) => p.entity_id)
        cy.nodes().forEach((node) => { if (pathNodeIds.includes(node.id())) node.removeClass('dimmed').addClass('path-node') })
        cy.edges().forEach((edge) => {
          const src = edge.data('source'), tgt = edge.data('target')
          if (pathNodeIds.includes(src) && pathNodeIds.includes(tgt)) {
            const i1 = pathNodeIds.indexOf(src), i2 = pathNodeIds.indexOf(tgt)
            if (Math.abs(i1 - i2) === 1) edge.removeClass('dimmed').addClass('path-edge')
          }
        })
      }
    } catch (err: any) { alert(err.message || 'No path found') }
  }

  const handleExportPng = useCallback(() => {
    if (!cyInstance.current) return
    setExportingPng(true)
    try {
      cyInstance.current.fit(undefined, 30)
      const png = cyInstance.current.png({ bg: '#07090e', full: true, scale: 2, maxWidth: 2800, maxHeight: 2000 })
      const link = document.createElement('a')
      link.download = `syndicate-graph-${new Date().toISOString().slice(0, 10)}.png`
      link.href = png
      link.click()
    } finally { setExportingPng(false) }
  }, [])

  return (
    <div className="h-[calc(100vh-7rem)] flex flex-col animate-fade-in">
      {/* Toolbar */}
      <div className="ops-panel rounded-b-none px-4 py-2 flex items-center gap-3 flex-wrap border-b-0 rounded-t-xl">
        <button onClick={() => navigate('/')} className="btn-ops" style={{ padding: '6px 8px' }}>
          <ArrowLeft size={14} />
        </button>
        <div className="flex items-center gap-1.5 text-xs font-semibold tracking-wider" style={{ color: 'var(--ops-accent)' }}>
          <Network size={14} />
          SYNDICATE GRAPH
        </div>

        <div className="relative flex-1 max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ops-text-muted)' }} />
          <input type="text" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search nodes..."
            className="input-ops" />
        </div>

        <button onClick={() => setShowCaseSelector(!showCaseSelector)}
          className={`btn-ops ${showCaseSelector ? 'active' : ''}`}>
          <Layers size={13} /> Cases ({selectedCaseIds.length})
        </button>
        <button onClick={() => setShowFilters(!showFilters)}
          className={`btn-ops ${showFilters ? 'active' : ''}`}>
          <Filter size={13} /> Filters
        </button>
        <button onClick={() => setShowTopInfluencers(!showTopInfluencers)}
          className={`btn-ops ${showTopInfluencers ? 'active' : ''}`}>
          <TrendingUp size={13} /> Top Influencers
        </button>
        <button onClick={() => setShowPathFinder(!showPathFinder)}
          className={`btn-ops ${showPathFinder ? 'active' : ''}`}>
          <Route size={13} /> Find Path
        </button>
        <button onClick={handleExportPng} disabled={exportingPng || !graphData}
          className="btn-ops disabled:opacity-30">
          <Download size={13} /> {exportingPng ? 'Saving...' : 'PNG'}
        </button>

        <div className="text-[10px] ml-auto" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
          {graphData?.node_count || 0}N • {graphData?.edge_count || 0}E
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden border-x border-b rounded-b-xl" style={{ borderColor: 'var(--ops-border)' }}>
        {/* Case selector */}
        {showCaseSelector && (
          <div className="w-72 p-4 overflow-auto border-r animate-slide-left" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <h3 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>
              SELECT CASES FOR MACRO ANALYSIS
            </h3>
            <div className="space-y-1.5 mb-4">
              {cases.map(c => (
                <label key={c.id} className="flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors"
                  style={{ background: selectedCaseIds.includes(c.id) ? 'var(--ops-accent-bg)' : 'transparent' }}>
                  <input type="checkbox" checked={selectedCaseIds.includes(c.id)}
                    onChange={() => setSelectedCaseIds(prev => prev.includes(c.id) ? prev.filter(x => x !== c.id) : [...prev, c.id])}
                    className="checkbox-ops" />
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium truncate" style={{ color: 'var(--ops-text-primary)' }}>{c.name}</p>
                    <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{c.case_number}</p>
                  </div>
                </label>
              ))}
            </div>
            <button onClick={loadGraph} disabled={selectedCaseIds.length === 0 || loading}
              className="btn-ops-primary w-full py-2.5 rounded-lg text-xs font-semibold tracking-wider">
              {loading ? 'LOADING...' : 'LOAD MACRO GRAPH'}
            </button>
          </div>
        )}

        {/* Filters */}
        {showFilters && (
          <div className="w-56 p-4 overflow-auto border-r animate-slide-left" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <h3 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>FILTERS</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-[9px] font-semibold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>NODE TYPE</label>
                <select value={filters.entityType} onChange={(e) => setFilters({ ...filters, entityType: e.target.value })}
                  className="select-ops w-full">
                  <option value="">All Types</option>
                  {Object.keys(NODE_COLORS).map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[9px] font-semibold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>EDGE TYPE</label>
                <select value={filters.relationshipType} onChange={(e) => setFilters({ ...filters, relationshipType: e.target.value })}
                  className="select-ops w-full">
                  <option value="">All Types</option>
                  {Object.keys(REL_COLORS).map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <button onClick={() => setFilters({ entityType: '', relationshipType: '' })}
                className="text-[10px]" style={{ color: 'var(--ops-accent-dim)' }}>Clear Filters</button>
            </div>

            <div className="mt-6">
              <h4 className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>LEGEND</h4>
              <div className="space-y-1.5">
                {Object.entries(NODE_COLORS).map(([type, color]) => (
                  <div key={type} className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: color, boxShadow: `0 0 6px ${color}40` }} />
                    <span className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>{type}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Path finder */}
        {showPathFinder && (
          <div className="w-64 p-4 overflow-auto border-r animate-slide-left" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[10px] font-bold tracking-wider" style={{ color: 'var(--ops-text-secondary)' }}>FIND PATH</h3>
              <button onClick={() => { setPathResult(null); cyInstance.current?.elements().removeClass('dimmed path-node path-edge') }}>
                <X size={12} style={{ color: 'var(--ops-text-muted)' }} />
              </button>
            </div>
            <div className="space-y-3">
              <input type="text" value={pathSource} onChange={(e) => setPathSource(e.target.value)}
                placeholder="Source entity" className="input-ops" style={{ paddingLeft: 12 }} />
              <input type="text" value={pathTarget} onChange={(e) => setPathTarget(e.target.value)}
                placeholder="Target entity" className="input-ops" style={{ paddingLeft: 12 }} />
              <button onClick={handleFindPath} className="btn-ops-primary w-full py-2 rounded-lg text-[11px] font-semibold">
                <Target size={12} /> FIND PATH
              </button>
              {pathResult && (
                <div className="rounded-lg p-3 mt-3" style={{ background: 'var(--ops-critical-bg)', border: '1px solid rgba(255, 61, 113, 0.2)' }}>
                  <p className="text-[10px] font-bold mb-2" style={{ color: 'var(--ops-critical)' }}>
                    PATH: {pathResult.hops} HOPS
                  </p>
                  <div className="space-y-1">
                    {pathResult.path.map((p: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 text-[10px]">
                        <span style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{i}.</span>
                        <span className="font-medium" style={{ color: 'var(--ops-text-primary)' }}>{p.name}</span>
                        {p.edge_to_next && <span style={{ color: 'var(--ops-critical)' }}>→ {p.edge_to_next.relationship_type}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Graph canvas */}
        <div className="flex-1 relative" style={{ background: 'var(--ops-bg-void)' }}>
          <div ref={cyRef} className="w-full h-full" />
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(7, 9, 14, 0.8)' }}>
              <div className="text-center">
                <div className="loading-spinner mx-auto mb-3" />
                <p className="text-[10px] tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>MAPPING NETWORK...</p>
              </div>
            </div>
          )}
          {graphData && graphData.node_count === 0 && !loading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <Network size={40} style={{ color: 'var(--ops-text-muted)', opacity: 0.2 }} />
                <p className="text-xs mt-3" style={{ color: 'var(--ops-text-muted)' }}>Select cases to load the macro syndicate graph.</p>
              </div>
            </div>
          )}
        </div>

        {/* Detail panel */}
        {(selectedNode || selectedEdge) && (
          <div className="w-72 p-4 overflow-auto border-l animate-slide-right" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            {selectedNode && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-3 h-3 rounded-full" style={{ background: NODE_COLORS[selectedNode.entity_type] || '#6b7280' }} />
                  <h3 className="text-xs font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{selectedNode.label}</h3>
                </div>
                <div className="space-y-2 text-[11px]">
                  <div className="flex justify-between">
                    <span style={{ color: 'var(--ops-text-muted)' }}>Type</span>
                    <span className="font-medium" style={{ color: 'var(--ops-text-primary)' }}>{selectedNode.entity_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ color: 'var(--ops-text-muted)' }}>Confidence</span>
                    <span className="font-mono font-medium" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {((selectedNode.confidence || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                <button onClick={() => navigate(`/entities/${selectedNode.id}`)}
                  className="btn-ops-primary w-full mt-4 py-2 rounded-lg text-[11px] font-semibold text-center">
                  VIEW FULL PROFILE
                </button>
              </div>
            )}
            {selectedEdge && (
              <div>
                <h3 className="text-xs font-semibold mb-3" style={{ color: 'var(--ops-text-primary)' }}>Relationship</h3>
                <div className="space-y-2 text-[11px]">
                  <div className="flex justify-between">
                    <span style={{ color: 'var(--ops-text-muted)' }}>Type</span>
                    <span className="font-medium" style={{ color: 'var(--ops-text-primary)' }}>{selectedEdge.label}</span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ color: 'var(--ops-text-muted)' }}>Weight</span>
                    <span className="font-mono" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {selectedEdge.weight?.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Top influencers panel */}
        {showTopInfluencers && !selectedNode && (
          <div className="w-64 p-4 overflow-auto border-l animate-slide-right" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <h3 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>
              TOP INFLUENCERS
            </h3>
            <div className="space-y-1">
              {centrality.slice(0, 15).map((c: any, i: number) => (
                <div key={c.entity_id}
                  className="flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors"
                  style={{ background: 'transparent' }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(0, 229, 255, 0.04)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                  onClick={() => {
                    const node = cyInstance.current?.getElementById(c.entity_id)
                    if (node) { cyInstance.current?.animate({ center: { eles: node }, zoom: 1.5 } as any, { duration: 300 }) }
                  }}>
                  <span className="text-[9px] font-bold w-4" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium truncate" style={{ color: 'var(--ops-text-primary)' }}>{c.name}</p>
                    <p className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>{c.entity_type} • {c.connections} links</p>
                  </div>
                  <span className="text-[10px] font-bold" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>
                    {c.combined_score?.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
