import { useState, useEffect } from 'react'
import { api } from '../api'
import { Download, Users, Search, ChevronDown, ChevronUp, Briefcase, User, Car, MapPin, Phone, Building, FileText, AlertTriangle, Shield } from 'lucide-react'

const TYPE_ICONS: Record<string, any> = {
  user: User, car: Car, pin: MapPin, phone: Phone, building: Building, file: FileText,
}

const ROLE_COLORS: Record<string, string> = {
  accused: 'var(--ops-critical)', suspect: 'var(--ops-high)',
  witness: 'var(--ops-accent)', complainant: 'var(--ops-success)',
  victim: 'var(--ops-medium)', 'co-accused': 'var(--ops-critical)',
  financier: 'var(--ops-high)', 'kingpin': 'var(--ops-critical)',
}

function TypeBadge({ badge }: { badge: { label: string; color: string; icon: string } }) {
  const Icon = TYPE_ICONS[badge.icon] || Shield
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-bold tracking-wider"
      style={{ background: `${badge.color}15`, color: badge.color, border: `1px solid ${badge.color}30` }}>
      <Icon size={10} /> {badge.label.toUpperCase()}
    </span>
  )
}

function RoleBadge({ role }: { role: string }) {
  const color = ROLE_COLORS[role?.toLowerCase()] || 'var(--ops-text-muted)'
  return (
    <span className="badge-ops" style={{ background: `${color}15`, color, fontSize: 9 }}>
      {role?.toUpperCase() || 'UNKNOWN'}
    </span>
  )
}

