import { useState, useEffect } from 'react'
import { api } from '../api'
import { Shield, AlertTriangle, TrendingUp, Users, Layers, Search, ChevronDown, ChevronRight, Target, Network, Activity } from 'lucide-react'

interface ThreatScore { entity_id: string; name: string; threat_score: number; threat_level: string; breakdown: { centrality: number; role_severity: number; cross_case: number; activity: number }; connections: number; weighted_degree: number; cases_count: number; case_numbers: string[]; roles: Array<{ type: string; type_weight: number; crime_severity: number | null; effective_severity: number; edge_weight: number }>; crime_keywords: string[]; relationship_types: string[]; attributes: Record<string, any>; aliases: string[]; case_id: string; resolution_status: string; confidence_score: number; is_ai_extracted: boolean }

const THREAT_COLORS: Record<string, { color: string; bg: string }> = {
  CRITICAL: { color: 'var(--ops-critical)', bg: 'var(--ops-critical-bg)' },
  HIGH: { color: 'var(--ops-high)', bg: 'var(--ops-high-bg)' },
  MEDIUM: { color: 'var(--ops-medium)', bg: 'var(--ops-medium-bg)' },
  LOW: { color: 'var(--ops-low)', bg: 'var(--ops-low-bg)' },
  MINIMAL: { color: 'var(--ops-text-muted)', bg: 'var(--ops-bg-elevated)' },
}

