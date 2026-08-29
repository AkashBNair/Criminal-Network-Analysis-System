import { useState, useEffect } from 'react'
import { api } from '../api'
import { Search, AlertTriangle, MapPin, Clock, Users, Target, Shield, ChevronDown, ChevronUp, Activity, Crosshair, Layers, Zap, Brain, Eye, TrendingUp } from 'lucide-react'

interface EnhancedAnalysis {
  analysis_type: string
  cases_analyzed: number
  overall_similarity: number
  threat_assessment: string
  high_priority_signals: string[]
  component_scores: Record<string, number>
  narrative_signatures: {
    common_signatures: Record<string, { case_count: number; cases: string[]; description: string; weight: number }>
    overlap_score: number
    case_intensities: Record<string, number>
    per_case: Record<string, { signatures: string[]; intensity: number }>
  }
  escalation: {
    pattern: string
    mean_interval_days: number
    intervals: Array<{ from: string; to: string; from_date: string; to_date: string; days: number }>
    interval_differences: Array<{ between: string; difference_days: number; direction: string }>
    escalation_detected: boolean
  }
  victimology: {
    victims: Array<{ name: string; age: number; occupation: string; risk_factors: string[]; case_id: string }>
    age_range: string
    occupations: string[]
    common_risk_factors: Record<string, number>
  }
  geographic: {
    total_shared_locations: number
    shared_locations: Record<string, any>
    clustering_score: number
  }
  entity_links: {
    entity_case_map: Record<string, Record<string, string[]>>
    total_shared: number
    person_links: number
    phone_links: number
    vehicle_links: number
  }
  recommendation: string
}

const THREAT_COLORS: Record<string, string> = {
  CRITICAL: 'var(--ops-critical)',
  HIGH: 'var(--ops-high)',
  MEDIUM: 'var(--ops-medium)',
  LOW: 'var(--ops-low)',
}

const SIGNATURE_ICONS: Record<string, any> = {
  object_placement: Target,
  dead_frequency: Activity,
  trophy_taking: Eye,
  victim_vulnerability: Shield,
  occupational_targeting: Users,
  escalation_pattern: TrendingUp,
  cross_jurisdictional: MapPin,
}

const SIGNATURE_LABELS: Record<string, string> = {
  object_placement: 'OBJECT PLACEMENT',
  dead_frequency: 'DEAD FREQUENCY',
  trophy_taking: 'TROPHY TAKING',
  victim_vulnerability: 'VICTIM SELECTION',
  occupational_targeting: 'OCCUPATIONAL LINK',
  escalation_pattern: 'ESCALATION',
  cross_jurisdictional: 'CROSS-JURISDICTION',
}