export default function ReportsPage() {
  const [cases, setCases] = useState<any[]>([])
  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([])
  const [commonLinks, setCommonLinks] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [generatingPdf, setGeneratingPdf] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedPerson, setExpandedPerson] = useState<string | null>(null)
  const [expandedOther, setExpandedOther] = useState<string | null>(null)
  const [showReview, setShowReview] = useState(false)

  useEffect(() => { api.getCases().then(setCases).catch(console.error) }, [])

  const toggleCase = (caseId: string) => { setSelectedCaseIds(prev => prev.includes(caseId) ? prev.filter(id => id !== caseId) : [...prev, caseId]); setCommonLinks(null) }
  const selectAll = () => setSelectedCaseIds(cases.map(c => c.id))
  const clearSelection = () => { setSelectedCaseIds([]); setCommonLinks(null) }

  const handleFindLinks = async () => {
    if (selectedCaseIds.length < 2) { alert('Select at least 2 cases'); return }
    setLoading(true)
    try { const result = await api.findCommonLinks(selectedCaseIds); setCommonLinks(result) }
    catch (err: any) { alert(err.message) }
    finally { setLoading(false) }
  }

  const handleExportPdf = async () => {
    if (!commonLinks) return; setGeneratingPdf(true)
    try {
      const response = await api.exportCommonLinksPdf(selectedCaseIds)
      const blob = await response.blob(); const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = `common_link_report_${new Date().toISOString().slice(0, 10)}.pdf`
      document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(url); document.body.removeChild(a)
    } catch (err: any) { alert(err.message) } finally { setGeneratingPdf(false) }
  }

  const filteredCases = searchQuery ? cases.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.case_number.toLowerCase().includes(searchQuery.toLowerCase())) : cases
  const persons = commonLinks?.common_persons || []
  const otherEntities = commonLinks?.common_other_entities || []
  const needsReview = commonLinks?.needs_review || []

  return (
    <div className="max-w-[1400px] mx-auto animate-fade-in">
      <h1 className="text-lg font-bold tracking-wide mb-1" style={{ color: 'var(--ops-text-primary)' }}>COMMON LINK REPORT</h1>
      <p className="text-[10px] mb-5" style={{ color: 'var(--ops-text-muted)' }}>Find entities who appear across multiple cases. All entities show explicit type badges.</p>

      <div className="ops-panel p-5 mb-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[10px] font-bold tracking-wider flex items-center gap-2" style={{ color: 'var(--ops-text-secondary)' }}><Briefcase size={14} /> SELECT CASES ({selectedCaseIds.length})</h2>
          <div className="flex gap-2 text-[10px]"><button onClick={selectAll} style={{ color: 'var(--ops-accent-dim)' }}>All</button><span style={{ color: 'var(--ops-text-muted)' }}>|</span><button onClick={clearSelection} style={{ color: 'var(--ops-text-muted)' }}>Clear</button></div>
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
        <div className="flex items-center gap-3">
          <button onClick={handleFindLinks} disabled={selectedCaseIds.length < 2 || loading} className="btn-ops-primary px-5 py-2.5 rounded-lg text-[11px] font-semibold">{loading ? 'ANALYZING...' : 'FIND COMMON LINKS'}</button>
          {commonLinks && <button onClick={handleExportPdf} disabled={generatingPdf} className="btn-ops px-5 py-2.5 rounded-lg text-[11px] font-semibold"><Download size={13} className="inline mr-1" /> EXPORT PDF</button>}
        </div>
      </div>

      {commonLinks && (
        <div className="space-y-4">
          {/* Summary strip */}
          <div className="ops-panel p-4">
            <div className="flex items-center gap-6 flex-wrap">
              <div className="text-center"><p className="text-xl font-bold" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>{persons.length}</p><p className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>PERSONS</p></div>
              <div className="text-center"><p className="text-xl font-bold" style={{ color: '#f59e0b', fontFamily: "'JetBrains Mono', monospace" }}>{otherEntities.length}</p><p className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>OTHER ENTITIES</p></div>
              <div className="text-center"><p className="text-xl font-bold" style={{ color: needsReview.length > 0 ? 'var(--ops-high)' : 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{needsReview.length}</p><p className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>NEEDS REVIEW</p></div>
              <div className="text-center"><p className="text-xl font-bold" style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>{commonLinks.cases_analyzed}</p><p className="text-[9px] font-bold tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>CASES</p></div>
            </div>
          </div>

          {/* Persons Section */}
          {persons.length > 0 && (
            <div className="ops-panel p-5">
              <h2 className="text-[10px] font-bold tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--ops-accent)' }}><Users size={14} /> PERSONS ({persons.length})</h2>
              <div className="space-y-2">
                {persons.map((person: any) => (
                  <div key={person.name} className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--ops-border)' }}>
                    <div className="flex items-center gap-3 p-3 cursor-pointer transition-colors" onClick={() => setExpandedPerson(expandedPerson === person.name ? null : person.name)}
                      style={{ background: expandedPerson === person.name ? 'var(--ops-bg-elevated)' : 'transparent' }}>
                      <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(139, 92, 246, 0.1))', border: '1px solid var(--ops-border)' }}>
                        <span className="text-xs font-bold" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>{person.name.split(' ').map((n: string) => n[0]).join('').slice(0, 2)}</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-[11px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{person.name}</h3>
                          {person.profile?.alias && <span className="badge-ops" style={{ background: 'var(--ops-medium-bg)', color: 'var(--ops-medium)', fontSize: 9 }}>aka {person.profile.alias}</span>}
                          {person.partial_identity && <span className="badge-ops" style={{ background: 'var(--ops-high-bg)', color: 'var(--ops-high)', fontSize: 9 }}>⚠ PARTIAL</span>}
                          {/* Show role from first case */}
                          {person.cases?.[0]?.role_in_case && person.cases[0].role_in_case !== 'Unknown' && <RoleBadge role={person.cases[0].role_in_case} />}
                        </div>
                        <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{person.case_count} cases • {person.total_relationships} rels</p>
                      </div>
                      <span className="badge-ops" style={{ background: 'var(--ops-critical-bg)', color: 'var(--ops-critical)' }}>{person.case_count}</span>
                      {expandedPerson === person.name ? <ChevronUp size={14} style={{ color: 'var(--ops-text-muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--ops-text-muted)' }} />}
                    </div>
                    {expandedPerson === person.name && (
                      <div style={{ borderTop: '1px solid var(--ops-border)', background: 'var(--ops-bg-deep)' }} className="p-3">
                        <table className="table-ops">
                          <thead><tr><th>CASE</th><th>NAME</th><th>ROLE</th><th>STATUS</th></tr></thead>
                          <tbody>{person.cases?.map((c: any) => (
                            <tr key={c.case_id}>
                              <td style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>{c.case_number}</td>
                              <td style={{ color: 'var(--ops-text-primary)' }}>{c.case_name}</td>
                              <td><RoleBadge role={c.role_in_case || 'Unknown'} /></td>
                              <td><span className="badge-ops" style={{ background: c.status === 'Arrested' ? 'var(--ops-critical-bg)' : c.status === 'Absconding' ? 'var(--ops-high-bg)' : 'var(--ops-bg-elevated)', color: c.status === 'Arrested' ? 'var(--ops-critical)' : c.status === 'Absconding' ? 'var(--ops-high)' : 'var(--ops-text-muted)' }}>{c.status}</span></td>
                            </tr>
                          ))}</tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Other Entities Section */}
          {otherEntities.length > 0 && (
            <div className="ops-panel p-5">
              <h2 className="text-[10px] font-bold tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--ops-text-secondary)' }}><Car size={14} /> OTHER LINKED ENTITIES ({otherEntities.length})</h2>
              <div className="space-y-2">
                {otherEntities.map((ent: any) => (
                  <div key={`${ent.name}-${ent.entity_type}`} className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--ops-border)' }}>
                    <div className="flex items-center gap-3 p-3 cursor-pointer transition-colors" onClick={() => setExpandedOther(expandedOther === `${ent.name}-${ent.entity_type}` ? null : `${ent.name}-${ent.entity_type}`)}
                      style={{ background: expandedOther === `${ent.name}-${ent.entity_type}` ? 'var(--ops-bg-elevated)' : 'transparent' }}>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-[11px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{ent.name}</h3>
                          <TypeBadge badge={ent.type_badge} />
                        </div>
                        <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{ent.case_count} cases • {ent.total_relationships} rels</p>
                      </div>
                      <span className="badge-ops" style={{ background: 'var(--ops-bg-elevated)', color: 'var(--ops-text-secondary)' }}>{ent.case_count}</span>
                      {expandedOther === `${ent.name}-${ent.entity_type}` ? <ChevronUp size={14} style={{ color: 'var(--ops-text-muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--ops-text-muted)' }} />}
                    </div>
                    {expandedOther === `${ent.name}-${ent.entity_type}` && (
                      <div style={{ borderTop: '1px solid var(--ops-border)', background: 'var(--ops-bg-deep)' }} className="p-3">
                        <table className="table-ops">
                          <thead><tr><th>CASE</th><th>NAME</th><th>ROLE</th><th>STATUS</th></tr></thead>
                          <tbody>{ent.cases?.map((c: any) => (
                            <tr key={c.case_id}>
                              <td style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>{c.case_number}</td>
                              <td style={{ color: 'var(--ops-text-primary)' }}>{c.case_name}</td>
                              <td><span className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{c.role_in_case || '—'}</span></td>
                              <td><span className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{c.status || '—'}</span></td>
                            </tr>
                          ))}</tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Needs Review Section */}
          {needsReview.length > 0 && (
            <div className="ops-panel p-5" style={{ border: '1px solid var(--ops-high)' }}>
              <button onClick={() => setShowReview(!showReview)} className="flex items-center gap-2 w-full text-left">
                <AlertTriangle size={14} style={{ color: 'var(--ops-high)' }} />
                <h2 className="text-[10px] font-bold tracking-wider" style={{ color: 'var(--ops-high)' }}>NEEDS REVIEW ({needsReview.length})</h2>
                <span className="text-[9px] ml-auto" style={{ color: 'var(--ops-text-muted)' }}>{showReview ? 'collapse' : 'expand'}</span>
              </button>
              {showReview && (
                <div className="mt-3 space-y-1">
                  {needsReview.map((item: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 p-2 rounded" style={{ background: 'var(--ops-bg-deep)' }}>
                      <span className="text-[10px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{item.name}</span>
                      <span className="badge-ops" style={{ background: 'var(--ops-high-bg)', color: 'var(--ops-high)', fontSize: 9 }}>{item.entity_type}</span>
                      <span className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>{item.case_number}</span>
                      <span className="text-[9px] ml-auto" style={{ color: 'var(--ops-text-muted)' }}>{item.reason}</span>
                    </div>
                  ))}
                  <p className="text-[9px] mt-2" style={{ color: 'var(--ops-text-muted)' }}>⚠ These entities may represent incomplete extractions. Review before using in investigation.</p>
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {persons.length === 0 && otherEntities.length === 0 && (
            <div className="ops-panel p-8 text-center">
              <Users size={40} style={{ color: 'var(--ops-text-muted)', opacity: 0.2 }} />
              <p className="text-xs mt-3" style={{ color: 'var(--ops-text-muted)' }}>No common entities found across selected cases.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
