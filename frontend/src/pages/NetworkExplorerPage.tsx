import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import cytoscape from 'cytoscape'
import { useCrossGraph } from '../context/CrossGraphContext'
import {
  ArrowLeft, Search, Filter, TrendingUp, Route,
  X, Target, Network, Layers, Users, Download, MapPin, Zap, Activity
} from 'lucide-react'

const PEOPLE_COLORS: Record<string, string> = {
  Person: '#00e5ff',
  Phone: '#8b5cf6',
  Vehicle: '#f59e0b',
  Organization: '#ec4899',
  Event: '#6b7280',
  Location: '#10b981',
}

const REL_COLORS: Record<string, string> = {
  Communication: '#00e5ff',
  'Financial Transaction': '#3de87a',
  Family: '#ffc23d',
  'Co-accused': '#ff3d71',
  Associate: '#8b5cf6',
  Employment: '#0891b2',
  Ownership: '#f97316',
}

function CentralityBadge({ score }: { score: number }) {
  let color = '#64748b', label = 'LOW'
  if (score >= 0.7) { color = '#ff3d71'; label = 'CRITICAL' }
  else if (score >= 0.4) { color = '#f59e0b'; label = 'HIGH' }
  else if (score >= 0.2) { color = '#00e5ff'; label = 'MEDIUM' }
  return (
    <span className="badge-ops" style={{ background: `${color}18`, color, fontSize: 8, fontWeight: 700, letterSpacing: '0.05em' }}>{label}</span>
  )
}