function ThreatGauge({ score, size = 'lg' }: { score: number; size?: 'sm' | 'lg' }) {
  const r = size === 'sm' ? 22 : 42
  const sw = size === 'sm' ? 3 : 5
  const circ = 2 * Math.PI * r * 0.75
  const offset = circ - (score / 100) * circ
  let color = '#484f58'
  if (score >= 80) color = 'var(--ops-critical)'
  else if (score >= 60) color = 'var(--ops-high)'
  else if (score >= 40) color = 'var(--ops-medium)'
  else if (score >= 20) color = 'var(--ops-low)'
  const sz = size === 'sm' ? 56 : 100
  return (
    <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`}>
      <circle cx={sz / 2} cy={sz / 2} r={r} fill="none" stroke="rgba(56, 189, 248, 0.06)" strokeWidth={sw} strokeDasharray={circ} strokeLinecap="round" transform={`rotate(135 ${sz / 2} ${sz / 2})`} />
      <circle cx={sz / 2} cy={sz / 2} r={r} fill="none" stroke={color} strokeWidth={sw} strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" transform={`rotate(135 ${sz / 2} ${sz / 2})`} style={{ transition: 'stroke-dashoffset 0.6s ease-out', filter: `drop-shadow(0 0 6px ${color}40)` }} />
      <text x={sz / 2} y={size === 'sm' ? sz / 2 + 3 : sz / 2 + 5} textAnchor="middle" className={`font-bold ${size === 'sm' ? 'text-xs' : 'text-lg'}`} fill={color} fontFamily="'JetBrains Mono', monospace">{Math.round(score)}%</text>
    </svg>
  )
}

export default function ThreatScorePage() {

  const [cases, setCases] = useState<any[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([])
  const [scores, setScores] = useState<ThreatScore[]>([])
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filterLevel, setFilterLevel] = useState<string>('')
  const [showCaseSelector, setShowCaseSelector] = useState(true)
  const [hasRun, setHasRun] = useState(false)

  useEffect(() => { api.getCases().then(setCases).catch(console.error) }, [])

  const loadScores = async () => {
    if (selectedCaseIds.length === 0) return
    try { setLoading(true); setHasRun(true); const result = await api.getThreatScores(selectedCaseIds); setScores(result.scores) } catch (err) { console.error(err) } finally { setLoading(false) }
  }

  const filtered = scores.filter(s => { if (searchTerm && !s.name.toLowerCase().includes(searchTerm.toLowerCase())) return false; if (filterLevel && s.threat_level !== filterLevel) return false; return true })

  const criticalCount = scores.filter(s => s.threat_level === 'CRITICAL').length
  const highCount = scores.filter(s => s.threat_level === 'HIGH').length

  return (
    <div className="max-w-[1400px] mx-auto animate-fade-in">
      <div className="ops-panel p-4 mb-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2"><Shield size={18} style={{ color: 'var(--ops-critical)' }} /><h1 className="text-lg font-bold tracking-wide" style={{ color: 'var(--ops-text-primary)' }}>THREAT ASSESSMENT</h1></div>
          <div className="relative flex-1 max-w-xs ml-2"><Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ops-text-muted)' }} /><input type="text" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} placeholder="Search suspects..." className="input-ops" /></div>
          <button onClick={() => setShowCaseSelector(!showCaseSelector)} className={`btn-ops ${showCaseSelector ? 'active' : ''}`}><Layers size={13} /> Cases ({selectedCaseIds.length || 'All'})</button>
          <select value={filterLevel} onChange={(e) => setFilterLevel(e.target.value)} className="select-ops"><option value="">All Levels</option><option value="CRITICAL">Critical</option><option value="HIGH">High+</option><option value="MEDIUM">Medium+</option></select>
          <button onClick={loadScores} disabled={loading || selectedCaseIds.length === 0} className="btn-ops-primary px-4 py-2 rounded-lg text-[11px] font-semibold" style={{ opacity: selectedCaseIds.length === 0 ? 0.5 : 1 }}>{loading ? 'ANALYZING...' : 'RUN ANALYSIS'}</button>
        </div>
        {showCaseSelector && (
          <div className="mt-3 p-3 rounded-lg" style={{ background: 'var(--ops-bg-deep)', border: '1px solid var(--ops-border)' }}>
            <p className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>SELECT CASES:</p>
            <div className="flex flex-wrap gap-2">{cases.map(c => (<label key={c.id} className="flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer" style={{ background: 'var(--ops-bg-panel)', border: '1px solid var(--ops-border)' }}><input type="checkbox" checked={selectedCaseIds.includes(c.id)} onChange={() => setSelectedCaseIds(prev => prev.includes(c.id) ? prev.filter(x => x !== c.id) : [...prev, c.id])} className="checkbox-ops" style={{ width: 14, height: 14 }} /><span className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>{c.case_number}</span></label>))}</div>
            <p className="text-[9px] mt-1" style={{ color: 'var(--ops-text-muted)' }}>Leave empty = all cases</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {[
          { label: 'SUSPECTS', value: scores.length, icon: Users, color: 'var(--ops-accent)' },
          { label: 'CRITICAL', value: criticalCount, icon: AlertTriangle, color: 'var(--ops-critical)' },
          { label: 'HIGH THREAT', value: highCount, icon: TrendingUp, color: 'var(--ops-high)' },
          { label: 'CASES', value: new Set(scores.flatMap(s => s.case_numbers)).size, icon: Network, color: '#8b5cf6' },
        ].map(m => (
          <div key={m.label} className="metric-card">
            <div className="flex items-center gap-2 mb-1.5"><m.icon size={13} style={{ color: m.color }} /><span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>{m.label}</span></div>
            <span className="text-xl font-bold" style={{ color: m.color, fontFamily: "'JetBrains Mono', monospace" }}>{m.value}</span>
          </div>
        ))}
      </div>

      <div className="ops-panel p-3 mb-4">
        <details>
          <summary className="text-[10px] font-semibold tracking-wider cursor-pointer" style={{ color: 'var(--ops-text-secondary)' }}>HOW IS THE THREAT SCORE CALCULATED?</summary>
          <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-4 text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>
            <div><span className="font-semibold" style={{ color: 'var(--ops-text-primary)' }}>Centrality (40%)</span><p className="mt-0.5">Degree, betweenness, eigenvector — network influence.</p></div>
            <div><span className="font-semibold" style={{ color: 'var(--ops-text-primary)' }}>Role Severity (30%)</span><p className="mt-0.5">Type of crime: financial, ownership, co-accused.</p></div>
            <div><span className="font-semibold" style={{ color: 'var(--ops-text-primary)' }}>Cross-Case (20%)</span><p className="mt-0.5">Multiple cases = organized crime signal.</p></div>
            <div><span className="font-semibold" style={{ color: 'var(--ops-text-primary)' }}>Activity (10%)</span><p className="mt-0.5">Total connections and relationship weight.</p></div>
          </div>
        </details>
      </div>

      {loading && <div className="flex items-center justify-center py-12"><div className="loading-spinner" /></div>}

      {!loading && !hasRun && (
        <div className="flex flex-col items-center justify-center py-20">
          <Shield size={48} style={{ color: 'var(--ops-text-muted)', opacity: 0.3 }} />
          <p className="text-sm mt-4" style={{ color: 'var(--ops-text-muted)' }}>Select cases above and click RUN ANALYSIS to begin threat assessment</p>
          <p className="text-[10px] mt-2" style={{ color: 'var(--ops-text-muted)', opacity: 0.6 }}>Only assessed suspects from your selected cases will appear here</p>
        </div>
      )}

      {!loading && hasRun && <div className="space-y-2">
        {filtered.map((suspect, rank) => {
          const tc = THREAT_COLORS[suspect.threat_level] || THREAT_COLORS.MINIMAL
          const isExpanded = expandedId === suspect.entity_id
          return (
            <div key={suspect.entity_id} className="ops-panel overflow-hidden" style={{ borderColor: `${tc.color}25` }}>
              <div className="flex items-center gap-4 px-5 py-3 cursor-pointer" onClick={() => setExpandedId(isExpanded ? null : suspect.entity_id)}>
                <span className="text-[10px] font-bold w-6 text-center" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>#{rank + 1}</span>
                <ThreatGauge score={suspect.threat_score} size="sm" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xs font-semibold truncate" style={{ color: 'var(--ops-text-primary)' }}>{suspect.name}</h3>
                    {suspect.aliases.length > 0 && <span className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>(aka {suspect.aliases.slice(0, 2).join(', ')})</span>}
                    <span className="badge-ops" style={{ background: suspect.resolution_status === 'unresolved' ? 'var(--ops-high-bg)' : suspect.confidence_score >= 0.85 ? 'var(--ops-success-bg)' : 'var(--ops-bg-elevated)', color: suspect.resolution_status === 'unresolved' ? 'var(--ops-high)' : suspect.confidence_score >= 0.85 ? 'var(--ops-success)' : 'var(--ops-text-muted)', fontSize: 9 }}>{suspect.resolution_status === 'unresolved' ? '⚠ UNRESOLVED' : suspect.is_ai_extracted ? 'AI' : 'CONFIRMED'}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="badge-ops" style={{ background: tc.bg, color: tc.color, fontSize: 9 }}>{suspect.threat_level}</span>
                    <span className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{suspect.connections} links</span>
                    <span className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{suspect.cases_count} cases: {suspect.case_numbers.slice(0, 3).join(', ')}</span>
                  </div>
                </div>
                <div className="hidden md:flex items-center gap-4 text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>
                  <div className="text-center"><p className="text-[8px]">CENT</p><p className="font-bold" style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>{suspect.breakdown.centrality.toFixed(1)}</p></div>
                  <div className="text-center"><p className="text-[8px]">ROLE</p><p className="font-bold" style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>{suspect.breakdown.role_severity.toFixed(1)}</p></div>
                  <div className="text-center"><p className="text-[8px]">XCASE</p><p className="font-bold" style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>{suspect.breakdown.cross_case.toFixed(1)}</p></div>
                  <div className="text-center"><p className="text-[8px]">ACT</p><p className="font-bold" style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>{suspect.breakdown.activity.toFixed(1)}</p></div>
                </div>
                <div style={{ color: 'var(--ops-text-muted)' }}>{isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</div>
              </div>

              {isExpanded && (
                <div className="px-5 pb-4" style={{ borderTop: '1px solid var(--ops-border)' }}>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
                    <div>
                      <h4 className="text-[10px] font-bold tracking-wider mb-3 flex items-center gap-1" style={{ color: 'var(--ops-text-secondary)' }}><Activity size={11} /> SCORE BREAKDOWN</h4>
                      <div className="space-y-2">
                        {[
                          { label: 'Centrality', value: suspect.breakdown.centrality, color: 'var(--ops-accent)' },
                          { label: 'Role Severity', value: suspect.breakdown.role_severity, color: 'var(--ops-critical)' },
                          { label: 'Cross-Case', value: suspect.breakdown.cross_case, color: 'var(--ops-high)' },
                          { label: 'Activity', value: suspect.breakdown.activity, color: 'var(--ops-success)' },
                        ].map(bar => {
                          const maxVal = Math.max(suspect.breakdown.centrality, suspect.breakdown.role_severity, suspect.breakdown.cross_case, suspect.breakdown.activity, 1)
                          return (
                            <div key={bar.label} className="flex items-center gap-2">
                              <span className="text-[9px] w-20 text-right" style={{ color: 'var(--ops-text-muted)' }}>{bar.label}</span>
                              <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--ops-bg-elevated)' }}>
                                <div className="h-full rounded-full" style={{ width: `${(bar.value / maxVal) * 100}%`, background: bar.color, boxShadow: `0 0 6px ${bar.color}40` }} />
                              </div>
                              <span className="text-[9px] w-8 font-mono" style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>{bar.value.toFixed(1)}</span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                    <div>
                      <h4 className="text-[10px] font-bold tracking-wider mb-3 flex items-center gap-1" style={{ color: 'var(--ops-text-secondary)' }}><Target size={11} /> ROLES & ACTIVITIES</h4>
                      {suspect.roles.length > 0 ? (
                        <div className="space-y-1.5">{Object.entries(suspect.roles.reduce((acc: Record<string, { count: number; maxSev: number }>, r) => { acc[r.type] = acc[r.type] || { count: 0, maxSev: 0 }; acc[r.type].count++; acc[r.type].maxSev = Math.max(acc[r.type].maxSev, r.effective_severity); return acc }, {})).map(([type, data]) => (
                          <div key={type} className="flex items-center justify-between p-2 rounded-lg" style={{ background: 'var(--ops-bg-elevated)' }}>
                            <span className="text-[10px] font-medium" style={{ color: 'var(--ops-text-primary)' }}>{type}</span>
                            <div className="flex items-center gap-2">
                              <span className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>{data.count}x</span>
                              <div className="w-14 h-1 rounded-full overflow-hidden" style={{ background: 'var(--ops-bg-deep)' }}><div className="h-full rounded-full" style={{ width: `${data.maxSev * 100}%`, background: 'var(--ops-critical)' }} /></div>
                            </div>
                          </div>
                        ))}</div>
                      ) : <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>No role data.</p>}
                      {suspect.crime_keywords?.length > 0 && (
                        <div className="mt-3"><p className="text-[9px] font-bold tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>KEYWORDS</p><div className="flex flex-wrap gap-1">{suspect.crime_keywords.map((k: string, i: number) => <span key={i} className="badge-ops" style={{ background: 'var(--ops-critical-bg)', color: 'var(--ops-critical)', fontSize: 9 }}>{k}</span>)}</div></div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>}
    </div>
  )
}
