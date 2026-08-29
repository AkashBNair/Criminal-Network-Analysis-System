import { useState, useEffect } from 'react'
import { api } from '../api'
import {
  Activity, Phone, DollarSign, MapPin, Users, Shield,
  Play, Filter, ChevronDown, ChevronRight, Zap, Eye,
  AlertTriangle, CheckCircle, XCircle, RefreshCw, Layers
} from 'lucide-react'

interface Alert {
  id: string
  alert_type: string
  title: string
  description: string
  severity: string
  status: string
  case_id: string
  detected_at: string
  involved_entity_ids: string[]
  supporting_evidence: Record<string, any>
}

const PATTERN_CONFIG: Record<string, {
  icon: any
  label: string
  color: string
  bg: string
  description: string
  plainLanguage: string
}> = {
  'Communication Burst': {
    icon: Phone,
    label: 'COMMUNICATION BURST',
    color: '#00e5ff',
    bg: 'rgba(0, 229, 255, 0.08)',
    description: 'Unusual spike in calls between two people',
    plainLanguage: 'Two people who normally don\'t talk suddenly started calling each other a lot — possibly coordinating around an event.',
  },
  'Circular Transaction': {
    icon: DollarSign,
    label: 'FINANCIAL PATTERN',
    color: '#f59e0b',
    bg: 'rgba(245, 158, 11, 0.08)',
    description: 'Suspicious money flow detected',
    plainLanguage: 'Money is moving in circles between accounts — or being split into small amounts to avoid detection. This is a classic money laundering or structuring signal.',
  },
  'Cross-Case Match': {
    icon: Users,
    label: 'CROSS-CASE LINK',
    color: '#f43f5e',
    bg: 'rgba(244, 63, 94, 0.08)',
    description: 'Same person/phone/vehicle appears in multiple unrelated cases',
    plainLanguage: 'This is the most important finding — someone or something connects cases that were filed separately. They might be part of one larger criminal network.',
  },
  'Shared Phone Number': {
    icon: Phone,
    label: 'SHARED PHONE',
    color: '#a855f7',
    bg: 'rgba(168, 85, 247, 0.08)',
    description: 'Same phone number used across cases',
    plainLanguage: 'A phone number shows up in multiple investigations — the same device is being used by people connected to different crimes.',
  },
  'Shared Address': {
    icon: MapPin,
    label: 'SHARED LOCATION',
    color: '#10b981',
    bg: 'rgba(16, 185, 129, 0.08)',
    description: 'Same address linked to different suspects',
    plainLanguage: 'Two or more suspects share an address — they may be operating from the same base or safe house.',
  },
}

const SEVERITY_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  high: { color: '#f43f5e', bg: 'rgba(244, 63, 94, 0.12)', label: 'HIGH' },
  medium: { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)', label: 'MEDIUM' },
  low: { color: '#64748b', bg: 'rgba(100, 116, 139, 0.12)', label: 'LOW' },
}

const CONFIDENCE_CONFIG: Record<string, { color: string; label: string; description: string }> = {
  confirmed: { color: '#10b981', label: 'CONFIRMED', description: 'Directly supported by evidence' },
  statistically_unusual: { color: '#f59e0b', label: 'SUSPICIOUS', description: 'Unusual pattern — needs review' },
  unexplained: { color: '#64748b', label: 'NOTED', description: 'Flagged for tracking — may be innocent' },
}

