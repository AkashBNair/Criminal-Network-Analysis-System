import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { FolderOpen, Plus, Network, Bell, TrendingUp, Archive, RotateCcw, Lock, Search } from 'lucide-react'

export default function CasesPage() {
  const [searchParams] = useSearchParams()
  const [cases, setCases] = useState<any[]>([])
  const [archivedCases, setArchivedCases] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [activeTab, setActiveTab] = useState<'active' | 'archived'>('active')
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '')
  const [newCase, setNewCase] = useState({ case_number: '', name: '', description: '', jurisdiction: '' })
  useEffect(() => { loadCases() }, [activeTab])

  const loadCases = async () => {
    setLoading(true)
    try { const [active, archived] = await Promise.all([api.getCases(), api.getArchivedCases()]); setCases(active); setArchivedCases(archived) } catch (err) { console.error(err) } finally { setLoading(false) }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try { await api.createCase(newCase); setShowCreate(false); setNewCase({ case_number: '', name: '', description: '', jurisdiction: '' }); loadCases() } catch (err: any) { alert(err.message) }
  }

  const handleCloseCase = async (caseId: string) => { if (!confirm('Close this case?')) return; try { await api.closeCase(caseId); loadCases() } catch (err: any) { alert(err.message) } }
  const handleReopenCase = async (caseId: string) => { try { await api.reopenCase(caseId); loadCases() } catch (err: any) { alert(err.message) } }

  const displayCases = activeTab === 'active' ? cases : archivedCases
  const filtered = searchQuery ? displayCases.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.case_number.toLowerCase().includes(searchQuery.toLowerCase())) : displayCases

  return (
    <div className="max-w-[1400px] mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-5">
        <div><h1 className="text-lg font-bold tracking-wide" style={{ color: 'var(--ops-text-primary)' }}>CASES</h1><p className="text-[10px] mt-0.5" style={{ color: 'var(--ops-text-muted)' }}>{activeTab === 'active' ? cases.length : archivedCases.length} cases</p></div>
        <button onClick={() => setShowCreate(true)} className="btn-ops-primary px-4 py-2 rounded-lg text-[11px] font-semibold"><Plus size={14} /> NEW CASE</button>
      </div>

      <div className="flex items-center gap-4 mb-5">
        <div className="flex rounded-lg p-0.5" style={{ background: 'var(--ops-bg-panel)', border: '1px solid var(--ops-border)' }}>
          <button onClick={() => setActiveTab('active')} className="flex items-center gap-1.5 px-4 py-2 rounded-md text-[11px] font-semibold transition-colors" style={{ background: activeTab === 'active' ? 'var(--ops-accent-bg)' : 'transparent', color: activeTab === 'active' ? 'var(--ops-accent)' : 'var(--ops-text-muted)' }}><FolderOpen size={13} /> ACTIVE ({cases.length})</button>
          <button onClick={() => setActiveTab('archived')} className="flex items-center gap-1.5 px-4 py-2 rounded-md text-[11px] font-semibold transition-colors" style={{ background: activeTab === 'archived' ? 'var(--ops-accent-bg)' : 'transparent', color: activeTab === 'archived' ? 'var(--ops-accent)' : 'var(--ops-text-muted)' }}><Archive size={13} /> CLOSED ({archivedCases.length})</button>
        </div>
        <div className="relative flex-1 max-w-xs"><Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--ops-text-muted)' }} /><input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search cases..." className="input-ops" /></div>
      </div>

      {showCreate && (
        <div className="modal-overlay"><div className="modal-panel" style={{ maxWidth: 420 }}>
          <h3 className="text-sm font-bold tracking-wider mb-5" style={{ color: 'var(--ops-text-primary)' }}>NEW CASE</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div><label className="block text-[9px] font-bold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>CASE NUMBER *</label><input type="text" value={newCase.case_number} onChange={(e) => setNewCase({ ...newCase, case_number: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} required /></div>
            <div><label className="block text-[9px] font-bold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>CASE NAME *</label><input type="text" value={newCase.name} onChange={(e) => setNewCase({ ...newCase, name: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} required /></div>
            <div><label className="block text-[9px] font-bold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>DESCRIPTION</label><textarea value={newCase.description} onChange={(e) => setNewCase({ ...newCase, description: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} rows={3} /></div>
            <div><label className="block text-[9px] font-bold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>JURISDICTION</label><input type="text" value={newCase.jurisdiction} onChange={(e) => setNewCase({ ...newCase, jurisdiction: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} /></div>
            <div className="flex gap-3 pt-2"><button type="button" onClick={() => setShowCreate(false)} className="btn-ops flex-1 py-2.5 rounded-lg text-[11px] font-semibold text-center">CANCEL</button><button type="submit" className="btn-ops-primary flex-1 py-2.5 rounded-lg text-[11px] font-semibold text-center">CREATE</button></div>
          </form>
        </div></div>
      )}

      {loading ? <div className="flex items-center justify-center h-64"><div className="loading-spinner" /></div> : filtered.length === 0 ? (
        <div className="ops-panel p-12 text-center"><FolderOpen size={40} style={{ color: 'var(--ops-text-muted)', opacity: 0.3 }} /><p className="text-xs mt-3" style={{ color: 'var(--ops-text-muted)' }}>No cases found</p></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((c) => (
            <div key={c.id} className="ops-panel p-4 relative group transition-all duration-200" style={{ borderColor: 'var(--ops-border)' }}>
              <Link to={`/cases/${c.id}`} className="block">
                <div className="flex items-start justify-between mb-3">
                  <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: c.status === 'Archived' ? 'var(--ops-bg-elevated)' : 'var(--ops-accent-bg)', border: '1px solid var(--ops-border)' }}>
                    {c.status === 'Archived' ? <Lock size={16} style={{ color: 'var(--ops-text-muted)' }} /> : <FolderOpen size={16} style={{ color: 'var(--ops-accent)' }} />}
                  </div>
                  <span className="badge-ops" style={{ background: c.status === 'Active' ? 'var(--ops-success-bg)' : 'var(--ops-bg-elevated)', color: c.status === 'Active' ? 'var(--ops-success)' : 'var(--ops-text-muted)', borderColor: c.status === 'Active' ? 'rgba(61, 232, 122, 0.2)' : 'var(--ops-border)' }}>{c.status}</span>
                </div>
                <h3 className="text-xs font-semibold mb-0.5" style={{ color: 'var(--ops-text-primary)' }}>{c.name}</h3>
                <p className="text-[10px] mb-3" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{c.case_number}</p>
                <div className="flex items-center gap-3 text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>
                  <span className="flex items-center gap-1"><Network size={11} /> {c.entity_count}</span>
                  <span className="flex items-center gap-1"><TrendingUp size={11} /> {c.relationship_count}</span>
                  {c.alert_count > 0 && <span className="flex items-center gap-1" style={{ color: 'var(--ops-high)' }}><Bell size={11} /> {c.alert_count}</span>}
                </div>
              </Link>
              <div className="absolute top-3 right-3 z-10">
                {c.status === 'Active' ? (
                  <button onClick={(e) => { e.preventDefault(); handleCloseCase(c.id) }} className="p-1.5 rounded-lg transition-colors" style={{ color: 'var(--ops-text-muted)' }} title="Close"><Lock size={13} /></button>
                ) : (
                  <button onClick={(e) => { e.preventDefault(); handleReopenCase(c.id) }} className="p-1.5 rounded-lg transition-colors" style={{ color: 'var(--ops-success)' }} title="Reopen"><RotateCcw size={13} /></button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
