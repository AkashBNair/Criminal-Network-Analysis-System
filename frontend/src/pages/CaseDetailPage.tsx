import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Network, Users, Bell, Upload, FileText, ArrowLeft } from 'lucide-react'

export default function CaseDetailPage() {
  const { caseId } = useParams()
  const navigate = useNavigate()
  const [caseData, setCaseData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => { if (caseId) loadCase() }, [caseId])
  const loadCase = async () => { try { const data = await api.getCase(caseId!); setCaseData(data) } catch (err) { console.error(err) } finally { setLoading(false) } }

  if (loading) return <div className="flex items-center justify-center h-64"><div className="loading-spinner" /></div>
  if (!caseData) return <div className="text-center py-12" style={{ color: 'var(--ops-text-muted)' }}>Case not found</div>

  const quickActions = [
    { icon: Network, label: 'Network Explorer', desc: 'Entity relationships', to: `/cases/${caseId}/network`, color: 'var(--ops-accent)' },
    { icon: Users, label: 'Entities', desc: `${caseData.entity_count} tracked`, to: `/cases/${caseId}/entities`, color: 'var(--ops-success)' },
    { icon: Bell, label: 'Alerts', desc: `${caseData.alert_count} active`, to: `/cases/${caseId}/alerts`, color: 'var(--ops-high)' },
    { icon: Upload, label: 'Ingestion', desc: 'Upload documents', to: `/cases/${caseId}/ingestion`, color: '#8b5cf6' },
    { icon: FileText, label: 'Reports', desc: 'Export reports', to: `/cases/${caseId}/reports`, color: 'var(--ops-critical)' },
  ]

  return (
    <div className="max-w-5xl mx-auto animate-fade-in">
      <button onClick={() => navigate('/cases')} className="btn-ops mb-4"><ArrowLeft size={14} /> Back</button>

      <div className="ops-panel p-6 mb-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-lg font-bold" style={{ color: 'var(--ops-text-primary)' }}>{caseData.name}</h1>
              <span className="badge-ops" style={{ background: caseData.status === 'Active' ? 'var(--ops-success-bg)' : 'var(--ops-bg-elevated)', color: caseData.status === 'Active' ? 'var(--ops-success)' : 'var(--ops-text-muted)' }}>{caseData.status}</span>
            </div>
            <p className="text-[10px]" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{caseData.case_number} • {caseData.jurisdiction || 'No jurisdiction'}</p>
            {caseData.description && <p className="text-[11px] mt-2" style={{ color: 'var(--ops-text-secondary)' }}>{caseData.description}</p>}
          </div>
        </div>
        <div className="grid grid-cols-4 gap-4 mt-5 pt-4" style={{ borderTop: '1px solid var(--ops-border)' }}>
          {[{ v: caseData.entity_count, l: 'Entities' }, { v: caseData.relationship_count, l: 'Relationships' }, { v: caseData.alert_count, l: 'Alerts' }, { v: caseData.document_count, l: 'Documents' }].map(s => (
            <div key={s.l} className="text-center"><p className="text-xl font-bold" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>{s.v}</p><p className="text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>{s.l}</p></div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {quickActions.map(a => (
          <Link key={a.label} to={a.to} className="ops-panel p-4 transition-all duration-200 group" style={{ borderColor: 'var(--ops-border)' }}>
            <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: `${a.color}12`, border: `1px solid ${a.color}25` }}><a.icon size={18} style={{ color: a.color }} /></div>
            <h3 className="text-[11px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{a.label}</h3>
            <p className="text-[10px] mt-0.5" style={{ color: 'var(--ops-text-muted)' }}>{a.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