export default function PatternsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [filterType, setFilterType] = useState<string>('')
  const [filterSeverity, setFilterSeverity] = useState<string>('')
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null)
  const [cases, setCases] = useState<any[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([])
  const [showCaseSelector, setShowCaseSelector] = useState(true)
  const [hasRun, setHasRun] = useState(false)

  useEffect(() => { api.getCases().then(setCases).catch(console.error) }, [])

  const loadAlerts = async () => {
    try {
      setLoading(true)
      const data = await api.getAlerts()
      setAlerts(Array.isArray(data) ? data : data.alerts || [])
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  const handleRunDetection = async () => {
    try {
      setRunning(true)
      setHasRun(true)
      await api.runDetection()
      await loadAlerts()
    } catch (err: any) { alert(err.message) }
    finally { setRunning(false) }
  }

  // Group alerts by type
  const grouped = alerts.reduce((acc, alert) => {
    const type = alert.alert_type || 'Other'
    if (!acc[type]) acc[type] = []
    acc[type].push(alert)
    return acc
  }, {} as Record<string, Alert[]>)

  // Filter
  const filteredGrouped = Object.entries(grouped).reduce((acc, [type, typeAlerts]) => {
    const filtered = typeAlerts.filter(a => {
      if (filterType && a.alert_type !== filterType) return false
      if (filterSeverity && a.severity !== filterSeverity) return false
      return true
    })
    if (filtered.length > 0) acc[type] = filtered
    return acc
  }, {} as Record<string, Alert[]>)

  const totalHigh = alerts.filter(a => a.severity === 'high').length
  const totalMedium = alerts.filter(a => a.severity === 'medium').length
  const totalLow = alerts.filter(a => a.severity === 'low').length
  const totalConfirmed = alerts.filter(a => a.supporting_evidence?.confidence === 'confirmed').length

  return (
    <div className="max-w-[1400px] mx-auto animate-fade-in">
      {/* Header */}
      <div className="ops-panel p-5 mb-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'var(--ops-critical-bg)', border: '1px solid rgba(244, 63, 94, 0.2)' }}>
              <Activity size={20} style={{ color: 'var(--ops-critical)' }} />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-wide" style={{ color: 'var(--ops-text-primary)' }}>
                SUSPICIOUS PATTERNS
              </h1>
              <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>
                Automated detection of criminal patterns across all cases
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowCaseSelector(!showCaseSelector)}
            className={`btn-ops ${showCaseSelector ? 'active' : ''}`}
          ><Layers size={13} /> Cases ({selectedCaseIds.length || 'All'})</button>
          <button
            onClick={handleRunDetection}
            disabled={running}
            className="btn-ops px-5 py-2.5 rounded-lg text-[11px] font-semibold flex items-center gap-2"
            style={{ background: 'var(--ops-critical-bg)', borderColor: 'rgba(244, 63, 94, 0.2)', color: 'var(--ops-critical)' }}
          >
            {running ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
            {running ? 'SCANNING...' : 'RUN DETECTION'}
          </button>
        </div>
        {showCaseSelector && (
          <div className="mt-3 p-3 rounded-lg" style={{ background: 'var(--ops-bg-deep)', border: '1px solid var(--ops-border)' }}>
            <p className="text-[9px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>SELECT CASES:</p>
            <div className="flex flex-wrap gap-2">{cases.map(c => (<label key={c.id} className="flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer" style={{ background: 'var(--ops-bg-panel)', border: '1px solid var(--ops-border)' }}><input type="checkbox" checked={selectedCaseIds.includes(c.id)} onChange={() => setSelectedCaseIds(prev => prev.includes(c.id) ? prev.filter(x => x !== c.id) : [...prev, c.id])} className="checkbox-ops" style={{ width: 14, height: 14 }} /><span className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>{c.case_number}</span></label>))}</div>
            <p className="text-[9px] mt-1" style={{ color: 'var(--ops-text-muted)' }}>Leave empty = all cases</p>
          </div>
        )}
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        {[
          { label: 'TOTAL PATTERNS', value: alerts.length, color: 'var(--ops-accent)' },
          { label: 'HIGH PRIORITY', value: totalHigh, color: '#f43f5e' },
          { label: 'MEDIUM', value: totalMedium, color: '#f59e0b' },
          { label: 'LOW / NOTED', value: totalLow, color: '#64748b' },
          { label: 'CONFIRMED', value: totalConfirmed, color: '#10b981' },
        ].map(m => (
          <div key={m.label} className="metric-card">
            <span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>{m.label}</span>
            <span className="text-xl font-bold mt-1 block" style={{ color: m.color, fontFamily: "'JetBrains Mono', monospace" }}>{m.value}</span>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="ops-panel p-3 mb-4 flex items-center gap-3 flex-wrap">
        <Filter size={13} style={{ color: 'var(--ops-text-muted)' }} />
        <span className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>FILTER:</span>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="select-ops text-[10px]"
        >
          <option value="">All Pattern Types</option>
          {Object.keys(grouped).map(type => (
            <option key={type} value={type}>{type} ({grouped[type].length})</option>
          ))}
        </select>
        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          className="select-ops text-[10px]"
        >
          <option value="">All Severities</option>
          <option value="high">High Only</option>
          <option value="medium">Medium Only</option>
          <option value="low">Low Only</option>
        </select>
        {(filterType || filterSeverity) && (
          <button
            onClick={() => { setFilterType(''); setFilterSeverity('') }}
            className="btn-ops text-[9px] px-2 py-1"
          >
            CLEAR
          </button>
        )}
      </div>

      {!hasRun && !loading ? (
        <div className="ops-panel p-16 text-center">
          <Activity size={48} style={{ color: 'var(--ops-text-muted)', opacity: 0.15 }} />
          <p className="text-sm mt-3" style={{ color: 'var(--ops-text-muted)' }}>Select cases above and click RUN DETECTION to scan for suspicious patterns</p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--ops-text-muted)', opacity: 0.6 }}>Only patterns from your selected cases will appear here</p>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="loading-spinner" />
        </div>
      ) : Object.keys(filteredGrouped).length === 0 ? (
        <div className="ops-panel p-16 text-center">
          <Activity size={48} style={{ color: 'var(--ops-text-muted)', opacity: 0.15 }} />
          <p className="text-sm mt-3" style={{ color: 'var(--ops-text-muted)' }}>No patterns detected</p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--ops-text-muted)' }}>
            Click "Run Detection" to scan for suspicious patterns
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {Object.entries(filteredGrouped).map(([type, typeAlerts]) => {
            const config = PATTERN_CONFIG[type] || {
              icon: AlertTriangle,
              label: type.toUpperCase(),
              color: '#64748b',
              bg: 'rgba(100, 116, 139, 0.08)',
              description: 'Detected pattern',
              plainLanguage: 'A suspicious pattern was detected in the data.',
            }
            const Icon = config.icon
            const isExpanded = expandedGroup === type

            return (
              <div key={type} className="ops-panel overflow-hidden" style={{ borderColor: `${config.color}20` }}>
                {/* Group Header */}
                <div
                  className="flex items-center gap-4 px-5 py-4 cursor-pointer"
                  onClick={() => setExpandedGroup(isExpanded ? null : type)}
                  style={{ background: config.bg }}
                >
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ background: `${config.color}15`, border: `1px solid ${config.color}30` }}>
                    <Icon size={18} style={{ color: config.color }} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-xs font-bold tracking-wide" style={{ color: 'var(--ops-text-primary)' }}>
                        {config.label}
                      </h3>
                      <span className="badge-ops" style={{ background: 'var(--ops-bg-elevated)', color: 'var(--ops-text-muted)', fontSize: 9 }}>
                        {typeAlerts.length} detected
                      </span>
                    </div>
                    <p className="text-[10px] mt-0.5" style={{ color: 'var(--ops-text-secondary)' }}>
                      {config.description}
                    </p>
                  </div>
                  {/* Severity summary */}
                  <div className="flex items-center gap-2">
                    {typeAlerts.filter(a => a.severity === 'high').length > 0 && (
                      <span className="badge-ops" style={{ background: SEVERITY_CONFIG.high.bg, color: SEVERITY_CONFIG.high.color, fontSize: 9 }}>
                        {typeAlerts.filter(a => a.severity === 'high').length} HIGH
                      </span>
                    )}
                    {typeAlerts.filter(a => a.severity === 'medium').length > 0 && (
                      <span className="badge-ops" style={{ background: SEVERITY_CONFIG.medium.bg, color: SEVERITY_CONFIG.medium.color, fontSize: 9 }}>
                        {typeAlerts.filter(a => a.severity === 'medium').length} MED
                      </span>
                    )}
                  </div>
                  {isExpanded ? <ChevronDown size={14} style={{ color: 'var(--ops-text-muted)' }} /> : <ChevronRight size={14} style={{ color: 'var(--ops-text-muted)' }} />}
                </div>

                {/* Plain Language Explanation */}
                {isExpanded && (
                  <div className="px-5 py-3" style={{ background: 'var(--ops-bg-deep)', borderTop: '1px solid var(--ops-border)' }}>
                    <div className="flex items-start gap-3 p-3 rounded-lg" style={{ background: `${config.color}08`, border: `1px solid ${config.color}15` }}>
                      <Zap size={14} style={{ color: config.color, flexShrink: 0, marginTop: 2 }} />
                      <div>
                        <p className="text-[10px] font-bold mb-1" style={{ color: config.color }}>WHAT THIS MEANS</p>
                        <p className="text-[11px] leading-relaxed" style={{ color: 'var(--ops-text-secondary)' }}>
                          {config.plainLanguage}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Individual Alerts */}
                {isExpanded && (
                  <div className="divide-y" style={{ borderColor: 'var(--ops-border)' }}>
                    {typeAlerts.map(alert => {
                      const sev = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.low
                      const conf = CONFIDENCE_CONFIG[alert.supporting_evidence?.confidence] || CONFIDENCE_CONFIG.unexplained

                      return (
                        <div
                          key={alert.id}
                          className="px-5 py-3 cursor-pointer transition-colors"
                          style={{ background: selectedAlert?.id === alert.id ? 'var(--ops-bg-elevated)' : 'transparent' }}
                          onClick={() => setSelectedAlert(selectedAlert?.id === alert.id ? null : alert)}
                          onMouseEnter={(e) => { if (selectedAlert?.id !== alert.id) e.currentTarget.style.background = 'var(--ops-bg-panel)' }}
                          onMouseLeave={(e) => { if (selectedAlert?.id !== alert.id) e.currentTarget.style.background = 'transparent' }}
                        >
                          <div className="flex items-start gap-3">
                            <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: sev.color, boxShadow: `0 0 6px ${sev.color}60` }} />
                            <div className="flex-1 min-w-0">
                              <h4 className="text-[11px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>
                                {alert.title}
                              </h4>
                              <p className="text-[10px] mt-0.5" style={{ color: 'var(--ops-text-muted)' }}>
                                {alert.description}
                              </p>
                              {/* Evidence Summary — Simple & Plain */}
                              <div className="flex items-center gap-3 mt-2 flex-wrap">
                                <span className="badge-ops" style={{ background: sev.bg, color: sev.color, fontSize: 9 }}>
                                  {sev.label}
                                </span>
                                <span className="badge-ops" style={{ background: `${conf.color}15`, color: conf.color, fontSize: 9 }}>
                                  {conf.label}
                                </span>
                                {alert.supporting_evidence?.entity_a && (
                                  <span className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>
                                    Between: <span style={{ color: 'var(--ops-text-secondary)' }}>
                                      {alert.supporting_evidence.entity_a}
                                    </span>
                                    {alert.supporting_evidence.entity_b && (
                                      <> &amp; <span style={{ color: 'var(--ops-text-secondary)' }}>
                                        {alert.supporting_evidence.entity_b}
                                      </span></>
                                    )}
                                  </span>
                                )}
                                {alert.supporting_evidence?.entity_name && (
                                  <span className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>
                                    Entity: <span style={{ color: 'var(--ops-text-secondary)' }}>
                                      {alert.supporting_evidence.entity_name}
                                    </span>
                                    {alert.supporting_evidence?.case_count && (
                                      <> in <span style={{ color: 'var(--ops-text-secondary)' }}>
                                        {alert.supporting_evidence.case_count} cases
                                      </span></>
                                    )}
                                  </span>
                                )}
                                {alert.supporting_evidence?.location && (
                                  <span className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>
                                    Location: <span style={{ color: 'var(--ops-text-secondary)' }}>
                                      {alert.supporting_evidence.location}
                                    </span>
                                  </span>
                                )}
                              </div>
                            </div>
                            {selectedAlert?.id === alert.id ? <Eye size={13} style={{ color: 'var(--ops-accent)' }} /> : <ChevronRight size={13} style={{ color: 'var(--ops-text-muted)' }} />}
                          </div>

                          {/* Expanded Evidence Detail */}
                          {selectedAlert?.id === alert.id && (
                            <div className="mt-3 pl-4 space-y-2" style={{ borderLeft: `2px solid ${config.color}30` }}>
                              {/* Plain Language Explanation */}
                              {alert.supporting_evidence?.explanation && (
                                <div className="p-2.5 rounded-lg" style={{ background: 'var(--ops-bg-deep)' }}>
                                  <p className="text-[9px] font-bold tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>
                                    INVESTIGATOR NOTE
                                  </p>
                                  <p className="text-[11px] leading-relaxed" style={{ color: 'var(--ops-text-secondary)' }}>
                                    {alert.supporting_evidence.explanation}
                                  </p>
                                </div>
                              )}

                              {/* Key Facts */}
                              <div className="grid grid-cols-2 gap-2">
                                {alert.supporting_evidence?.communication_count && (
                                  <div className="p-2 rounded-lg" style={{ background: 'var(--ops-bg-elevated)' }}>
                                    <p className="text-[8px] font-bold" style={{ color: 'var(--ops-text-muted)' }}>CALLS</p>
                                    <p className="text-sm font-bold" style={{ color: config.color, fontFamily: "'JetBrains Mono', monospace" }}>
                                      {alert.supporting_evidence.communication_count}
                                    </p>
                                  </div>
                                )}
                                {alert.supporting_evidence?.transfer_count && (
                                  <div className="p-2 rounded-lg" style={{ background: 'var(--ops-bg-elevated)' }}>
                                    <p className="text-[8px] font-bold" style={{ color: 'var(--ops-text-muted)' }}>TRANSFERS</p>
                                    <p className="text-sm font-bold" style={{ color: config.color, fontFamily: "'JetBrains Mono', monospace" }}>
                                      {alert.supporting_evidence.transfer_count}
                                    </p>
                                  </div>
                                )}
                                {alert.supporting_evidence?.cycle && (
                                  <div className="p-2 rounded-lg col-span-2" style={{ background: 'var(--ops-bg-elevated)' }}>
                                    <p className="text-[8px] font-bold" style={{ color: 'var(--ops-text-muted)' }}>MONEY FLOW CYCLE</p>
                                    <p className="text-[11px] font-medium" style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>
                                      {alert.supporting_evidence.cycle.join(' → ')} → {alert.supporting_evidence.cycle[0]}
                                    </p>
                                  </div>
                                )}
                                {alert.supporting_evidence?.case_details && (
                                  <div className="p-2 rounded-lg col-span-2" style={{ background: 'var(--ops-bg-elevated)' }}>
                                    <p className="text-[8px] font-bold" style={{ color: 'var(--ops-text-muted)' }}>CASES INVOLVED</p>
                                    <p className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>
                                      {alert.supporting_evidence.case_details.join(' | ')}
                                    </p>
                                  </div>
                                )}
                                {alert.supporting_evidence?.co_location_count && (
                                  <div className="p-2 rounded-lg" style={{ background: 'var(--ops-bg-elevated)' }}>
                                    <p className="text-[8px] font-bold" style={{ color: 'var(--ops-text-muted)' }}>CO-LOCATIONS</p>
                                    <p className="text-sm font-bold" style={{ color: config.color, fontFamily: "'JetBrains Mono', monospace" }}>
                                      {alert.supporting_evidence.co_location_count} times
                                    </p>
                                  </div>
                                )}
                              </div>

                              {/* Source Records */}
                              {alert.supporting_evidence?.source_records && (
                                <p className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>
                                  Evidence from {alert.supporting_evidence.source_records.length} source record(s)
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