export default function NetworkExplorerPage() {
  const { caseId } = useParams()
  const navigate = useNavigate()
  const cyRef = useRef<HTMLDivElement>(null)
  const cyInstance = useRef<cytoscape.Core | null>(null)
  const { highlightSuspect } = useCrossGraph()

  const [cases, setCases] = useState<any[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([])
  const [multiMode, setMultiMode] = useState(!caseId)
  const [graphData, setGraphData] = useState<any>(null)
  const [centrality, setCentrality] = useState<any[]>([])
  const [selectedNode, setSelectedNode] = useState<any>(null)
  const [selectedEdge, setSelectedEdge] = useState<any>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [showTopInfluencers, setShowTopInfluencers] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [showPathFinder, setShowPathFinder] = useState(false)
  const [showCaseSelector, setShowCaseSelector] = useState(false)
  const [pathSource, setPathSource] = useState('')
  const [pathTarget, setPathTarget] = useState('')
  const [pathResult, setPathResult] = useState<any>(null)
  const [loading, setLoading] = useState(!!caseId)
  const [exportingPng, setExportingPng] = useState(false)
  const [filters, setFilters] = useState({ entityType: '', relationshipType: '', minConfidence: 0 })
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)

  useEffect(() => { api.getCases().then(setCases).catch(console.error) }, [])

  useEffect(() => {
    if (caseId) { setMultiMode(false); loadGraph() } else { setMultiMode(true); setLoading(false) }
  }, [caseId, filters])

  const loadGraph = async () => {
    try {
      setLoading(true)
      const params: Record<string, string> = {}
      if (filters.entityType) params.entity_type = filters.entityType
      if (filters.relationshipType) params.relationship_type = filters.relationshipType
      if (filters.minConfidence > 0) params.min_confidence = String(filters.minConfidence)
      const [graph, centRaw] = await Promise.all([api.getPeopleGraph(caseId!, params), api.getCentrality(caseId!)])
      setGraphData(graph)
      const centList = Array.isArray(centRaw) ? centRaw : Object.entries(centRaw).map(([id, data]: [string, any]) => ({ entity_id: id, name: data.name || id, ...data }))
      setCentrality(centList)
    } catch (err) { console.error(err) } finally { setLoading(false) }
  }

  const loadMultiCaseGraph = async () => {
    if (selectedCaseIds.length === 0) return
    try {
      setLoading(true)
      const params: Record<string, string> = {}
      if (filters.entityType) params.entity_type = filters.entityType
      if (filters.relationshipType) params.relationship_type = filters.relationshipType
      if (filters.minConfidence > 0) params.min_confidence = String(filters.minConfidence)
      const [graph, centRaw] = await Promise.all([api.getMultiPeopleGraph(selectedCaseIds, params), api.getMultiCentrality(selectedCaseIds)])
      setGraphData(graph)
      // Handle both dict (node_id->data) and list formats from centrality API
      const centList = Array.isArray(centRaw) ? centRaw : Object.entries(centRaw).map(([id, data]: [string, any]) => ({ entity_id: id, name: data.name || id, ...data }))
      setCentrality(centList)
    } catch (err) { console.error(err) } finally { setLoading(false) }
  }

  const handleLoadMultiCase = () => { if (selectedCaseIds.length === 0) { alert('Select at least one case'); return } setShowCaseSelector(false); loadMultiCaseGraph() }

  useEffect(() => {
    if (!cyRef.current || !graphData) return
    if (cyInstance.current) cyInstance.current.destroy()

    const centralityMap = new Map(centrality.map((c: any) => [c.entity_id, c]))

    const elements: cytoscape.ElementDefinition[] = [
      ...graphData.nodes.map((n: any) => {
        const cent = centralityMap.get(n.data.id)
        const score = cent?.combined_score || 0
        const isHigh = score >= 0.4
        return {
          data: { id: n.data.id, label: n.data.label, entity_type: n.data.type, confidence: n.data.confidence, is_ai: n.data.is_ai, attributes: n.data.attributes, centrality_score: score },
          classes: isHigh ? 'high-centrality' : '',
        }
      }),
      ...graphData.edges.map((e: any) => ({ data: { id: e.data.id, source: e.data.source, target: e.data.target, label: e.data.label, weight: e.data.weight } })),
    ]

    const cy = cytoscape({
      container: cyRef.current, elements,
      style: [
        {
          selector: 'node', style: {
            'background-color': (ele: any) => PEOPLE_COLORS[ele.data('entity_type')] || '#6b7280',
            label: 'data(label)',
            'font-size': '10px',
            "font-family": "'JetBrains Mono', monospace",
            color: '#e2e8f0',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            width: (ele: any) => {
              const score = ele.data('centrality_score') || 0
              if (ele.data('entity_type') === 'Person') return 28 + score * 30
              return 18
            },
            height: (ele: any) => {
              const score = ele.data('centrality_score') || 0
              if (ele.data('entity_type') === 'Person') return 28 + score * 30
              return 18
            },
            'border-width': (ele: any) => ele.data('entity_type') === 'Person' ? 2 : 1,
            'border-color': (ele: any) => {
              const score = ele.data('centrality_score') || 0
              if (score >= 0.7) return '#ff3d71'
              if (score >= 0.4) return '#f59e0b'
              return 'rgba(0, 229, 255, 0.25)'
            },
            'text-outline-width': 2,
            'text-outline-color': '#07090e',
          } as any
        },
        {
          selector: 'node.high-centrality', style: {
            'overlay-opacity': 0.08,
            'overlay-color': (ele: any) => {
              const score = ele.data('centrality_score') || 0
              return score >= 0.7 ? '#ff3d71' : '#f59e0b'
            },
          } as any
        },
        { selector: 'node.highlighted', style: { width: 42, height: 42, 'border-width': 3, 'border-color': '#ffc23d', 'z-index': 999, 'font-size': '12px' } },
        { selector: 'node.path-node', style: { 'background-color': '#ff3d71', width: 36, height: 36, 'border-width': 3, 'border-color': '#ff6b91' } },
        { selector: 'node.dimmed', style: { opacity: 0.06 } },
        { selector: 'node.hovered', style: { 'border-width': 3, 'border-color': '#ffc23d', width: 38, height: 38 } },
        {
          selector: 'edge', style: {
            width: (ele: any) => Math.max(0.8, Math.min((ele.data('weight') || 1) * 1.5, 5)),
            'line-color': (ele: any) => REL_COLORS[ele.data('label')] || 'rgba(139, 148, 158, 0.3)',
            'target-arrow-color': (ele: any) => REL_COLORS[ele.data('label')] || 'rgba(139, 148, 158, 0.3)',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 0.8,
            'curve-style': 'bezier',
            opacity: 0.4,
            label: '',
            'font-size': '9px',
            "font-family": "'JetBrains Mono', monospace",
            color: 'rgba(139, 148, 158, 0.7)',
            'text-background-color': '#07090e',
            'text-background-opacity': 0.8,
            'text-background-padding': '3px',
          } as any
        },
        { selector: 'edge:active', style: { opacity: 1, label: 'data(label)', 'font-size': '10px', width: 4 } },
        { selector: 'edge.path-edge', style: { width: 4, 'line-color': '#ff3d71', opacity: 1, 'z-index': 999, 'target-arrow-color': '#ff3d71' } },
        { selector: 'edge.dimmed', style: { opacity: 0.03 } },
      ],
      layout: { name: 'cose', animate: true, animationDuration: 1000, nodeRepulsion: () => 10000, idealEdgeLength: () => 140, gravity: 0.25, numIter: 400, coolingFactor: 0.95 } as any,
      minZoom: 0.1, maxZoom: 4,
    })

    cy.on('tap', 'node', (evt: any) => {
      const n = evt.target
      setSelectedNode({ id: n.id(), label: n.data('label'), entity_type: n.data('entity_type'), confidence: n.data('confidence'), is_ai: n.data('is_ai'), attributes: n.data('attributes'), centrality_score: n.data('centrality_score') })
      setSelectedEdge(null)
      // Highlight neighbors
      cy.elements().removeClass('dimmed highlighted')
      const neighborhood = n.closedNeighborhood()
      cy.elements().addClass('dimmed')
      neighborhood.removeClass('dimmed')
      n.addClass('highlighted')
    })
    cy.on('tap', 'edge', (evt: any) => {
      const e = evt.target
      setSelectedEdge({ id: e.id(), label: e.data('label'), weight: e.data('weight'), source: e.data('source'), target: e.data('target') })
      setSelectedNode(null)
    })
    cy.on('tap', (evt: any) => {
      if (evt.target === cy) { setSelectedNode(null); setSelectedEdge(null); cy.elements().removeClass('dimmed highlighted') }
    })
    cy.on('mouseover', 'node', (evt: any) => { setHoveredNode(evt.target.id()) })
    cy.on('mouseout', 'node', () => { setHoveredNode(null) })

    cyInstance.current = cy
    return () => { if (cyInstance.current) { cyInstance.current.destroy(); cyInstance.current = null } }
  }, [graphData, centrality])

  useEffect(() => {
    if (!cyInstance.current || !searchTerm) { if (cyInstance.current) cyInstance.current.elements().removeClass('dimmed highlighted'); return }
    const cy = cyInstance.current; cy.elements().addClass('dimmed')
    cy.nodes().forEach((node) => { if (node.data('label').toLowerCase().includes(searchTerm.toLowerCase())) { node.removeClass('dimmed').addClass('highlighted'); node.connectedEdges().removeClass('dimmed'); node.neighborhood('node').removeClass('dimmed') } })
  }, [searchTerm])

  useEffect(() => {
    if (!cyInstance.current) return; const cy = cyInstance.current
    if (showTopInfluencers) {
      const topIds = new Set(centrality.slice(0, 10).map((c: any) => c.entity_id))
      cy.nodes().forEach((node) => { topIds.has(node.id()) ? node.removeClass('dimmed').addClass('highlighted') : node.addClass('dimmed') })
      cy.edges().addClass('dimmed')
    } else { cy.elements().removeClass('dimmed highlighted') }
  }, [showTopInfluencers, centrality])

  const handleFindPath = async () => {
    if (!pathSource || !pathTarget) return
    try {
      const src = centrality.find((c: any) => c.name.toLowerCase().includes(pathSource.toLowerCase()))
      const tgt = centrality.find((c: any) => c.name.toLowerCase().includes(pathTarget.toLowerCase()))
      if (!src || !tgt) { alert('Entity not found.'); return }
      const result = await api.findPath(src.entity_id, tgt.entity_id); setPathResult(result)
      if (cyInstance.current) { const cy = cyInstance.current; cy.elements().addClass('dimmed'); const ids = result.path.map((p: any) => p.entity_id); cy.nodes().forEach((n) => { if (ids.includes(n.id())) n.removeClass('dimmed').addClass('path-node') }); cy.edges().forEach((e) => { const s = e.data('source'), t = e.data('target'); if (ids.includes(s) && ids.includes(t)) { const i1 = ids.indexOf(s), i2 = ids.indexOf(t); if (Math.abs(i1 - i2) === 1) e.removeClass('dimmed').addClass('path-edge') } }) }
    } catch (err: any) { alert(err.message || 'No path found') }
  }

  const handleExportPng = useCallback(() => {
    if (!cyInstance.current) return; setExportingPng(true)
    try { cyInstance.current.fit(undefined, 30); const png = cyInstance.current.png({ bg: '#07090e', full: true, scale: 2, maxWidth: 2400, maxHeight: 1800 }); const link = document.createElement('a'); link.download = `people-network-${caseId || 'multi'}-${new Date().toISOString().slice(0, 10)}.png`; link.href = png; link.click() } finally { setExportingPng(false) }
  }, [caseId])

  const handleHighlightOnLocationGraph = useCallback(() => {
    if (!selectedNode || selectedNode.entity_type !== 'Person') return
    highlightSuspect(selectedNode.id, selectedNode.label); navigate('/location-network')
  }, [selectedNode, highlightSuspect, navigate])

  const focusOnNode = (nodeId: string) => {
    if (!cyInstance.current) return
    const n = cyInstance.current.getElementById(nodeId)
    if (n) cyInstance.current.animate({ center: { eles: n }, zoom: 2 } as any, { duration: 400 })
  }

  const toolbarBtnClass = 'btn-ops'

  return (
    <div className="h-[calc(100vh-7rem)] flex flex-col animate-fade-in">
      {/* Toolbar */}
      <div className="ops-panel rounded-b-none px-4 py-2 flex items-center gap-3 flex-wrap border-b-0 rounded-t-xl">
        <button onClick={() => caseId ? navigate(`/cases/${caseId}`) : navigate('/cases')} className={toolbarBtnClass} style={{ padding: '6px 8px' }}><ArrowLeft size={14} /></button>
        <div className="flex items-center gap-1.5 text-xs font-semibold tracking-wider" style={{ color: 'var(--ops-accent)' }}><Users size={14} /> PEOPLE GRAPH</div>
        <div className="relative flex-1 max-w-xs"><Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ops-text-muted)' }} /><input type="text" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search suspects..." className="input-ops" /></div>
        {!caseId && <button onClick={() => setShowCaseSelector(!showCaseSelector)} className={`${toolbarBtnClass} ${showCaseSelector ? 'active' : ''}`}><Layers size={13} /> Cases ({selectedCaseIds.length})</button>}
        <button onClick={() => setShowFilters(!showFilters)} className={`${toolbarBtnClass} ${showFilters ? 'active' : ''}`}><Filter size={13} /> Filters</button>
        <button onClick={() => setShowTopInfluencers(!showTopInfluencers)} className={`${toolbarBtnClass} ${showTopInfluencers ? 'active' : ''}`}><TrendingUp size={13} /> Top Influencers</button>
        <button onClick={() => setShowPathFinder(!showPathFinder)} className={`${toolbarBtnClass} ${showPathFinder ? 'active' : ''}`}><Route size={13} /> Path</button>
        <button onClick={handleExportPng} disabled={exportingPng || !graphData} className={`${toolbarBtnClass} disabled:opacity-30`}><Download size={13} /> PNG</button>
        {selectedNode && selectedNode.entity_type === 'Person' && (
          <button onClick={handleHighlightOnLocationGraph} className="btn-ops" style={{ borderColor: 'rgba(0, 229, 255, 0.3)', color: 'var(--ops-accent)' }}><MapPin size={13} /> → Location</button>
        )}
        <div className="text-[10px] ml-auto" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{graphData?.node_count || 0}N • {graphData?.edge_count || 0}E{multiMode && graphData?.cases_included ? ` • ${graphData.cases_included} cases` : ''}</div>
      </div>

      <div className="flex-1 flex overflow-hidden border-x border-b rounded-b-xl" style={{ borderColor: 'var(--ops-border)' }}>
        {/* Case Selector Panel */}
        {showCaseSelector && (
          <div className="w-72 p-4 overflow-auto border-r animate-slide-left" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <h3 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>SELECT CASES</h3>
            <div className="space-y-1.5 mb-4">{cases.map(c => (
              <label key={c.id} className="flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors" style={{ background: selectedCaseIds.includes(c.id) ? 'var(--ops-accent-bg)' : 'transparent' }}>
                <input type="checkbox" checked={selectedCaseIds.includes(c.id)} onChange={() => setSelectedCaseIds(prev => prev.includes(c.id) ? prev.filter(x => x !== c.id) : [...prev, c.id])} className="checkbox-ops" />
                <div className="min-w-0"><p className="text-[11px] font-medium truncate" style={{ color: 'var(--ops-text-primary)' }}>{c.name}</p><p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{c.case_number}</p></div>
              </label>
            ))}</div>
            <button onClick={handleLoadMultiCase} disabled={selectedCaseIds.length === 0} className="btn-ops-primary w-full py-2.5 rounded-lg text-[11px] font-semibold"><Layers size={13} className="inline mr-1" /> LOAD GRAPH</button>
          </div>
        )}

        {/* Filters Panel */}
        {showFilters && (
          <div className="w-56 p-4 overflow-auto border-r animate-slide-left" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <h3 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>FILTERS</h3>
            <div className="space-y-4">
              <div><label className="block text-[9px] font-semibold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>NODE TYPE</label><select value={filters.entityType} onChange={(e) => setFilters({ ...filters, entityType: e.target.value })} className="select-ops w-full"><option value="">All</option>{Object.keys(PEOPLE_COLORS).map(t => <option key={t} value={t}>{t}</option>)}</select></div>
              <div><label className="block text-[9px] font-semibold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>EDGE TYPE</label><select value={filters.relationshipType} onChange={(e) => setFilters({ ...filters, relationshipType: e.target.value })} className="select-ops w-full"><option value="">All</option>{Object.keys(REL_COLORS).map(t => <option key={t} value={t}>{t}</option>)}</select></div>
              <div><label className="block text-[9px] font-semibold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>CONFIDENCE: {filters.minConfidence}</label><input type="range" min="0" max="1" step="0.1" value={filters.minConfidence} onChange={(e) => setFilters({ ...filters, minConfidence: parseFloat(e.target.value) })} className="w-full" /></div>
              <button onClick={() => setFilters({ entityType: '', relationshipType: '', minConfidence: 0 })} className="text-[10px]" style={{ color: 'var(--ops-accent-dim)' }}>Clear</button>
            </div>
            <div className="mt-5"><h4 className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>LEGEND</h4>
              <div className="space-y-1.5">{Object.entries(PEOPLE_COLORS).map(([t, c]) => (<div key={t} className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full" style={{ background: c }} /><span className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>{t}</span></div>))}</div>
              <div className="mt-3"><h4 className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>CONNECTIONS</h4>
                <div className="space-y-1.5">{Object.entries(REL_COLORS).map(([t, c]) => (<div key={t} className="flex items-center gap-2"><div className="w-4 h-0.5 rounded" style={{ background: c }} /><span className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>{t}</span></div>))}</div>
              </div>
            </div>
          </div>
        )}

        {/* Path Finder Panel */}
        {showPathFinder && (
          <div className="w-64 p-4 overflow-auto border-r animate-slide-left" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <div className="flex items-center justify-between mb-3"><h3 className="text-[10px] font-bold tracking-wider" style={{ color: 'var(--ops-text-secondary)' }}>FIND PATH</h3><button onClick={() => { setPathResult(null); cyInstance.current?.elements().removeClass('dimmed path-node path-edge') }}><X size={12} style={{ color: 'var(--ops-text-muted)' }} /></button></div>
            <div className="space-y-3">
              <input type="text" value={pathSource} onChange={(e) => setPathSource(e.target.value)} placeholder="Source" className="input-ops" style={{ paddingLeft: 12 }} />
              <input type="text" value={pathTarget} onChange={(e) => setPathTarget(e.target.value)} placeholder="Target" className="input-ops" style={{ paddingLeft: 12 }} />
              <button onClick={handleFindPath} className="btn-ops-primary w-full py-2 rounded-lg text-[11px] font-semibold"><Target size={12} /> FIND PATH</button>
              {pathResult && (<div className="rounded-lg p-3 mt-3" style={{ background: 'var(--ops-critical-bg)', border: '1px solid rgba(255, 61, 113, 0.2)' }}><p className="text-[10px] font-bold mb-2" style={{ color: 'var(--ops-critical)' }}>PATH: {pathResult.hops} HOPS</p><div className="space-y-1">{pathResult.path.map((p: any, i: number) => (<div key={i} className="flex items-center gap-2 text-[10px]"><span style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{i}.</span><span style={{ color: 'var(--ops-text-primary)' }}>{p.name}</span>{p.edge_to_next && <span style={{ color: 'var(--ops-critical)' }}>→ {p.edge_to_next.relationship_type}</span>}</div>))}</div></div>)}
            </div>
          </div>
        )}

        {/* Graph Canvas */}
        <div className="flex-1 relative" style={{ background: 'var(--ops-bg-void)' }}>
          {/* Grid background effect */}
          <div className="absolute inset-0" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(0, 229, 255, 0.03) 1px, transparent 0)', backgroundSize: '40px 40px' }} />
          <div ref={cyRef} className="w-full h-full relative" style={{ zIndex: 1 }} />
          {loading && <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(7, 9, 14, 0.8)', zIndex: 10 }}><div className="loading-spinner" /></div>}
          {graphData && graphData.node_count === 0 && !loading && (
            <div className="absolute inset-0 flex items-center justify-center" style={{ zIndex: 10 }}>
              <div className="text-center p-8 rounded-2xl" style={{ background: 'rgba(7, 9, 14, 0.9)', border: '1px solid var(--ops-border)' }}>
                <Network size={48} style={{ color: 'var(--ops-accent)', opacity: 0.3 }} />
                <p className="text-sm mt-4 font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{multiMode ? 'Select cases to build the network' : 'No entities in this case yet'}</p>
                <p className="text-[11px] mt-2" style={{ color: 'var(--ops-text-muted)' }}>{multiMode ? 'Choose cases from the sidebar to visualize connections between suspects' : 'Upload case documents to extract entities and relationships'}</p>
              </div>
            </div>
          )}
          {/* Hovered node tooltip */}
          {hoveredNode && !selectedNode && (() => {
            const node = graphData?.nodes?.find((n: any) => n.data.id === hoveredNode)
            const cent = centrality.find((c: any) => c.entity_id === hoveredNode)
            if (!node) return null
            return (
              <div className="absolute bottom-4 left-4 p-3 rounded-xl z-20" style={{ background: 'rgba(7, 9, 14, 0.95)', border: '1px solid var(--ops-border)', backdropFilter: 'blur(8px)' }}>
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: PEOPLE_COLORS[node.data.type] || '#6b7280' }} />
                  <span className="text-[11px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{node.data.label}</span>
                  {cent && <CentralityBadge score={cent.combined_score} />}
                </div>
                {cent && <p className="text-[9px] mt-1" style={{ color: 'var(--ops-text-muted)' }}>{cent.connections} connections • Score: {cent.combined_score?.toFixed(3)}</p>}
              </div>
            )
          })()}
          {/* Stats overlay */}
          {graphData && graphData.node_count > 0 && (
            <div className="absolute top-3 right-3 flex items-center gap-2 z-10">
              <div className="px-2.5 py-1 rounded-lg text-[9px] font-bold" style={{ background: 'rgba(7, 9, 14, 0.85)', border: '1px solid var(--ops-border)', color: 'var(--ops-text-muted)' }}>
                <span style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>{graphData.node_count}</span> nodes
              </div>
              <div className="px-2.5 py-1 rounded-lg text-[9px] font-bold" style={{ background: 'rgba(7, 9, 14, 0.85)', border: '1px solid var(--ops-border)', color: 'var(--ops-text-muted)' }}>
                <span style={{ color: '#8b5cf6', fontFamily: "'JetBrains Mono', monospace" }}>{graphData.edge_count}</span> edges
              </div>
            </div>
          )}
        </div>

        {/* Node/Edge Detail Panel */}
        {(selectedNode || selectedEdge) && (
          <div className="w-72 p-4 overflow-auto border-l animate-slide-right" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            {selectedNode && (<div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-4 h-4 rounded-full" style={{ background: PEOPLE_COLORS[selectedNode.entity_type] || '#6b7280', boxShadow: `0 0 8px ${PEOPLE_COLORS[selectedNode.entity_type] || '#6b7280'}40` }} />
                <h3 className="text-sm font-bold" style={{ color: 'var(--ops-text-primary)' }}>{selectedNode.label}</h3>
              </div>
              <div className="space-y-3 text-[11px]">
                <div className="flex justify-between items-center"><span style={{ color: 'var(--ops-text-muted)' }}>Type</span><span className="badge-ops" style={{ background: `${PEOPLE_COLORS[selectedNode.entity_type] || '#6b7280'}18`, color: PEOPLE_COLORS[selectedNode.entity_type] || '#6b7280', fontSize: 9 }}>{selectedNode.entity_type}</span></div>
                <div className="flex justify-between items-center"><span style={{ color: 'var(--ops-text-muted)' }}>Confidence</span><span className="font-mono" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>{((selectedNode.confidence || 0) * 100).toFixed(0)}%</span></div>
                <div className="flex justify-between items-center"><span style={{ color: 'var(--ops-text-muted)' }}>Source</span><span className="badge-ops" style={{ fontSize: 9 }}>{selectedNode.is_ai ? 'AI EXTRACTED' : 'CONFIRMED'}</span></div>
                {selectedNode.centrality_score != null && (
                  <div className="flex justify-between items-center"><span style={{ color: 'var(--ops-text-muted)' }}>Influence</span>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--ops-bg-elevated)' }}>
                        <div className="h-full rounded-full" style={{ width: `${Math.min(selectedNode.centrality_score * 100, 100)}%`, background: selectedNode.centrality_score >= 0.7 ? '#ff3d71' : selectedNode.centrality_score >= 0.4 ? '#f59e0b' : 'var(--ops-accent)' }} />
                      </div>
                      <CentralityBadge score={selectedNode.centrality_score} />
                    </div>
                  </div>
                )}
                {selectedNode.attributes?.resolution_status && (<div className="flex justify-between items-center"><span style={{ color: 'var(--ops-text-muted)' }}>Resolution</span><span className="badge-ops" style={{ fontSize: 9, background: selectedNode.attributes.resolution_status === 'unresolved' ? 'var(--ops-high-bg)' : 'var(--ops-success-bg)', color: selectedNode.attributes.resolution_status === 'unresolved' ? 'var(--ops-high)' : 'var(--ops-success)' }}>{selectedNode.attributes.resolution_status === 'unresolved' ? 'NEEDS REVIEW' : 'RESOLVED'}</span></div>)}
              </div>
              <div className="flex gap-2 mt-5">
                <button onClick={() => navigate(`/entities/${selectedNode.id}`)} className="btn-ops-primary flex-1 py-2 rounded-lg text-[11px] font-semibold text-center">PROFILE</button>
                {selectedNode.entity_type === 'Person' && <button onClick={handleHighlightOnLocationGraph} className="btn-ops py-2 px-3 rounded-lg"><MapPin size={13} /></button>}
              </div>
            </div>)}
            {selectedEdge && (<div><h3 className="text-xs font-semibold mb-3" style={{ color: 'var(--ops-text-primary)' }}>Relationship</h3><div className="space-y-2 text-[11px]">
              <div className="flex justify-between"><span style={{ color: 'var(--ops-text-muted)' }}>Type</span><span className="badge-ops" style={{ background: `${REL_COLORS[selectedEdge.label] || '#6b7280'}18`, color: REL_COLORS[selectedEdge.label] || '#6b7280', fontSize: 9 }}>{selectedEdge.label}</span></div>
              <div className="flex justify-between"><span style={{ color: 'var(--ops-text-muted)' }}>Weight</span><span className="font-mono" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>{selectedEdge.weight?.toFixed(2)}</span></div>
            </div></div>)}
          </div>
        )}

        {/* Top Influencers Panel */}
        {showTopInfluencers && !selectedNode && (
          <div className="w-72 p-4 overflow-auto border-l animate-slide-right" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp size={14} style={{ color: '#f59e0b' }} />
              <h3 className="text-[10px] font-bold tracking-wider" style={{ color: 'var(--ops-text-secondary)' }}>TOP INFLUENCERS</h3>
            </div>
            <p className="text-[9px] mb-4" style={{ color: 'var(--ops-text-muted)' }}>Ranked by combined centrality (degree + betweenness + eigenvector)</p>
            <div className="space-y-2">
              {centrality.length === 0 && <p className="text-[10px] text-center py-4" style={{ color: 'var(--ops-text-muted)' }}>No centrality data. Load a graph first.</p>}
              {centrality.slice(0, 15).map((c: any, i: number) => {
                const maxScore = centrality[0]?.combined_score || 1
                const barWidth = Math.min((c.combined_score / maxScore) * 100, 100)
                return (
                  <div key={c.entity_id}
                    className="p-2.5 rounded-xl cursor-pointer transition-all"
                    style={{ background: i === 0 ? 'rgba(255, 61, 113, 0.08)' : 'var(--ops-bg-elevated)', border: `1px solid ${i === 0 ? 'rgba(255, 61, 113, 0.2)' : 'var(--ops-border)'}` }}
                    onClick={() => focusOnNode(c.entity_id)}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[9px] font-bold w-5 text-center" style={{ color: i < 3 ? '#ff3d71' : 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>#{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-[11px] font-semibold truncate" style={{ color: 'var(--ops-text-primary)' }}>{c.name}</p>
                      </div>
                      <CentralityBadge score={c.combined_score} />
                    </div>
                    <div className="flex items-center gap-2 ml-7">
                      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--ops-bg-deep)' }}>
                        <div className="h-full rounded-full transition-all" style={{ width: `${barWidth}%`, background: c.combined_score >= 0.7 ? '#ff3d71' : c.combined_score >= 0.4 ? '#f59e0b' : 'var(--ops-accent)', boxShadow: `0 0 6px ${c.combined_score >= 0.7 ? '#ff3d71' : c.combined_score >= 0.4 ? '#f59e0b' : 'var(--ops-accent)'}40` }} />
                      </div>
                      <span className="text-[9px] font-bold w-10 text-right" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>{c.combined_score?.toFixed(3)}</span>
                    </div>
                    <div className="flex items-center gap-3 ml-7 mt-1">
                      <span className="text-[8px]" style={{ color: 'var(--ops-text-muted)' }}>{c.connections} links</span>
                      {c.case_ids?.length > 0 && <span className="text-[8px]" style={{ color: 'var(--ops-text-muted)' }}>{c.case_ids.length} cases</span>}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