function ScoreGauge({ score, size = 'lg' }: { score: number; size?: 'sm' | 'lg' }) {
  const r = size === 'sm' ? 22 : 42
  const sw = size === 'sm' ? 3 : 5
  const circ = 2 * Math.PI * r * 0.75
  const offset = circ - (score / 100) * circ
  let color = '#484f58'
  if (score >= 70) color = 'var(--ops-critical)'
  else if (score >= 40) color = 'var(--ops-high)'
  else if (score >= 20) color = 'var(--ops-medium)'
  else color = 'var(--ops-low)'
  const sz = size === 'sm' ? 56 : 100
  return (
    <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`}>
      <circle cx={sz / 2} cy={sz / 2} r={r} fill="none" stroke="rgba(56, 189, 248, 0.06)" strokeWidth={sw} strokeDasharray={circ} strokeLinecap="round" transform={`rotate(135 ${sz / 2} ${sz / 2})`} />
      <circle cx={sz / 2} cy={sz / 2} r={r} fill="none" stroke={color} strokeWidth={sw} strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" transform={`rotate(135 ${sz / 2} ${sz / 2})`} style={{ transition: 'stroke-dashoffset 0.6s ease-out', filter: `drop-shadow(0 0 6px ${color}40)` }} />
      <text x={sz / 2} y={size === 'sm' ? sz / 2 + 3 : sz / 2 + 5} textAnchor="middle" className={`font-bold ${size === 'sm' ? 'text-xs' : 'text-lg'}`} fill={color} fontFamily="'JetBrains Mono', monospace">{Math.round(score)}%</text>
    </svg>
  )
}

export default function SerialPatternsPage() {
  const [cases, setCases] = useState<any[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([])
  const [analysis, setAnalysis] = useState<EnhancedAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => { api.getCases().then(setCases).catch(console.error) }, [])

  const toggleCase = (id: string) => { setSelectedCaseIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]); setAnalysis(null) }
  const selectAll = () => setSelectedCaseIds(cases.map(c => c.id))

  const runAnalysis = async () => {
    if (selectedCaseIds.length < 2) { alert('Select at least 2 cases'); return }
    setLoading(true)
    try { const result = await api.analyzeSerialPatterns(selectedCaseIds); setAnalysis(result) }
    catch (err: any) { alert(err.message) } finally { setLoading(false) }
  }

  const filteredCases = searchQuery ? cases.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.case_number.toLowerCase().includes(searchQuery.toLowerCase())) : cases
  const components = analysis?.component_scores || {}
  const sigs = analysis?.narrative_signatures
  const esc = analysis?.escalation
  const vict = analysis?.victimology

  return (
    <div className="max-w-[1400px] mx-auto animate-fade-in">
      <h1 className="text-lg font-bold tracking-wide mb-1" style={{ color: 'var(--ops-text-primary)' }}>SERIAL PATTERN DETECTION</h1>
      <p className="text-[10px] mb-5" style={{ color: 'var(--ops-text-muted)' }}>Behavioral pattern analysis across cases. Lead-generation tool — flagged patterns require human investigator review.</p>

      {/* Case Selector */}
      <div className="ops-panel p-5 mb-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[10px] font-bold tracking-wider flex items-center gap-2" style={{ color: 'var(--ops-text-secondary)' }}><Layers size={14} /> SELECT CASES ({selectedCaseIds.length})</h2>
          <div className="flex gap-2 text-[10px]"><button onClick={selectAll} style={{ color: 'var(--ops-accent-dim)' }}>All</button><span style={{ color: 'var(--ops-text-muted)' }}>|</span><button onClick={() => { setSelectedCaseIds([]); setAnalysis(null) }} style={{ color: 'var(--ops-text-muted)' }}>Clear</button></div>
        </div>
        <div className="relative mb-3"><Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ops-text-muted)' }} /><input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search cases..." className="input-ops" /></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 mb-4">
          {filteredCases.map(c => (
            <label key={c.id} className="flex items-start gap-2 p-2.5 rounded-lg cursor-pointer transition-all" style={{ background: selectedCaseIds.includes(c.id) ? 'var(--ops-accent-bg)' : 'var(--ops-bg-deep)', border: `1px solid ${selectedCaseIds.includes(c.id) ? 'rgba(0, 229, 255, 0.2)' : 'var(--ops-border)'}` }}>
              <input type="checkbox" checked={selectedCaseIds.includes(c.id)} onChange={() => toggleCase(c.id)} className="checkbox-ops mt-0.5" />
              <div className="min-w-0"><p className="text-[11px] font-medium truncate" style={{ color: 'var(--ops-text-primary)' }}>{c.name}</p><p className="text-[9px]" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{c.case_number}</p></div>
            </label>
          ))}
        </div>
        <button onClick={runAnalysis} disabled={selectedCaseIds.length < 2 || loading} className="btn-ops-primary px-5 py-2.5 rounded-lg text-[11px] font-semibold">{loading ? 'ANALYZING PATTERNS...' : 'RUN SERIAL PATTERN ANALYSIS'}</button>
      </div>

      {/* Analysis Results */}
      {analysis && (
        <div className="space-y-4">
          {/* Threat Assessment Banner */}
          <div className="ops-panel p-5" style={{ borderColor: `${THREAT_COLORS[analysis.threat_assessment]}40` }}>
            <div className="flex items-center gap-5">
              <ScoreGauge score={analysis.overall_similarity} />
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-1">
                  <h2 className="text-sm font-bold" style={{ color: 'var(--ops-text-primary)' }}>BEHAVIORAL SIMILARITY</h2>
                  <span className="badge-ops px-3 py-1" style={{ background: `${THREAT_COLORS[analysis.threat_assessment]}20`, color: THREAT_COLORS[analysis.threat_assessment], fontSize: 10, fontWeight: 700 }}>{analysis.threat_assessment} PATTERN MATCH</span>
                </div>
                <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{analysis.cases_analyzed} cases analyzed</p>
                {analysis.high_priority_signals.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {analysis.high_priority_signals.map((signal, i) => (
                      <div key={i} className="flex items-center gap-1.5">
                        <AlertTriangle size={10} style={{ color: 'var(--ops-high)' }} />
                        <span className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>{signal}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Component Scores */}
          <div className="ops-panel p-5">
            <h2 className="text-[10px] font-bold tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--ops-text-secondary)' }}><Activity size={14} /> PATTERN DIMENSIONS</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
              {[
                { key: 'entity_linking', label: 'ENTITY LINKS', icon: Users, desc: 'Shared persons, phones, vehicles' },
                { key: 'narrative_signatures', label: 'SIGNATURES', icon: Target, desc: 'Behavioral pattern overlap' },
                { key: 'geographic_clustering', label: 'GEO CLUSTER', icon: MapPin, desc: 'Shared locations' },
                { key: 'escalation_pattern', label: 'ESCALATION', icon: TrendingUp, desc: 'Temporal acceleration' },
                { key: 'victimology', label: 'VICTIMOLOGY', icon: Shield, desc: 'Victim profile similarity' },
              ].map(dim => (
                <div key={dim.key} className="p-3 rounded-lg" style={{ background: 'var(--ops-bg-deep)', border: '1px solid var(--ops-border)' }}>
                  <div className="flex items-center gap-2 mb-2"><dim.icon size={13} style={{ color: 'var(--ops-accent)' }} /><span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>{dim.label}</span></div>
                  <div className="flex items-baseline gap-1"><span className="text-lg font-bold" style={{ color: 'var(--ops-text-primary)', fontFamily: "'JetBrains Mono', monospace" }}>{components[dim.key] ?? 0}%</span></div>
                  <p className="text-[9px] mt-1" style={{ color: 'var(--ops-text-muted)' }}>{dim.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Narrative Signatures */}
          {sigs && Object.keys(sigs.common_signatures).length > 0 && (
            <div className="ops-panel p-5">
              <h2 className="text-[10px] font-bold tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--ops-critical)' }}><Brain size={14} /> BEHAVIORAL SIGNATURES ({Object.keys(sigs.common_signatures).length} COMMON)</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
                {Object.entries(sigs.common_signatures).map(([sigType, sig]: [string, any]) => {
                  const Icon = SIGNATURE_ICONS[sigType] || Target
                  return (
                    <div key={sigType} className="p-3 rounded-lg" style={{ background: 'var(--ops-bg-deep)', border: '1px solid var(--ops-critical)', borderWidth: 2 }}>
                      <div className="flex items-center gap-2 mb-1">
                        <Icon size={13} style={{ color: 'var(--ops-critical)' }} />
                        <span className="text-[10px] font-bold" style={{ color: 'var(--ops-critical)' }}>{SIGNATURE_LABELS[sigType] || sigType.toUpperCase()}</span>
                      </div>
                      <p className="text-[9px] mb-2" style={{ color: 'var(--ops-text-muted)' }}>{sig.description}</p>
                      <div className="flex items-center gap-2">
                        <span className="badge-ops px-2 py-0.5" style={{ background: 'var(--ops-critical-bg)', color: 'var(--ops-critical)', fontSize: 9, fontWeight: 700 }}>{sig.case_count} CASES</span>
                        <span className="text-[9px]" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>weight: {(sig.weight * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  )
                })}
              </div>
              {/* Per-case signature intensity */}
              <h3 className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>PER-CASE SIGNATURE INTENSITY</h3>
              <div className="space-y-1">
                {Object.entries(sigs.per_case).map(([cid, data]: [string, any]) => {
                  const caseInfo = cases.find(c => c.id === cid)
                  return (
                    <div key={cid} className="flex items-center gap-3 p-2 rounded" style={{ background: 'var(--ops-bg-deep)' }}>
                      <span className="text-[10px] w-28 truncate" style={{ color: 'var(--ops-text-primary)' }}>{caseInfo?.case_number || cid.slice(0, 8)}</span>
                      <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--ops-bg-elevated)' }}>
                        <div className="h-full rounded-full" style={{ width: `${Math.min((data.intensity / 1.6) * 100, 100)}%`, background: data.intensity > 1.2 ? 'var(--ops-critical)' : data.intensity > 0.8 ? 'var(--ops-high)' : 'var(--ops-medium)', transition: 'width 0.5s ease' }} />
                      </div>
                      <span className="text-[9px] w-10 text-right" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{data.intensity.toFixed(2)}</span>
                      <div className="flex gap-1 flex-wrap max-w-[200px]">
                        {data.signatures.map((s: string) => (
                          <span key={s} className="badge-ops" style={{ background: 'var(--ops-accent-bg)', color: 'var(--ops-accent)', fontSize: 7, padding: '1px 4px' }}>{SIGNATURE_LABELS[s]?.slice(0, 6) || s.slice(0, 6)}</span>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Escalation Analysis */}
          {esc && esc.escalation_detected && (
            <div className="ops-panel p-5">
              <h2 className="text-[10px] font-bold tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--ops-high)' }}><TrendingUp size={14} /> TEMPORAL ESCALATION</h2>
              <div className="mb-3 p-3 rounded-lg" style={{ background: 'var(--ops-bg-deep)', border: '1px solid var(--ops-border)' }}>
                <span className="text-[10px] font-bold" style={{ color: 'var(--ops-text-primary)' }}>Pattern: </span>
                <span className="text-[10px]" style={{ color: 'var(--ops-high)' }}>{esc.pattern}</span>
                <span className="text-[9px] ml-3" style={{ color: 'var(--ops-text-muted)' }}>Mean interval: {esc.mean_interval_days} days</span>
              </div>
              {/* Timeline */}
              <div className="relative ml-4">
                {esc.intervals.map((iv, i) => (
                  <div key={i} className="flex items-start gap-3 mb-4 relative">
                    <div className="flex flex-col items-center">
                      <div className="w-3 h-3 rounded-full" style={{ background: 'var(--ops-high)', border: '2px solid var(--ops-bg-deep)' }} />
                      {i < esc.intervals.length - 1 && <div className="w-0.5 h-8" style={{ background: 'var(--ops-border)' }} />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{iv.from} → {iv.to}</span>
                        <span className="badge-ops px-2 py-0.5" style={{ background: 'var(--ops-high-bg)', color: 'var(--ops-high)', fontSize: 9, fontWeight: 700 }}>{iv.days} DAYS</span>
                      </div>
                      <p className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>{iv.from_date} → {iv.to_date}</p>
                      {esc.interval_differences[i] && (
                        <p className="text-[9px] mt-0.5" style={{ color: esc.interval_differences[i].direction === 'accelerating' ? 'var(--ops-critical)' : 'var(--ops-medium)' }}>
                          Δ {esc.interval_differences[i].difference_days > 0 ? '+' : ''}{esc.interval_differences[i].difference_days} days ({esc.interval_differences[i].direction})
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Victimology */}
          {vict && vict.victims.length > 0 && (
            <div className="ops-panel p-5">
              <h2 className="text-[10px] font-bold tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--ops-text-secondary)' }}><Shield size={14} /> VICTIMOLOGY PROFILE</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
                {vict.victims.map((v, i) => (
                  <div key={i} className="p-3 rounded-lg" style={{ background: 'var(--ops-bg-deep)', border: '1px solid var(--ops-border)' }}>
                    <p className="text-[11px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{v.name}</p>
                    <p className="text-[9px]" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>Age {v.age} — {v.occupation}</p>
                    {v.risk_factors.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {v.risk_factors.map((rf, j) => (
                          <span key={j} className="badge-ops" style={{ background: 'var(--ops-high-bg)', color: 'var(--ops-high)', fontSize: 7, padding: '1px 4px' }}>{rf.replace(/_/g, ' ')}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              <div className="p-3 rounded-lg" style={{ background: 'var(--ops-bg-deep)', border: '1px solid var(--ops-border)' }}>
                <h3 className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>COMMON RISK FACTORS</h3>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(vict.common_risk_factors).sort((a, b) => b[1] - a[1]).map(([rf, count]) => (
                    <div key={rf} className="flex items-center gap-1.5">
                      <span className="text-[9px]" style={{ color: 'var(--ops-text-secondary)' }}>{rf.replace(/_/g, ' ')}</span>
                      <span className="badge-ops px-1.5 py-0.5" style={{ background: 'var(--ops-accent-bg)', color: 'var(--ops-accent)', fontSize: 8, fontWeight: 700 }}>{count}/{vict.victims.length}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Geographic & Entity Links */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Geographic */}
            {analysis.geographic && analysis.geographic.shared_locations && Object.keys(analysis.geographic.shared_locations).length > 0 && (
              <div className="ops-panel p-5">
                <h2 className="text-[10px] font-bold tracking-wider mb-3 flex items-center gap-2" style={{ color: 'var(--ops-text-secondary)' }}><MapPin size={14} /> GEOGRAPHIC CLUSTERING</h2>
                <div className="space-y-2">
                  {Object.entries(analysis.geographic.shared_locations).map(([loc, data]: [string, any]) => (
                    <div key={loc} className="p-2 rounded" style={{ background: 'var(--ops-bg-deep)', border: '1px solid var(--ops-border)' }}>
                      <span className="text-[10px] font-semibold" style={{ color: 'var(--ops-accent)' }}>{loc}</span>
                      <span className="text-[9px] ml-2" style={{ color: 'var(--ops-text-muted)' }}>— {Array.isArray(data) ? data.length : 2} cases</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Entity Links */}
            {analysis.entity_links && analysis.entity_links.entity_case_map && Object.keys(analysis.entity_links.entity_case_map).length > 0 && (
              <div className="ops-panel p-5">
                <h2 className="text-[10px] font-bold tracking-wider mb-3 flex items-center gap-2" style={{ color: 'var(--ops-text-secondary)' }}><Users size={14} /> CROSS-CASE ENTITIES</h2>
                <div className="space-y-2">
                  {Object.entries(analysis.entity_links.entity_case_map).map(([name, types]: [string, any]) => (
                    <div key={name} className="p-2 rounded" style={{ background: 'var(--ops-bg-deep)' }}>
                      <span className="text-[10px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{name}</span>
                      {Object.entries(types).map(([etype, cids]: [string, any]) => (
                        <span key={etype} className="text-[9px] ml-2" style={{ color: 'var(--ops-text-muted)' }}>— {etype} in {cids.length} cases</span>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Recommendation */}
          <div className="ops-panel p-5" style={{ borderLeft: '3px solid var(--ops-accent)' }}>
            <h2 className="text-[10px] font-bold tracking-wider mb-2 flex items-center gap-2" style={{ color: 'var(--ops-accent)' }}><Target size={14} /> INVESTIGATOR RECOMMENDATION</h2>
            <p className="text-[11px] leading-relaxed" style={{ color: 'var(--ops-text-primary)' }}>{analysis.recommendation}</p>
          </div>

          {/* Disclaimer */}
          <div className="ops-panel p-3" style={{ border: '1px solid var(--ops-high)' }}>
            <p className="text-[9px]" style={{ color: 'var(--ops-high)' }}>⚠ This tool identifies statistical patterns for investigative lead generation only. It does not determine guilt and must not be used as sole grounds for suspicion or arrest.</p>
          </div>
        </div>
      )}
    </div>
  )
}
