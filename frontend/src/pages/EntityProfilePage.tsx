import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../api'
import { ArrowLeft, Network, Link2, AlertTriangle } from 'lucide-react'

const ENTITY_COLORS: Record<string, string> = { Person: 'var(--ops-accent)', Location: 'var(--ops-success)', Phone: '#8b5cf6', Vehicle: 'var(--ops-medium)', Organization: '#ec4899', Event: 'var(--ops-text-muted)' }

export default function EntityProfilePage() {
  const { entityId } = useParams()
  const navigate = useNavigate()
  const [entity, setEntity] = useState<any>(null)
  const [matches, setMatches] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { if (entityId) loadEntity() }, [entityId])
  const loadEntity = async () => { try { const data = await api.getEntity(entityId!); setEntity(data) } catch (err) { console.error(err) } finally { setLoading(false) } }
  const handleFindMatches = async () => { try { const data = await api.findMatches(entityId!); setMatches(data) } catch (err: any) { alert(err.message) } }
  const handleMerge = async (secondaryId: string) => { if (!confirm('Merge this entity?')) return; try { await api.mergeEntities(entityId!, secondaryId); loadEntity(); setMatches([]) } catch (err: any) { alert(err.message) } }

  if (loading) return <div className="flex items-center justify-center h-64"><div className="loading-spinner" /></div>
  if (!entity) return <div className="text-center py-12" style={{ color: 'var(--ops-text-muted)' }}>Entity not found</div>

  const eColor = ENTITY_COLORS[entity.entity_type] || 'var(--ops-text-muted)'

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <button onClick={() => navigate(-1)} className="btn-ops mb-4"><ArrowLeft size={14} /> Back</button>

      {entity.attributes?.partial_identity && (
        <div className="mb-4 p-3 rounded-lg" style={{ background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
          <p className="text-[11px] font-semibold" style={{ color: '#f59e0b' }}>⚠ PARTIAL IDENTITY — MAY REPRESENT MULTIPLE INDIVIDUALS</p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--ops-text-muted)' }}>{entity.attributes.partial_reason || 'This entity was extracted as a surname-only or single-word name. It may represent more than one person. Do not merge with other same-surname entities without corroborating evidence (phone number, address, DOB).'}</p>
        </div>
      )}
      <div className="ops-panel p-5 mb-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-lg font-bold" style={{ color: 'var(--ops-text-primary)' }}>{entity.name}</h1>
              <span className="badge-ops" style={{ background: `${eColor}12`, color: eColor, borderColor: `${eColor}30` }}>{entity.entity_type}</span>
              <span className="badge-ops" style={{ background: entity.is_ai_extracted ? 'rgba(139, 92, 246, 0.08)' : 'var(--ops-success-bg)', color: entity.is_ai_extracted ? '#8b5cf6' : 'var(--ops-success)' }}>{entity.is_ai_extracted ? '🤖 AI' : '✓ CONFIRMED'}</span>
              {entity.attributes?.partial_identity && (
                <span className="badge-ops" style={{ background: 'rgba(245, 158, 11, 0.12)', color: '#f59e0b', borderColor: 'rgba(245, 158, 11, 0.3)' }}>⚠ PARTIAL IDENTITY</span>
              )}
            </div>
            <div className="flex items-center gap-4 text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>
              <span>Confidence: <strong style={{ color: entity.confidence_score >= 0.85 ? 'var(--ops-success)' : entity.confidence_score >= 0.6 ? 'var(--ops-medium)' : 'var(--ops-critical)', fontFamily: "'JetBrains Mono', monospace" }}>{(entity.confidence_score * 100).toFixed(0)}%</strong></span>
              <span>{entity.relationships?.length || 0} connections</span>
            </div>
          </div>
          <div className="flex gap-2">
            <Link to={`/cases/${entity.case_id}/network`} className="btn-ops-primary px-3 py-2 rounded-lg text-[10px] font-semibold"><Network size={12} className="inline mr-1" /> GRAPH</Link>
            <button onClick={handleFindMatches} className="btn-ops px-3 py-2 rounded-lg text-[10px] font-semibold"><AlertTriangle size={12} className="inline mr-1" /> MATCHES</button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="ops-panel p-5">
          <h2 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>ATTRIBUTES</h2>
          {entity.aliases?.length > 0 && <div className="mb-3"><p className="text-[9px] mb-1" style={{ color: 'var(--ops-text-muted)' }}>ALIASES</p><div className="flex flex-wrap gap-1">{entity.aliases.map((a: string, i: number) => <span key={i} className="badge-ops" style={{ background: 'var(--ops-bg-elevated)', color: 'var(--ops-text-secondary)' }}>{a}</span>)}</div></div>}
          {entity.attributes && Object.keys(entity.attributes).length > 0 ? (
            <div className="space-y-1.5">{Object.entries(entity.attributes).map(([key, value]) => (
              <div key={key} className="flex justify-between text-[11px] py-1" style={{ borderBottom: '1px solid var(--ops-border)' }}>
                <span style={{ color: 'var(--ops-text-muted)' }}>{key.replace(/_/g, ' ')}</span>
                <span className="font-mono" style={{ color: 'var(--ops-text-primary)', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
              </div>
            ))}</div>
          ) : <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>No attributes</p>}
        </div>

        <div className="ops-panel p-5">
          <h2 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>CONNECTIONS ({entity.relationships?.length || 0})</h2>
          {entity.relationships?.length > 0 ? (
            <div className="space-y-1 max-h-96 overflow-auto">{entity.relationships.map((rel: any) => (
              <Link key={rel.id} to={`/entities/${rel.other_entity_id}`} className="flex items-center gap-2 p-2 rounded-lg transition-colors" style={{ color: 'var(--ops-text-primary)' }}>
                <div className="w-2 h-2 rounded-full" style={{ background: ENTITY_COLORS[rel.other_entity_type] || 'var(--ops-text-muted)' }} />
                <div className="flex-1 min-w-0"><p className="text-[11px] font-medium truncate">{rel.other_entity_name}</p><p className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}><Link2 size={9} className="inline" /> {rel.relationship_type}{rel.is_ai_generated && <span style={{ color: '#8b5cf6' }}> • AI</span>}</p></div>
                <span className="text-[9px] font-mono" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>w:{rel.weight?.toFixed(1)}</span>
              </Link>
            ))}</div>
          ) : <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>No connections</p>}
        </div>
      </div>

      {matches.length > 0 && (
        <div className="ops-panel p-5 mt-5">
          <h2 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>POTENTIAL DUPLICATES</h2>
          <div className="space-y-2">{matches.map(m => (
            <div key={m.entity_id} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--ops-bg-elevated)' }}>
              <div><p className="text-[11px] font-medium" style={{ color: 'var(--ops-text-primary)' }}>{m.entity_name}</p><p className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>{m.entity_type} • {(m.similarity_score * 100).toFixed(0)}% match</p></div>
              <button onClick={() => handleMerge(m.entity_id)} className="btn-ops-primary px-3 py-1.5 rounded-lg text-[10px] font-semibold">MERGE</button>
            </div>
          ))}</div>
        </div>
      )}
    </div>
  )
}
