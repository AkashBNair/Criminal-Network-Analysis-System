import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import cytoscape from 'cytoscape'
import { useCrossGraph } from '../context/CrossGraphContext'
import { ArrowLeft, Search, Filter, MapPin, Layers, Grid3X3, Map, Clock, Download, Play, Pause, RotateCcw, X } from 'lucide-react'

interface LocationNode { data: { id: string; label: string; address: string; area: string; lat: number | null; lng: number | null; is_tower: boolean; suspect_count: number; suspects: Array<{ person_id: string; person_name: string; weight: number; first_observed?: string; last_observed?: string }>; case_id: string; confidence: number } }
interface CoLocationEdge { data: { id: string; source: string; target: string; label: string; weight: number; shared_suspects: string[] } }

const TOWER_COLOR = '#0891b2'
const SCENE_COLOR = '#ff3d71'
const SAFE_HOUSE_COLOR = '#8b5cf6'
const DEFAULT_COLOR = '#484f58'
const HIGHLIGHTED_COLOR = '#ffc23d'

function getLocationColor(node: LocationNode, highlighted?: boolean): string {
  if (highlighted) return HIGHLIGHTED_COLOR
  const addr = (node.data.address || '').toLowerCase()
  const label = node.data.label.toLowerCase()
  if (label.startsWith('rtp-')) return TOWER_COLOR
  if (addr.includes('shooting') || addr.includes('scene') || addr.includes('murder')) return SCENE_COLOR
  if (addr.includes('godown') || addr.includes('safe')) return SAFE_HOUSE_COLOR
  return DEFAULT_COLOR
}

const MAP_POSITIONS: Record<string, { x: number; y: number }> = {
  'RTP-T009': { x: 180, y: 300 }, 'RTP-T009B': { x: 120, y: 340 }, 'RTP-T014': { x: 220, y: 180 },
  'RTP-T017': { x: 100, y: 260 }, 'RTP-T022': { x: 280, y: 140 }, 'RTP-T028': { x: 240, y: 240 },
  'RTP-T031': { x: 260, y: 200 }, 'RTP-T045': { x: 180, y: 220 }, 'RTP-T052': { x: 150, y: 310 },
  'RTP-T060': { x: 80, y: 370 },
}

function parseDate(s?: string): Date | null {
  if (!s) return null
  const dmy = s.match(/(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/)
  if (dmy) return new Date(parseInt(dmy[3]), parseInt(dmy[2]) - 1, parseInt(dmy[1]))
  const ymd = s.match(/(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})/)
  if (ymd) return new Date(parseInt(ymd[1]), parseInt(ymd[2]) - 1, parseInt(ymd[3]))
  return null
}

