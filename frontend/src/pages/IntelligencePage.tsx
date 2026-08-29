import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import {
  Brain, Shield, AlertTriangle, Users, FileText, Search,
  ChevronDown, ChevronRight, ExternalLink, CheckCircle,
  HelpCircle, Target, Activity, Layers, RefreshCw
} from 'lucide-react'

interface ThreatScore {
  entity_id: string
  name: string
  threat_score: number
  threat_level: string
  breakdown: { centrality: number; role_severity: number; cross_case: number; activity: number }
  connections: number
  cases_count: number
  case_numbers: string[]
  crime_keywords: string[]
  is_cross_case_bridge: boolean
  record_count: number
}

interface Brief {
  entity_id: string
  name: string
  entity_type: string
  threat_score: number | null
  threat_level: string | null
  resolution_status: string
  confidence_score: number
  cases: Array<{ case_id: string; case_number: string; case_name: string }>
  total_relationships: number
  confirmed_relationships: number
  inferred_relationships: number
  narrative: string
  evidence_summary: {
    confirmed: Array<{
      type: string
      connected_to: string
      connected_type: string
      justification: string
      source_case: string
    }>
    inferred: Array<{
      type: string
      connected_to: string
      connected_type: string
      confidence: number
      warning: string
    }>
  }
  unresolved_threads: string[]
  aliases: string[]
  attributes: Record<string, any>
}

const THREAT_COLORS: Record<string, { color: string; bg: string }> = {
  CRITICAL: { color: '#f43f5e', bg: 'rgba(244, 63, 94, 0.12)' },
  HIGH: { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)' },
  MEDIUM: { color: '#00e5ff', bg: 'rgba(0, 229, 255, 0.08)' },
  LOW: { color: '#64748b', bg: 'rgba(100, 116, 139, 0.08)' },
  MINIMAL: { color: '#475569', bg: 'rgba(71, 85, 105, 0.08)' },
}

function ThreatGauge({ score }: { score: number }) {
  const r = 32
  const sw = 4
  const circ = 2 * Math.PI * r * 0.75
  const offset = circ - (score / 100) * circ
  let color = '#484f58'
  if (score >= 80) color = '#f43f5e'
  else if (score >= 60) color = '#f59e0b'
  else if (score >= 40) color = '#00e5ff'
  else if (score >= 20) color = '#64748b'
  return (
    <svg width={80} height={80} viewBox="0 0 80 80">
      <circle cx={40} cy={40} r={r} fill="none" stroke="rgba(56, 189, 248, 0.06)" strokeWidth={sw}
        strokeDasharray={circ} strokeLinecap="round" transform={`rotate(135 40 40)`} />
      <circle cx={40} cy={40} r={r} fill="none" stroke={color} strokeWidth={sw}
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        transform={`rotate(135 40 40)`} style={{ filter: `drop-shadow(0 0 6px ${color}40)` }} />
      <text x={40} y={44} textAnchor="middle" className="text-sm font-bold" fill={color}
        fontFamily="'JetBrains Mono', monospace">{Math.round(score)}%</text>
    </svg>
  )
}

