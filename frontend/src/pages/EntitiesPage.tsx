import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { ArrowLeft, Users, Search, Plus, Eye } from 'lucide-react'

const ENTITY_COLORS: Record<string, string> = { Person: 'var(--ops-accent)', Location: 'var(--ops-success)', Phone: '#8b5cf6', Vehicle: 'var(--ops-medium)', Organization: '#ec4899', Event: 'var(--ops-text-muted)' }

export default function EntitiesPage() {
  const { caseId } = useParams()
  const navigate = useNavigate()
  const [entities, setEntities] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [newEntity, setNewEntity] = useState({ name: '', entity_type: 'Person', attributes: '{}' })

  useEffect(() => { loadEntities() }, [caseId, filter])
  const loadEntities = async () => { try { const params: Record<string, string> = { case_id: caseId! }; if (filter) params.entity_type = filter; const data = await api.getEntities(params); setEntities(data) } catch (err) { console.error(err) } finally { setLoading(false) } }

  const handleCreate = async (e: React.FormEvent) => { e.preventDefault(); try { await api.createEntity({ case_id: caseId, name: newEntity.name, entity_type: newEntity.entity_type, attributes: JSON.parse(newEntity.attributes || '{}') }); setShowCreate(false); setNewEntity({ name: '', entity_type: 'Person', attributes: '{}' }); loadEntities() } catch (err: any) { alert(err.message) } }

  const filtered = search ? entities.filter(e => e.name.toLowerCase().includes(search.toLowerCase())) : entities

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      <button onClick={() => navigate(`/cases/${caseId}`)} className="btn-ops mb-4"><ArrowLeft size={14} /> Back</button>
      <div className="flex items-center justify-between mb-5">
        <div><h1 className="text-lg font-bold tracking-wide" style={{ color: 'var(--ops-text-primary)' }}>ENTITIES</h1><p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{entities.length} in this case</p></div>
        <button onClick={() => setShowCreate(true)} className="btn-ops-primary px-4 py-2 rounded-lg text-[11px] font-semibold"><Plus size={14} /> ADD</button>
      </div>

      <div className="flex items-center gap-4 mb-4">
        <div className="relative flex-1 max-w-sm"><Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ops-text-muted)' }} /><input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." className="input-ops" /></div>
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="select-ops"><option value="">All Types</option>{Object.keys(ENTITY_COLORS).map(t => <option key={t} value={t}>{t}</option>)}</select>
      </div>

      {showCreate && (
        <div className="modal-overlay"><div className="modal-panel">
          <h3 className="text-sm font-bold tracking-wider mb-5" style={{ color: 'var(--ops-text-primary)' }}>ADD ENTITY</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div><label className="block text-[9px] font-bold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>NAME *</label><input type="text" value={newEntity.name} onChange={(e) => setNewEntity({ ...newEntity, name: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} required /></div>
            <div><label className="block text-[9px] font-bold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>TYPE *</label><select value={newEntity.entity_type} onChange={(e) => setNewEntity({ ...newEntity, entity_type: e.target.value })} className="select-ops w-full">{Object.keys(ENTITY_COLORS).map(t => <option key={t} value={t}>{t}</option>)}</select></div>
            <div className="flex gap-3 pt-2"><button type="button" onClick={() => setShowCreate(false)} className="btn-ops flex-1 py-2.5 rounded-lg text-[11px] font-semibold text-center">CANCEL</button><button type="submit" className="btn-ops-primary flex-1 py-2.5 rounded-lg text-[11px] font-semibold text-center">CREATE</button></div>
          </form>
        </div></div>
      )}

      {loading ? <div className="flex items-center justify-center h-64"><div className="loading-spinner" /></div> : filtered.length === 0 ? (
        <div className="ops-panel p-12 text-center"><Users size={40} style={{ color: 'var(--ops-text-muted)', opacity: 0.2 }} /><p className="text-xs mt-3" style={{ color: 'var(--ops-text-muted)' }}>No entities</p></div>
      ) : (
        <div className="ops-panel overflow-hidden">
          <table className="table-ops">
            <thead><tr><th>NAME</th><th>TYPE</th><th>CONFIDENCE</th><th>SOURCE</th><th>LINKS</th><th className="text-right">ACTION</th></tr></thead>
            <tbody>{filtered.map(entity => (
              <tr key={entity.id}>
                <td><p className="font-medium" style={{ color: 'var(--ops-text-primary)' }}>{entity.name}</p>{entity.aliases?.length > 0 && <p className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>aka: {entity.aliases.slice(0, 2).join(', ')}</p>}{entity.attributes?.partial_identity && <p className="text-[9px] mt-0.5 font-semibold" style={{ color: 'var(--ops-warning, #f59e0b)' }}>⚠ Partial identity — may represent multiple individuals</p>}</td>
                <td><span className="badge-ops" style={{ background: `${ENTITY_COLORS[entity.entity_type]}12`, color: ENTITY_COLORS[entity.entity_type] }}>{entity.entity_type}</span></td>
                <td><span className="font-mono font-medium" style={{ color: entity.confidence_score >= 0.85 ? 'var(--ops-success)' : entity.confidence_score >= 0.6 ? 'var(--ops-medium)' : 'var(--ops-critical)', fontFamily: "'JetBrains Mono', monospace" }}>{(entity.confidence_score * 100).toFixed(0)}%</span></td>
                <td><span className="badge-ops" style={{ background: entity.is_ai_extracted ? 'rgba(139, 92, 246, 0.08)' : 'var(--ops-success-bg)', color: entity.is_ai_extracted ? '#8b5cf6' : 'var(--ops-success)', fontSize: 9 }}>{entity.is_ai_extracted ? 'AI' : 'MANUAL'}</span></td>
                <td className="font-mono" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{entity.relationship_count}</td>
                <td className="text-right"><button onClick={() => navigate(`/entities/${entity.id}`)} className="text-[10px] font-semibold" style={{ color: 'var(--ops-accent-dim)' }}><Eye size={12} className="inline mr-1" />VIEW</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  )
}
