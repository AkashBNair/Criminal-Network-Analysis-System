import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { ArrowLeft, Bell, AlertTriangle, CheckCircle, XCircle, Eye, Play } from 'lucide-react'

const SEVERITY_COLORS: Record<string, string> = { high: 'var(--ops-critical)', medium: 'var(--ops-medium)', low: 'var(--ops-text-muted)' }

export default function AlertsPage() {
  const { caseId } = useParams()
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedAlert, setSelectedAlert] = useState<any>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [dismissNote, setDismissNote] = useState('')

  useEffect(() => { loadAlerts() }, [caseId, statusFilter])
  const loadAlerts = async () => { try { const params: Record<string, string> = {}; if (caseId) params.case_id = caseId; if (statusFilter) params.status = statusFilter; const data = await api.getAlerts(params); setAlerts(data) } catch (err) { console.error(err) } finally { setLoading(false) } }

  const handleStatusUpdate = async (alertId: string, status: string) => { if (status === 'Dismissed' && !dismissNote) { alert('Reason required'); return } try { await api.updateAlertStatus(alertId, status, status === 'Dismissed' ? dismissNote : undefined); setDismissNote(''); setSelectedAlert(null); loadAlerts() } catch (err: any) { alert(err.message) } }

  const handleRunDetection = async () => { try { const result = await api.runDetection(); alert(result.message); loadAlerts() } catch (err: any) { alert(err.message) } }

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      <button onClick={() => navigate(`/cases/${caseId}`)} className="btn-ops mb-4"><ArrowLeft size={14} /> Back</button>
      <div className="flex items-center justify-between mb-5">
        <div><h1 className="text-lg font-bold tracking-wide" style={{ color: 'var(--ops-text-primary)' }}>ALERTS</h1><p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{alerts.length} alerts</p></div>
        <button onClick={handleRunDetection} className="btn-ops px-4 py-2 rounded-lg text-[11px] font-semibold" style={{ background: 'var(--ops-high-bg)', borderColor: 'rgba(255, 138, 61, 0.2)', color: 'var(--ops-high)' }}><Play size={14} className="inline mr-1" /> RUN DETECTION</button>
      </div>

      <div className="flex items-center gap-2 mb-4">{['', 'New', 'Under Review', 'Confirmed', 'Dismissed'].map(status => (
        <button key={status} onClick={() => setStatusFilter(status)} className="btn-ops px-3 py-1.5 rounded-lg text-[10px] font-semibold" style={statusFilter === status ? { background: 'var(--ops-accent-bg)', borderColor: 'rgba(0, 229, 255, 0.2)', color: 'var(--ops-accent)' } : {}}>
          {status || 'ALL'}
        </button>
      ))}</div>

      <div className="flex gap-5">
        <div className="flex-1 space-y-2">
          {loading ? <div className="flex items-center justify-center h-64"><div className="loading-spinner" /></div> : alerts.length === 0 ? (
            <div className="ops-panel p-12 text-center"><Bell size={40} style={{ color: 'var(--ops-text-muted)', opacity: 0.2 }} /><p className="text-xs mt-3" style={{ color: 'var(--ops-text-muted)' }}>No alerts</p></div>
          ) : alerts.map(alert => (
            <div key={alert.id} onClick={() => setSelectedAlert(alert)} className="ops-panel p-4 cursor-pointer transition-all" style={{ borderColor: selectedAlert?.id === alert.id ? 'var(--ops-border-active)' : 'var(--ops-border)' }}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <AlertTriangle size={13} style={{ color: SEVERITY_COLORS[alert.severity] || 'var(--ops-text-muted)' }} />
                    <h3 className="text-[11px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>{alert.title}</h3>
                  </div>
                  <p className="text-[10px] mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>{alert.description}</p>
                  <div className="flex items-center gap-2 text-[9px]" style={{ color: 'var(--ops-text-muted)' }}>
                    <span>{alert.alert_type}</span><span>•</span><span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{alert.detected_at ? new Date(alert.detected_at).toLocaleDateString() : ''}</span>
                  </div>
                </div>
                <span className="badge-ops" style={{ background: alert.severity === 'high' ? 'var(--ops-critical-bg)' : alert.severity === 'medium' ? 'var(--ops-medium-bg)' : 'var(--ops-bg-elevated)', color: SEVERITY_COLORS[alert.severity] || 'var(--ops-text-muted)' }}>{alert.status}</span>
              </div>
            </div>
          ))}
        </div>

        {selectedAlert && (
          <div className="w-80 ops-panel-elevated p-5 h-fit sticky top-6">
            <h2 className="text-[11px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-primary)' }}>{selectedAlert.title}</h2>
            <div className="space-y-3 text-[11px]">
              <div><p className="text-[9px] font-bold tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>DESCRIPTION</p><p style={{ color: 'var(--ops-text-secondary)' }}>{selectedAlert.description}</p></div>
              <div><p className="text-[9px] font-bold tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>EVIDENCE</p><pre className="rounded-lg p-2.5 text-[9px] overflow-auto max-h-40" style={{ background: 'var(--ops-bg-deep)', color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace", border: '1px solid var(--ops-border)' }}>{JSON.stringify(selectedAlert.supporting_evidence, null, 2)}</pre></div>
              <div className="pt-3 space-y-2" style={{ borderTop: '1px solid var(--ops-border)' }}>
                {selectedAlert.status === 'New' && <button onClick={() => handleStatusUpdate(selectedAlert.id, 'Under Review')} className="btn-ops w-full py-2 rounded-lg text-[10px] font-semibold text-center" style={{ background: 'var(--ops-medium-bg)', color: 'var(--ops-medium)' }}><Eye size={12} className="inline mr-1" /> UNDER REVIEW</button>}
                {(selectedAlert.status === 'New' || selectedAlert.status === 'Under Review') && (<>
                  <button onClick={() => handleStatusUpdate(selectedAlert.id, 'Confirmed')} className="btn-ops w-full py-2 rounded-lg text-[10px] font-semibold text-center" style={{ background: 'var(--ops-success-bg)', color: 'var(--ops-success)' }}><CheckCircle size={12} className="inline mr-1" /> CONFIRM</button>
                  <textarea value={dismissNote} onChange={(e) => setDismissNote(e.target.value)} placeholder="Dismissal reason..." className="input-ops text-[10px]" style={{ paddingLeft: 12 }} rows={2} />
                  <button onClick={() => handleStatusUpdate(selectedAlert.id, 'Dismissed')} className="btn-ops w-full py-2 rounded-lg text-[10px] font-semibold text-center"><XCircle size={12} className="inline mr-1" /> DISMISS</button>
                </>)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