export default function IntelligencePage() {
  const navigate = useNavigate()
  const [scores, setScores] = useState<ThreatScore[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedTarget, setSelectedTarget] = useState<ThreatScore | null>(null)
  const [brief, setBrief] = useState<Brief | null>(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [filterLevel, setFilterLevel] = useState<string>('CRITICAL')
  const [searchTerm, setSearchTerm] = useState('')
  const [cases, setCases] = useState<any[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([])
  const [showCaseSelector, setShowCaseSelector] = useState(true)
  const [hasRun, setHasRun] = useState(false)

  useEffect(() => { api.getCases().then(setCases).catch(console.error) }, [])

  const loadScores = async () => {
    if (selectedCaseIds.length === 0) return
    try {
      setLoading(true)
      setHasRun(true)
      const result = await api.getThreatScores(selectedCaseIds)
      setScores(result.scores)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const loadBrief = async (target: ThreatScore) => {
    setSelectedTarget(target)
    setBrief(null)
    setBriefLoading(true)
    try {
      const b = await api.getInvestigativeBrief(target.entity_id)
      setBrief(b)
    } catch (err) { console.error(err) }
    finally { setBriefLoading(false) }
  }

  // Filter to CRITICAL and HIGH only, plus MEDIUM if explicitly selected
  const filtered = scores.filter(s => {
    if (filterLevel === 'CRITICAL' && s.threat_level !== 'CRITICAL') return false
    if (filterLevel === 'HIGH+' && !['CRITICAL', 'HIGH'].includes(s.threat_level)) return false
    if (filterLevel === 'MEDIUM+' && s.threat_level === 'LOW') return false
    if (filterLevel === 'MEDIUM+' && s.threat_level === 'MINIMAL') return false
    if (searchTerm && !s.name.toLowerCase().includes(searchTerm.toLowerCase())) return false
    return true
  })

  const criticalTargets = scores.filter(s => s.threat_level === 'CRITICAL')
  const highTargets = scores.filter(s => s.threat_level === 'HIGH')

  return (
    <div className="max-w-[1400px] mx-auto animate-fade-in">
      {/* Header */}
      <div className="ops-panel p-5 mb-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
              <Brain size={20} style={{ color: '#f59e0b' }} />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-wide" style={{ color: 'var(--ops-text-primary)' }}>
                ACTIONABLE INTELLIGENCE
              </h1>
              <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>
                Investigative briefs for priority targets — who they are, what they did, and what to do next
              </p>
            </div>
          </div>
          <button onClick={() => setShowCaseSelector(!showCaseSelector)}
            className={`btn-ops ${showCaseSelector ? 'active' : ''}`}><Layers size={13} /> Cases ({selectedCaseIds.length || 'All'})</button>
          <button onClick={loadScores} disabled={loading || selectedCaseIds.length === 0}
            className="btn-ops px-4 py-2 rounded-lg text-[11px] font-semibold flex items-center gap-2"
            style={{ background: 'var(--ops-accent-bg)', borderColor: 'rgba(0, 229, 255, 0.2)', color: 'var(--ops-accent)', opacity: selectedCaseIds.length === 0 ? 0.5 : 1 }}>
            {loading ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />}
            {loading ? 'ANALYZING...' : 'RUN ANALYSIS'}
          </button>
        </div>
      </div>

      {showCaseSelector && (
        <div className="ops-panel p-3 mb-4">
          <p className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>SELECT CASES:</p>
          <div className="flex flex-wrap gap-2">{cases.map(c => (<label key={c.id} className="flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer" style={{ background: 'var(--ops-bg-panel)', border: '1px solid var(--ops-border)' }}><input type="checkbox" checked={selectedCaseIds.includes(c.id)} onChange={() => setSelectedCaseIds(prev => prev.includes(c.id) ? prev.filter(x => x !== c.id) : [...prev, c.id])} className="checkbox-ops" style={{ width: 14, height: 14 }} /><span className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>{c.case_number}</span></label>))}</div>
          <p className="text-[9px] mt-1" style={{ color: 'var(--ops-text-muted)' }}>Leave empty = all cases</p>
        </div>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {[
          { label: 'CRITICAL TARGETS', value: criticalTargets.length, color: '#f43f5e', icon: AlertTriangle },
          { label: 'HIGH PRIORITY', value: highTargets.length, color: '#f59e0b', icon: Shield },
          { label: 'CROSS-CASE BRIDGES', value: scores.filter(s => s.is_cross_case_bridge).length, color: '#a855f7', icon: Layers },
          { label: 'TOTAL SUSPECTS', value: scores.length, color: 'var(--ops-accent)', icon: Users },
        ].map(m => (
          <div key={m.label} className="metric-card">
            <div className="flex items-center gap-2 mb-1">
              <m.icon size={12} style={{ color: m.color }} />
              <span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>{m.label}</span>
            </div>
            <span className="text-xl font-bold" style={{ color: m.color, fontFamily: "'JetBrains Mono', monospace" }}>{m.value}</span>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="ops-panel p-3 mb-4 flex items-center gap-3 flex-wrap">
        <Target size={13} style={{ color: 'var(--ops-text-muted)' }} />
        <span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>SHOW:</span>
        {['CRITICAL', 'HIGH+', 'MEDIUM+', 'ALL'].map(level => (
          <button key={level} onClick={() => setFilterLevel(level)}
            className="btn-ops px-3 py-1.5 rounded-lg text-[10px] font-semibold"
            style={filterLevel === level ? { background: 'var(--ops-accent-bg)', borderColor: 'rgba(0, 229, 255, 0.2)', color: 'var(--ops-accent)' } : {}}>
            {level}
          </button>
        ))}
        <div className="relative flex-1 max-w-xs ml-2">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ops-text-muted)' }} />
          <input type="text" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search targets..." className="input-ops" />
        </div>
      </div>

      {!hasRun && !loading ? (
        <div className="ops-panel p-16 text-center">
          <Brain size={48} style={{ color: 'var(--ops-text-muted)', opacity: 0.15 }} />
          <p className="text-sm mt-3" style={{ color: 'var(--ops-text-muted)' }}>Select cases above and click RUN ANALYSIS to generate investigative briefs</p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--ops-text-muted)', opacity: 0.6 }}>Only priority targets from your selected cases will appear here</p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-16"><div className="loading-spinner" /></div>
      ) : (
        <div className="flex gap-5">
          {/* Target List */}
          <div className={`${selectedTarget ? 'w-96' : 'flex-1'} space-y-2 transition-all`}>
            {filtered.length === 0 ? (
              <div className="ops-panel p-12 text-center">
                <Brain size={40} style={{ color: 'var(--ops-text-muted)', opacity: 0.15 }} />
                <p className="text-sm mt-3" style={{ color: 'var(--ops-text-muted)' }}>No targets match filter</p>
              </div>
            ) : filtered.map((target, rank) => {
              const tc = THREAT_COLORS[target.threat_level] || THREAT_COLORS.MINIMAL
              const isSelected = selectedTarget?.entity_id === target.entity_id

              return (
                <div key={target.entity_id}
                  className="ops-panel overflow-hidden cursor-pointer transition-all"
                  style={{ borderColor: isSelected ? tc.color : `${tc.color}15` }}
                  onClick={() => loadBrief(target)}>
                  <div className="flex items-center gap-3 px-4 py-3">
                    <span className="text-[10px] font-bold w-5 text-center" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                      #{rank + 1}
                    </span>
                    <ThreatGauge score={target.threat_score} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-xs font-semibold truncate" style={{ color: 'var(--ops-text-primary)' }}>
                          {target.name}
                        </h3>
                        {target.is_cross_case_bridge && (
                          <span className="badge-ops" style={{ background: 'rgba(168, 85, 247, 0.12)', color: '#a855f7', fontSize: 8 }}>
                            BRIDGE
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="badge-ops" style={{ background: tc.bg, color: tc.color, fontSize: 9 }}>{target.threat_level}</span>
                        <span className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>
                          {target.connections} links · {target.cases_count} cases
                        </span>
                      </div>
                    </div>
                    {isSelected ? <ExternalLink size={12} style={{ color: tc.color }} /> : <ChevronRight size={12} style={{ color: 'var(--ops-text-muted)' }} />}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Brief Panel */}
          {selectedTarget && (
            <div className="flex-1 ops-panel-elevated p-6 h-fit sticky top-6 max-h-[calc(100vh-120px)] overflow-y-auto">
              {briefLoading ? (
                <div className="flex items-center justify-center py-12"><div className="loading-spinner" /></div>
              ) : brief ? (
                <div className="space-y-5">
                  {/* Target Header */}
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{
                        background: `${THREAT_COLORS[brief.threat_level || 'MEDIUM']?.color || '#00e5ff'}10`,
                        border: `1px solid ${THREAT_COLORS[brief.threat_level || 'MEDIUM']?.color || '#00e5ff'}30`,
                      }}>
                      <Target size={20} style={{ color: THREAT_COLORS[brief.threat_level || 'MEDIUM']?.color || '#00e5ff' }} />
                    </div>
                    <div className="flex-1">
                      <h2 className="text-sm font-bold" style={{ color: 'var(--ops-text-primary)' }}>{brief.name}</h2>
                      <div className="flex items-center gap-2 mt-1">
                        {brief.threat_level && (
                          <span className="badge-ops" style={{
                            background: THREAT_COLORS[brief.threat_level]?.bg,
                            color: THREAT_COLORS[brief.threat_level]?.color,
                            fontSize: 9
                          }}>
                            {brief.threat_level} {brief.threat_score}%
                          </span>
                        )}
                        <span className="badge-ops" style={{
                          background: brief.resolution_status === 'unresolved' ? 'rgba(245, 158, 11, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                          color: brief.resolution_status === 'unresolved' ? '#f59e0b' : '#10b981',
                          fontSize: 9
                        }}>
                          {brief.resolution_status === 'unresolved' ? 'UNRESOLVED' : 'CONFIRMED'}
                        </span>
                      </div>
                      {brief.aliases.length > 0 && (
                        <p className="text-[10px] mt-1" style={{ color: 'var(--ops-text-muted)' }}>
                          Also known as: {brief.aliases.slice(0, 3).join(', ')}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Cases */}
                  <div className="p-3 rounded-lg" style={{ background: 'var(--ops-bg-deep)' }}>
                    <p className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>CASES INVOLVED</p>
                    <div className="flex flex-wrap gap-2">
                      {brief.cases.map(c => (
                        <span key={c.case_id} className="badge-ops px-2 py-1" style={{ background: 'var(--ops-bg-elevated)', color: 'var(--ops-text-secondary)', fontSize: 10 }}>
                          {c.case_number} — {c.case_name}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Narrative — The Investigative Brief */}
                  <div className="p-4 rounded-lg" style={{ background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.05), rgba(0, 229, 255, 0.03))', border: '1px solid rgba(245, 158, 11, 0.12)' }}>
                    <div className="flex items-center gap-2 mb-3">
                      <FileText size={14} style={{ color: '#f59e0b' }} />
                      <p className="text-[10px] font-bold tracking-wider" style={{ color: '#f59e0b' }}>INVESTIGATIVE BRIEF</p>
                    </div>
                    <p className="text-[11px] leading-relaxed" style={{ color: 'var(--ops-text-secondary)' }}>
                      {brief.narrative}
                    </p>
                  </div>

                  {/* Stats Row */}
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: 'CONFIRMED', value: brief.confirmed_relationships, color: '#10b981', icon: CheckCircle },
                      { label: 'INFERRED', value: brief.inferred_relationships, color: '#f59e0b', icon: HelpCircle },
                      { label: 'TOTAL LINKS', value: brief.total_relationships, color: 'var(--ops-accent)', icon: Activity },
                    ].map(m => (
                      <div key={m.label} className="p-3 rounded-lg" style={{ background: 'var(--ops-bg-elevated)' }}>
                        <div className="flex items-center gap-1.5 mb-1">
                          <m.icon size={11} style={{ color: m.color }} />
                          <span className="text-[8px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>{m.label}</span>
                        </div>
                        <span className="text-lg font-bold" style={{ color: m.color, fontFamily: "'JetBrains Mono', monospace" }}>{m.value}</span>
                      </div>
                    ))}
                  </div>

                  {/* Confirmed Evidence */}
                  {brief.evidence_summary.confirmed.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <CheckCircle size={12} style={{ color: '#10b981' }} />
                        <p className="text-[9px] font-bold tracking-wider" style={{ color: '#10b981' }}>
                          CONFIRMED CONNECTIONS ({brief.evidence_summary.confirmed.length})
                        </p>
                      </div>
                      <div className="space-y-1.5">
                        {brief.evidence_summary.confirmed.slice(0, 8).map((e, i) => (
                          <div key={i} className="flex items-start gap-2 p-2 rounded-lg" style={{ background: 'var(--ops-bg-elevated)' }}>
                            <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: '#10b981' }} />
                            <div className="flex-1">
                              <p className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>
                                <span className="font-semibold">{e.type}</span> with{' '}
                                <span className="font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{e.connected_to}</span>
                                {e.justification && (
                                  <span style={{ color: 'var(--ops-text-muted)' }}> — {e.justification.slice(0, 80)}{e.justification.length > 80 ? '...' : ''}</span>
                                )}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Inferred Evidence — Needs Verification */}
                  {brief.evidence_summary.inferred.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <HelpCircle size={12} style={{ color: '#f59e0b' }} />
                        <p className="text-[9px] font-bold tracking-wider" style={{ color: '#f59e0b' }}>
                          INFERRED — NEEDS VERIFICATION ({brief.evidence_summary.inferred.length})
                        </p>
                      </div>
                      <div className="space-y-1.5">
                        {brief.evidence_summary.inferred.slice(0, 5).map((e, i) => (
                          <div key={i} className="flex items-start gap-2 p-2 rounded-lg" style={{ background: 'rgba(245, 158, 11, 0.04)', border: '1px solid rgba(245, 158, 11, 0.1)' }}>
                            <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: '#f59e0b' }} />
                            <div className="flex-1">
                              <p className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>
                                <span className="font-semibold">{e.type}</span> with{' '}
                                <span className="font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{e.connected_to}</span>
                              </p>
                              <p className="text-[9px] mt-0.5" style={{ color: '#f59e0b' }}>
                                ⚠ {e.warning || 'This relationship is inferred. Verify before acting.'}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Unresolved Threads */}
                  {brief.unresolved_threads.length > 0 && (
                    <div className="p-3 rounded-lg" style={{ background: 'rgba(244, 63, 94, 0.05)', border: '1px solid rgba(244, 63, 94, 0.12)' }}>
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle size={12} style={{ color: '#f43f5e' }} />
                        <p className="text-[9px] font-bold tracking-wider" style={{ color: '#f43f5e' }}>OPEN THREADS</p>
                      </div>
                      {brief.unresolved_threads.map((thread, i) => (
                        <p key={i} className="text-[10px] mb-1" style={{ color: 'var(--ops-text-secondary)' }}>
                          • {thread}
                        </p>
                      ))}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-2" style={{ borderTop: '1px solid var(--ops-border)' }}>
                    <button
                      onClick={() => navigate(`/entities/${brief.entity_id}`)}
                      className="btn-ops px-3 py-2 rounded-lg text-[10px] font-semibold flex items-center gap-1.5"
                    >
                      <ExternalLink size={11} /> Full Profile
                    </button>
                    <button
                      onClick={() => navigate('/people-network')}
                      className="btn-ops px-3 py-2 rounded-lg text-[10px] font-semibold flex items-center gap-1.5"
                    >
                      <Activity size={11} /> View in Graph
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-12 text-center">
                  <Brain size={40} style={{ color: 'var(--ops-text-muted)', opacity: 0.15 }} />
                  <p className="text-sm mt-3" style={{ color: 'var(--ops-text-muted)' }}>No brief available</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