export default function LocationGraphPage() {
  const navigate = useNavigate()
  const cyRef = useRef<HTMLDivElement>(null)
  const cyInstance = useRef<cytoscape.Core | null>(null)
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const { highlightedSuspect, clearHighlight } = useCrossGraph()
  const timelineIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [cases, setCases] = useState<any[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([])
  const [graphData, setGraphData] = useState<{ nodes: LocationNode[]; edges: CoLocationEdge[] } | null>(null)
  const [selectedNode, setSelectedNode] = useState<LocationNode | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [viewMode, setViewMode] = useState<'graph' | 'map'>('graph')
  const [showCaseSelector, setShowCaseSelector] = useState(true)
  const [showFilters, setShowFilters] = useState(false)
  const [loading, setLoading] = useState(false)
  const [hoveredNode, setHoveredNode] = useState<LocationNode | null>(null)
  const [exportingPng, setExportingPng] = useState(false)
  const [filters, setFilters] = useState({ towersOnly: false, minSuspects: 0 })
  const [timelineEnabled, setTimelineEnabled] = useState(false)
  const [timelineCurrentDate, setTimelineCurrentDate] = useState<string>('')
  const [timelinePlaying, setTimelinePlaying] = useState(false)
  const [timelineSpeed, setTimelineSpeed] = useState(1500)

  const allDates = useCallback(() => {
    if (!graphData) return []
    const dates = new Set<string>()
    graphData.nodes.forEach(n => { n.data.suspects.forEach(s => { if (s.first_observed) dates.add(s.first_observed); if (s.last_observed) dates.add(s.last_observed) }) })
    return Array.from(dates).sort()
  }, [graphData])

  useEffect(() => { api.getCases().then(setCases).catch(console.error) }, [])
  useEffect(() => { if (graphData && timelineEnabled) { const d = allDates(); if (d.length > 0) setTimelineCurrentDate(d[d.length - 1]) } }, [graphData, timelineEnabled, allDates])

  useEffect(() => {
    if (!highlightedSuspect || !graphData) return
    const matching = graphData.nodes.filter(n => n.data.suspects.some(s => s.person_id === highlightedSuspect.id))
    if (matching.length > 0 && cyInstance.current) {
      cyInstance.current.elements().addClass('dimmed')
      matching.forEach(n => { const node = cyInstance.current!.getElementById(n.data.id); if (node) { node.removeClass('dimmed').addClass('highlighted'); node.connectedEdges().removeClass('dimmed') } })
      const first = cyInstance.current.getElementById(matching[0].data.id)
      if (first) cyInstance.current.animate({ center: { eles: first }, zoom: 1.5 } as any, { duration: 400 })
      setSelectedNode(matching[0])
    }
  }, [highlightedSuspect, graphData])

  const loadLocationGraph = async (caseIds: string[]) => {
    if (caseIds.length === 0) return
    try { setLoading(true); const data = caseIds.length === 1 ? await api.getLocationGraph(caseIds[0]) : await api.getMultiLocationGraph(caseIds); setGraphData(data) } catch (err) { console.error(err) } finally { setLoading(false) }
  }

  const handleLoad = () => { if (selectedCaseIds.length === 0) return; setShowCaseSelector(false); loadLocationGraph(selectedCaseIds) }

  const isNodeInTimeline = useCallback((node: LocationNode): boolean => {
    if (!timelineEnabled || !timelineCurrentDate) return true
    const currentDate = parseDate(timelineCurrentDate); if (!currentDate) return true
    return node.data.suspects.some(s => { if (!s.first_observed) return true; const first = parseDate(s.first_observed); if (!first) return true; if (s.last_observed) { const last = parseDate(s.last_observed); if (last) return first <= currentDate && currentDate <= last } return first <= currentDate })
  }, [timelineEnabled, timelineCurrentDate])

  useEffect(() => {
    if (timelinePlaying && timelineEnabled) { const dates = allDates(); if (dates.length === 0) return; let idx = dates.indexOf(timelineCurrentDate); if (idx < 0) idx = 0; timelineIntervalRef.current = setInterval(() => { idx++; if (idx >= dates.length) idx = 0; setTimelineCurrentDate(dates[idx]) }, timelineSpeed); return () => { if (timelineIntervalRef.current) clearInterval(timelineIntervalRef.current) } } else { if (timelineIntervalRef.current) clearInterval(timelineIntervalRef.current) }
  }, [timelinePlaying, timelineEnabled, timelineCurrentDate, allDates, timelineSpeed])

  useEffect(() => { return () => { if (timelineIntervalRef.current) clearInterval(timelineIntervalRef.current) } }, [])

  useEffect(() => {
    if (!cyRef.current || !graphData || viewMode !== 'graph') return
    if (cyInstance.current) cyInstance.current.destroy()
    const filtered = graphData.nodes.filter(n => { if (filters.towersOnly && !n.data.is_tower) return false; if (filters.minSuspects > 0 && n.data.suspect_count < filters.minSuspects) return false; if (timelineEnabled && !isNodeInTimeline(n)) return false; return true })
    const filteredIds = new Set(filtered.map(n => n.data.id))
    const highlightedNodeIds = new Set<string>()
    if (highlightedSuspect) { graphData.nodes.forEach(n => { if (n.data.suspects.some(s => s.person_id === highlightedSuspect.id)) highlightedNodeIds.add(n.data.id) }) }

    const elements: cytoscape.ElementDefinition[] = [
      ...filtered.map(n => ({ data: { id: n.data.id, label: n.data.label, address: n.data.address, suspect_count: n.data.suspect_count, is_tower: n.data.is_tower }, classes: highlightedNodeIds.has(n.data.id) ? 'cross-highlighted' : '' })),
      ...graphData.edges.filter(e => filteredIds.has(e.data.source) && filteredIds.has(e.data.target)).map(e => ({ data: { id: e.data.id, source: e.data.source, target: e.data.target, label: e.data.label, weight: e.data.weight, shared_suspects: e.data.shared_suspects.join(', ') } })),
    ]

    const cy = cytoscape({
      container: cyRef.current, elements,
      style: [
        { selector: 'node', style: { 'background-color': (ele: any) => ele.data('is_tower') ? TOWER_COLOR : DEFAULT_COLOR, label: 'data(label)', 'font-size': '9px', "font-family": "'JetBrains Mono', monospace", color: '#e2e8f0', 'text-valign': 'bottom', 'text-margin-y': 5, width: (ele: any) => Math.max(18, 10 + (ele.data('suspect_count') || 1) * 5), height: (ele: any) => Math.max(18, 10 + (ele.data('suspect_count') || 1) * 5), 'border-width': 1.5, 'border-color': 'rgba(0, 229, 255, 0.2)', 'text-outline-width': 1.5, 'text-outline-color': '#07090e' } as any },
        { selector: 'node.highlighted', style: { width: 36, height: 36, 'border-width': 2.5, 'border-color': '#ffc23d', 'z-index': 999 } },
        { selector: 'node.cross-highlighted', style: { width: 36, height: 36, 'border-width': 2.5, 'border-color': '#ffc23d', 'z-index': 999, 'background-color': HIGHLIGHTED_COLOR } as any },
        { selector: 'node.dimmed', style: { opacity: 0.1 } },
        { selector: 'edge', style: { width: (ele: any) => Math.max(1, Math.min(ele.data('weight') || 1, 5)), 'line-color': 'rgba(139, 148, 158, 0.25)', 'target-arrow-color': 'rgba(139, 148, 158, 0.25)', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', opacity: 0.4, label: 'data(shared_suspects)', 'font-size': '7px', "font-family": "'JetBrains Mono', monospace", color: 'rgba(139, 148, 158, 0.5)' } as any },
        { selector: 'edge.dimmed', style: { opacity: 0.06 } },
      ],
      layout: { name: 'cose', animate: true, animationDuration: 600, nodeRepulsion: () => 6000, idealEdgeLength: () => 100, gravity: 0.3, numIter: 300 } as any,
      minZoom: 0.2, maxZoom: 3,
    })
    cy.on('tap', 'node', (evt: any) => { const nd = graphData.nodes.find(n => n.data.id === evt.target.id()); if (nd) setSelectedNode(nd) })
    cy.on('tap', (evt: any) => { if (evt.target === cy) setSelectedNode(null) })
    cyInstance.current = cy
    return () => { if (cyInstance.current) { cyInstance.current.destroy(); cyInstance.current = null } }
  }, [graphData, viewMode, filters, timelineEnabled, timelineCurrentDate, highlightedSuspect, isNodeInTimeline])

  useEffect(() => {
    if (!cyInstance.current || !searchTerm) { if (cyInstance.current) cyInstance.current.elements().removeClass('dimmed highlighted'); return }
    const cy = cyInstance.current; cy.elements().addClass('dimmed')
    cy.nodes().forEach((node) => { if (node.data('label').toLowerCase().includes(searchTerm.toLowerCase()) || (node.data('address') || '').toLowerCase().includes(searchTerm.toLowerCase())) { node.removeClass('dimmed').addClass('highlighted'); node.connectedEdges().removeClass('dimmed') } })
  }, [searchTerm])

  const handleExportPng = useCallback(() => {
    if (viewMode === 'graph' && cyInstance.current) { setExportingPng(true); try { cyInstance.current.fit(undefined, 30); const png = cyInstance.current.png({ bg: '#07090e', full: true, scale: 2 }); const link = document.createElement('a'); link.download = `location-graph-${new Date().toISOString().slice(0, 10)}.png`; link.href = png; link.click() } finally { setExportingPng(false) } }
  }, [viewMode])

  const filteredNodes = graphData?.nodes.filter(n => { if (filters.towersOnly && !n.data.is_tower) return false; if (filters.minSuspects > 0 && n.data.suspect_count < filters.minSuspects) return false; if (timelineEnabled && !isNodeInTimeline(n)) return false; return true }) || []
  const dates = allDates()

  return (
    <div className="h-[calc(100vh-7rem)] flex flex-col animate-fade-in">
      {/* Toolbar */}
      <div className="ops-panel rounded-b-none px-4 py-2 flex items-center gap-3 flex-wrap border-b-0 rounded-t-xl">
        <button onClick={() => { clearHighlight(); navigate('/cases') }} className="btn-ops" style={{ padding: '6px 8px' }}><ArrowLeft size={14} /></button>
        <div className="flex items-center gap-1 bg-black/30 rounded-lg p-0.5">
          <button onClick={() => setViewMode('graph')} className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-[11px] font-semibold transition-colors ${viewMode === 'graph' ? 'text-[var(--ops-accent)]' : ''}`} style={{ background: viewMode === 'graph' ? 'var(--ops-accent-bg)' : 'transparent', color: viewMode === 'graph' ? 'var(--ops-accent)' : 'var(--ops-text-muted)' }}><Grid3X3 size={13} /> NODE</button>
          <button onClick={() => setViewMode('map')} className={`flex items-center gap-1 px-3 py-1.5 rounded-md text-[11px] font-semibold transition-colors`} style={{ background: viewMode === 'map' ? 'var(--ops-accent-bg)' : 'transparent', color: viewMode === 'map' ? 'var(--ops-accent)' : 'var(--ops-text-muted)' }}><Map size={13} /> MAP</button>
        </div>
        <div className="relative flex-1 max-w-xs"><Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ops-text-muted)' }} /><input type="text" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search locations..." className="input-ops" /></div>
        <button onClick={() => setShowCaseSelector(!showCaseSelector)} className={`btn-ops ${showCaseSelector ? 'active' : ''}`}><Layers size={13} /> Cases ({selectedCaseIds.length})</button>
        <button onClick={() => setShowFilters(!showFilters)} className={`btn-ops ${showFilters ? 'active' : ''}`}><Filter size={13} /></button>
        <button onClick={() => { setTimelineEnabled(!timelineEnabled); setTimelinePlaying(false) }} className={`btn-ops ${timelineEnabled ? 'active' : ''}`}><Clock size={13} /></button>
        <button onClick={handleExportPng} disabled={exportingPng || !graphData} className="btn-ops disabled:opacity-30"><Download size={13} /></button>
        {highlightedSuspect && <button onClick={clearHighlight} className="btn-ops" style={{ borderColor: 'rgba(255, 194, 61, 0.3)', color: 'var(--ops-medium)' }}><X size={13} /> {highlightedSuspect.name}</button>}
        <div className="text-[10px] ml-auto" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{filteredNodes.length}L • {graphData?.edges.length || 0}E</div>
      </div>

      {/* Timeline bar */}
      {timelineEnabled && dates.length > 0 && (
        <div className="px-4 py-2 flex items-center gap-3 border-x" style={{ background: 'rgba(139, 92, 246, 0.06)', borderColor: 'var(--ops-border)' }}>
          <div className="flex items-center gap-2">
            <button onClick={() => setTimelinePlaying(!timelinePlaying)} className="btn-ops" style={{ padding: '5px 7px', background: timelinePlaying ? 'rgba(139, 92, 246, 0.15)' : undefined, color: timelinePlaying ? '#8b5cf6' : undefined }}>{timelinePlaying ? <Pause size={13} /> : <Play size={13} />}</button>
            <button onClick={() => { setTimelinePlaying(false); setTimelineCurrentDate(dates[0]) }} className="btn-ops" style={{ padding: '5px 7px' }}><RotateCcw size={13} /></button>
          </div>
          <div className="flex-1 flex items-center gap-3">
            <span className="text-[10px] w-20" style={{ color: '#8b5cf6', fontFamily: "'JetBrains Mono', monospace" }}>{dates[0]}</span>
            <input type="range" min={0} max={dates.length - 1} step={1} value={dates.indexOf(timelineCurrentDate)} onChange={(e) => { setTimelinePlaying(false); setTimelineCurrentDate(dates[parseInt(e.target.value)]) }} className="flex-1" style={{ accentColor: '#8b5cf6' }} />
            <span className="text-[10px] w-20 text-right" style={{ color: '#8b5cf6', fontFamily: "'JetBrains Mono', monospace" }}>{dates[dates.length - 1]}</span>
          </div>
          <span className="text-xs font-bold min-w-[100px] text-center" style={{ color: '#a78bfa', fontFamily: "'JetBrains Mono', monospace" }}>{timelineCurrentDate}</span>
          <select value={timelineSpeed} onChange={(e) => setTimelineSpeed(parseInt(e.target.value))} className="select-ops text-[10px]" style={{ padding: '3px 24px 3px 8px' }}>
            <option value={2500}>Slow</option><option value={1500}>Normal</option><option value={800}>Fast</option><option value={400}>V.Fast</option>
          </select>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden border-x border-b rounded-b-xl" style={{ borderColor: 'var(--ops-border)' }}>
        {showCaseSelector && (
          <div className="w-72 p-4 overflow-auto border-r animate-slide-left" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <h3 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>SELECT CASES</h3>
            <div className="space-y-1.5 mb-4">{cases.map(c => (
              <label key={c.id} className="flex items-center gap-2 p-2 rounded-lg cursor-pointer" style={{ background: selectedCaseIds.includes(c.id) ? 'var(--ops-accent-bg)' : 'transparent' }}>
                <input type="checkbox" checked={selectedCaseIds.includes(c.id)} onChange={() => setSelectedCaseIds(prev => prev.includes(c.id) ? prev.filter(x => x !== c.id) : [...prev, c.id])} className="checkbox-ops" />
                <div className="min-w-0"><p className="text-[11px] font-medium truncate" style={{ color: 'var(--ops-text-primary)' }}>{c.name}</p><p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{c.case_number}</p></div>
              </label>
            ))}</div>
            <button onClick={handleLoad} disabled={selectedCaseIds.length === 0} className="btn-ops-primary w-full py-2.5 rounded-lg text-[11px] font-semibold"><MapPin size={13} className="inline mr-1" /> LOAD MAP</button>
          </div>
        )}

        {showFilters && (
          <div className="w-52 p-4 overflow-auto border-r animate-slide-left" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <h3 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>FILTERS</h3>
            <div className="space-y-4">
              <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={filters.towersOnly} onChange={(e) => setFilters({ ...filters, towersOnly: e.target.checked })} className="checkbox-ops" /><span className="text-[11px]" style={{ color: 'var(--ops-text-primary)' }}>Towers Only</span></label>
              <div><label className="block text-[9px] font-semibold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>MIN SUSPECTS: {filters.minSuspects}</label><input type="range" min="0" max="10" step="1" value={filters.minSuspects} onChange={(e) => setFilters({ ...filters, minSuspects: parseInt(e.target.value) })} className="w-full" /></div>
            </div>
            <div className="mt-5"><h4 className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>LEGEND</h4>
              <div className="space-y-1.5">
                {[{ color: TOWER_COLOR, label: 'Cell Tower' }, { color: SCENE_COLOR, label: 'Crime Scene' }, { color: SAFE_HOUSE_COLOR, label: 'Safe House' }, { color: DEFAULT_COLOR, label: 'Other' }].map(l => (
                  <div key={l.label} className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full" style={{ background: l.color }} /><span className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>{l.label}</span></div>
                ))}
                {highlightedSuspect && <div className="flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full" style={{ background: HIGHLIGHTED_COLOR }} /><span className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>Cross-Graph</span></div>}
              </div>
            </div>
          </div>
        )}

        <div className="flex-1 relative overflow-hidden" style={{ background: 'var(--ops-bg-void)' }}>
          {viewMode === 'graph' ? <div ref={cyRef} className="w-full h-full" /> : (
            <div ref={mapContainerRef} className="w-full h-full relative overflow-auto">
              <svg width="600" height="500" className="mx-auto my-4">
                {[...Array(12)].map((_, i) => <g key={i}><line x1={i * 50} y1={0} x2={i * 50} y2={500} stroke="rgba(0, 229, 255, 0.03)" strokeWidth={0.5} /><line x1={0} y1={i * 50} x2={600} y2={i * 50} stroke="rgba(0, 229, 255, 0.03)" strokeWidth={0.5} /></g>)}
                <line x1={60} y1={380} x2={320} y2={380} stroke="rgba(0, 229, 255, 0.08)" strokeWidth={2} strokeDasharray="8,4" />
                <text x={330} y={383} fontSize={8} fill="var(--ops-text-muted)" fontFamily="'JetBrains Mono', monospace">NH-52</text>
                <line x1={200} y1={100} x2={200} y2={400} stroke="rgba(0, 229, 255, 0.08)" strokeWidth={1.5} strokeDasharray="6,3" />
                <text x={205} y={95} fontSize={8} fill="var(--ops-text-muted)" fontFamily="'JetBrains Mono', monospace">Ring Rd</text>
                {graphData?.edges.map((edge) => {
                  const src = graphData.nodes.find(n => n.data.id === edge.data.source)
                  const tgt = graphData.nodes.find(n => n.data.id === edge.data.target)
                  if (!src || !tgt) return null
                  const sp = MAP_POSITIONS[src.data.label], tp = MAP_POSITIONS[tgt.data.label]
                  if (!sp || !tp) return null
                  if (timelineEnabled && timelineCurrentDate && (!isNodeInTimeline(src) || !isNodeInTimeline(tgt))) return null
                  return <g key={edge.data.id}><line x1={sp.x} y1={sp.y} x2={tp.x} y2={tp.y} stroke="rgba(0, 229, 255, 0.15)" strokeWidth={Math.max(1, edge.data.weight)} strokeDasharray="4,2" opacity={0.5} /><text x={(sp.x + tp.x) / 2} y={(sp.y + tp.y) / 2 - 5} fontSize={7} fill="var(--ops-text-muted)" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">{edge.data.shared_suspects.slice(0, 2).join(', ')}</text></g>
                })}
                {filteredNodes.map((node) => {
                  const isHighlighted = highlightedSuspect && node.data.suspects.some(s => s.person_id === highlightedSuspect.id)
                  const color = isHighlighted ? HIGHLIGHTED_COLOR : getLocationColor(node)
                  const pos = MAP_POSITIONS[node.data.label]
                  if (!pos) return null
                  const r = Math.max(12, 8 + node.data.suspect_count * 3)
                  return (
                    <g key={node.data.id} onMouseEnter={() => setHoveredNode(node)} onMouseLeave={() => setHoveredNode(null)} onClick={() => setSelectedNode(node)} className="cursor-pointer">
                      <circle cx={pos.x} cy={pos.y} r={r} fill={color} opacity={0.85} stroke={isHighlighted ? '#ffc23d' : 'rgba(0, 229, 255, 0.2)'} strokeWidth={isHighlighted ? 2.5 : 1.5} style={{ filter: `drop-shadow(0 0 4px ${color}40)` }} />
                      <text x={pos.x} y={pos.y + r + 12} fontSize={8} fill="var(--ops-text-secondary)" textAnchor="middle" fontWeight={600} fontFamily="'JetBrains Mono', monospace">{node.data.label}</text>
                      <text x={pos.x} y={pos.y + r + 22} fontSize={6} fill="var(--ops-text-muted)" textAnchor="middle">{node.data.address}</text>
                      {node.data.suspect_count > 0 && <><circle cx={pos.x + r - 2} cy={pos.y - r + 2} r={7} fill="var(--ops-critical)" /><text x={pos.x + r - 2} y={pos.y - r + 5.5} fontSize={7} fill="#fff" textAnchor="middle" fontWeight={700}>{node.data.suspect_count}</text></>}
                    </g>
                  )
                })}
              </svg>
            </div>
          )}

          {viewMode === 'map' && hoveredNode && (
            <div className="absolute top-4 left-4 p-3 max-w-xs z-50 pointer-events-none ops-panel-elevated">
              <div className="flex items-center gap-2 mb-2"><MapPin size={13} style={{ color: getLocationColor(hoveredNode) }} /><span className="text-[11px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{hoveredNode.data.label}</span></div>
              <p className="text-[10px] mb-2" style={{ color: 'var(--ops-text-muted)' }}>{hoveredNode.data.address}</p>
              {hoveredNode.data.suspects.length > 0 && (<div><p className="text-[9px] font-bold mb-1" style={{ color: 'var(--ops-text-secondary)' }}>{hoveredNode.data.suspect_count} suspect(s)</p>{hoveredNode.data.suspects.map((s, i) => <p key={i} className="text-[9px]" style={{ color: 'var(--ops-text-primary)' }}>• {s.person_name}{s.first_observed && <span style={{ color: 'var(--ops-text-muted)' }}> ({s.first_observed})</span>}</p>)}</div>)}
            </div>
          )}

          {loading && <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'rgba(7, 9, 14, 0.8)' }}><div className="loading-spinner" /></div>}
          {graphData && filteredNodes.length === 0 && !loading && <div className="absolute inset-0 flex items-center justify-center"><div className="text-center"><MapPin size={40} style={{ color: 'var(--ops-text-muted)', opacity: 0.2 }} /><p className="text-xs mt-3" style={{ color: 'var(--ops-text-muted)' }}>{selectedCaseIds.length === 0 ? 'Select cases to view locations.' : 'No locations match filters.'}</p></div></div>}
        </div>

        {selectedNode && (
          <div className="w-72 p-4 overflow-auto border-l animate-slide-right" style={{ background: 'var(--ops-bg-panel)', borderColor: 'var(--ops-border)' }}>
            <div className="flex items-center gap-2 mb-3"><MapPin size={14} style={{ color: getLocationColor(selectedNode, !!(highlightedSuspect && selectedNode.data.suspects.some(s => s.person_id === highlightedSuspect.id))) }} /><h3 className="text-xs font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{selectedNode.data.label}</h3></div>
            <div className="space-y-2 text-[11px]">
              <div><span style={{ color: 'var(--ops-text-muted)' }}>Address</span><p className="font-medium mt-0.5" style={{ color: 'var(--ops-text-primary)' }}>{selectedNode.data.address || 'Unknown'}</p></div>
              <div><span style={{ color: 'var(--ops-text-muted)' }}>Type</span><p className="mt-0.5"><span className="badge-ops" style={{ background: selectedNode.data.is_tower ? 'rgba(8, 145, 178, 0.1)' : 'var(--ops-bg-elevated)', color: selectedNode.data.is_tower ? TOWER_COLOR : 'var(--ops-text-secondary)' }}>{selectedNode.data.is_tower ? 'TOWER' : 'LOCATION'}</span></p></div>
            </div>
            <div className="mt-4">
              <h4 className="text-[10px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-secondary)' }}>SUSPECTS ({selectedNode.data.suspects.length})</h4>
              {selectedNode.data.suspects.length === 0 ? <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>No data.</p> : (
                <div className="space-y-1.5">{selectedNode.data.suspects.map((s, i) => (
                  <div key={i} className="p-2 rounded-lg" style={{ background: highlightedSuspect && s.person_id === highlightedSuspect.id ? 'rgba(255, 194, 61, 0.06)' : 'var(--ops-bg-elevated)', border: highlightedSuspect && s.person_id === highlightedSuspect.id ? '1px solid rgba(255, 194, 61, 0.2)' : '1px solid transparent' }}>
                    <div className="flex items-center justify-between"><span className="text-[11px] font-medium" style={{ color: 'var(--ops-text-primary)' }}>{s.person_name}{highlightedSuspect && s.person_id === highlightedSuspect.id && <span style={{ color: 'var(--ops-medium)' }}> ★</span>}</span><button onClick={() => navigate(`/entities/${s.person_id}`)} className="text-[9px]" style={{ color: 'var(--ops-accent-dim)' }}>VIEW</button></div>
                    {s.first_observed && <div className="flex items-center gap-1 mt-0.5 text-[9px]" style={{ color: 'var(--ops-text-muted)' }}><Clock size={9} /> {s.first_observed}{s.last_observed && ` → ${s.last_observed}`}</div>}
                  </div>
                ))}</div>
              )}
            </div>
            <button onClick={() => setSelectedNode(null)} className="w-full mt-4 text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>Close</button>
          </div>
        )}
      </div>
    </div>
  )
}
