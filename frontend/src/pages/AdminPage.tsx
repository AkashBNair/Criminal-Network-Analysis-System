import { useState, useEffect } from 'react'
import { api } from '../api'
import { Shield, Users, ScrollText, Plus, Link2, CheckCircle, AlertTriangle, Clock, RefreshCw } from 'lucide-react'

export default function AdminPage() {
  const [tab, setTab] = useState<'users' | 'audit' | 'chain'>('users')
  const [users, setUsers] = useState<any[]>([])
  const [auditLogs, setAuditLogs] = useState<any[]>([])
  const [showCreateUser, setShowCreateUser] = useState(false)
  const [newUser, setNewUser] = useState({ username: '', email: '', full_name: '', password: '', role: 'investigating_officer' })

  useEffect(() => { if (tab === 'users') loadUsers(); else if (tab === 'audit') loadAuditLogs(); else if (tab === 'chain') { loadChainStatus(); verifyChain(); } }, [tab])
  const [chainStatus, setChainStatus] = useState<any>(null)
  const [chainVerification, setChainVerification] = useState<any>(null)
  const [verifying, setVerifying] = useState(false)

  const loadUsers = async () => { try { const data = await api.getUsers(); setUsers(data) } catch (err) { console.error(err) } }
  const loadAuditLogs = async () => { try { const data = await api.getAuditLog(); setAuditLogs(data) } catch (err) { console.error(err) } }
  const loadChainStatus = async () => { try { const data = await api.getChainStatus(); setChainStatus(data) } catch (err) { console.error(err) } }
  const verifyChain = async () => { setVerifying(true); try { const data = await api.verifyChain(); setChainVerification(data) } catch (err) { console.error(err) } setVerifying(false) }

  const handleCreateUser = async (e: React.FormEvent) => { e.preventDefault(); try { await api.createUser(newUser); setShowCreateUser(false); setNewUser({ username: '', email: '', full_name: '', password: '', role: 'investigating_officer' }); loadUsers() } catch (err: any) { alert(err.message) } }

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      <div className="flex items-center gap-3 mb-5">
        <Shield size={20} style={{ color: 'var(--ops-accent)' }} />
        <div><h1 className="text-lg font-bold tracking-wide" style={{ color: 'var(--ops-text-primary)' }}>ADMIN</h1><p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>User management & audit</p></div>
      </div>

      <div className="flex gap-2 mb-5">
        <button onClick={() => setTab('users')} className="btn-ops px-4 py-2 rounded-lg text-[11px] font-semibold" style={tab === 'users' ? { background: 'var(--ops-accent-bg)', borderColor: 'rgba(0, 229, 255, 0.2)', color: 'var(--ops-accent)' } : {}}><Users size={14} className="inline mr-1" /> USERS</button>
        <button onClick={() => setTab('audit')} className="btn-ops px-4 py-2 rounded-lg text-[11px] font-semibold" style={tab === 'audit' ? { background: 'var(--ops-accent-bg)', borderColor: 'rgba(0, 229, 255, 0.2)', color: 'var(--ops-accent)' } : {}}><ScrollText size={14} className="inline mr-1" /> AUDIT</button>
        <button onClick={() => setTab('chain')} className="btn-ops px-4 py-2 rounded-lg text-[11px] font-semibold" style={tab === 'chain' ? { background: 'var(--ops-accent-bg)', borderColor: 'rgba(0, 229, 255, 0.2)', color: 'var(--ops-accent)' } : {}}><Link2 size={14} className="inline mr-1" /> CHAIN</button>
      </div>

      {tab === 'users' && (
        <div>
          <div className="flex justify-end mb-4"><button onClick={() => setShowCreateUser(true)} className="btn-ops-primary px-4 py-2 rounded-lg text-[11px] font-semibold"><Plus size={14} /> ADD USER</button></div>

          {showCreateUser && (
            <div className="modal-overlay"><div className="modal-panel">
              <h3 className="text-sm font-bold tracking-wider mb-5" style={{ color: 'var(--ops-text-primary)' }}>CREATE USER</h3>
              <form onSubmit={handleCreateUser} className="space-y-3">
                <input type="text" placeholder="Username" value={newUser.username} onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} required />
                <input type="email" placeholder="Email" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} required />
                <input type="text" placeholder="Full Name" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} required />
                <input type="password" placeholder="Password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} required />
                <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })} className="select-ops w-full">
                  <option value="investigating_officer">Investigating Officer</option><option value="crime_analyst">Crime Analyst</option><option value="senior_official">Senior Official</option><option value="system_admin">System Admin</option>
                </select>
                <div className="flex gap-3 pt-2"><button type="button" onClick={() => setShowCreateUser(false)} className="btn-ops flex-1 py-2.5 rounded-lg text-[11px] font-semibold text-center">CANCEL</button><button type="submit" className="btn-ops-primary flex-1 py-2.5 rounded-lg text-[11px] font-semibold text-center">CREATE</button></div>
              </form>
            </div></div>
          )}

          <div className="ops-panel overflow-hidden">
            <table className="table-ops">
              <thead><tr><th>USER</th><th>ROLE</th><th>STATUS</th><th>CREATED</th></tr></thead>
              <tbody>{users.map(user => (
                <tr key={user.id}>
                  <td><p className="font-medium" style={{ color: 'var(--ops-text-primary)' }}>{user.full_name}</p><p className="text-[9px]" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>@{user.username} • {user.email}</p></td>
                  <td><span className="badge-ops" style={{ background: 'var(--ops-accent-bg)', color: 'var(--ops-accent)' }}>{user.role.replace('_', ' ')}</span></td>
                  <td><span className="badge-ops" style={{ background: user.is_active ? 'var(--ops-success-bg)' : 'var(--ops-critical-bg)', color: user.is_active ? 'var(--ops-success)' : 'var(--ops-critical)' }}>{user.is_active ? 'ACTIVE' : 'INACTIVE'}</span></td>
                  <td className="text-[10px] font-mono" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'audit' && (
        <div className="ops-panel overflow-hidden">
          <table className="table-ops">
            <thead><tr><th>TIMESTAMP</th><th>USER</th><th>ACTION</th><th>RESOURCE</th></tr></thead>
            <tbody>{auditLogs.map(log => (
              <tr key={log.id}>
                <td className="text-[10px] font-mono" style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}>{log.timestamp ? new Date(log.timestamp).toLocaleString() : 'N/A'}</td>
                <td className="text-[10px]" style={{ color: 'var(--ops-text-secondary)' }}>{log.user_id?.slice(0, 8)}...</td>
                <td><span className="badge-ops">{log.action}</span></td>
                <td className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{log.resource_type && `${log.resource_type}:${log.resource_id?.slice(0, 8)}`}</td>
              </tr>
            ))}</tbody>
          </table>
          {auditLogs.length === 0 && <div className="p-8 text-center text-[11px]" style={{ color: 'var(--ops-text-muted)' }}>No audit logs</div>}
        </div>
      )}

      {tab === 'chain' && (
        <div className="space-y-4">
          {/* Chain Status Cards */}
          {chainStatus && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="ops-panel p-4">
                <p className="text-[9px] font-mono uppercase tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>Total Entries</p>
                <p className="text-2xl font-bold" style={{ color: 'var(--ops-text-primary)' }}>{chainStatus.total_entries}</p>
              </div>
              <div className="ops-panel p-4">
                <p className="text-[9px] font-mono uppercase tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>Chained</p>
                <p className="text-2xl font-bold" style={{ color: 'var(--ops-success)' }}>{chainStatus.chained_entries}</p>
              </div>
              <div className="ops-panel p-4">
                <p className="text-[9px] font-mono uppercase tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>Unchained</p>
                <p className="text-2xl font-bold" style={{ color: chainStatus.unchained_entries > 0 ? 'var(--ops-warning)' : 'var(--ops-success)' }}>{chainStatus.unchained_entries}</p>
              </div>
              <div className="ops-panel p-4">
                <p className="text-[9px] font-mono uppercase tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>Chain Integrity</p>
                <div className="flex items-center gap-2">
                  {chainStatus.chain_integrity === 'full' ? (
                    <><CheckCircle size={18} style={{ color: 'var(--ops-success)' }} /><span className="text-sm font-bold" style={{ color: 'var(--ops-success)' }}>FULL</span></>
                  ) : (
                    <><AlertTriangle size={18} style={{ color: 'var(--ops-warning)' }} /><span className="text-sm font-bold" style={{ color: 'var(--ops-warning)' }}>PARTIAL</span></>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Verify Button */}
          <div className="flex items-center gap-3">
            <button onClick={verifyChain} disabled={verifying} className="btn-ops-primary px-5 py-2.5 rounded-lg text-[11px] font-semibold">
              <RefreshCw size={14} className={`inline mr-2 ${verifying ? 'animate-spin' : ''}`} />
              {verifying ? 'VERIFYING...' : 'VERIFY CHAIN INTEGRITY'}
            </button>
            {chainStatus && (
              <span className="text-[10px] font-mono" style={{ color: 'var(--ops-text-muted)' }}>
                Last block: #{chainStatus.last_block_index} • Hash: {chainStatus.last_block_hash}
              </span>
            )}
          </div>

          {/* Verification Result */}
          {chainVerification && (
            <div className="ops-panel p-5">
              <div className="flex items-center gap-3 mb-4">
                {chainVerification.is_valid ? (
                  <><CheckCircle size={24} style={{ color: 'var(--ops-success)' }} /><div><h3 className="text-sm font-bold tracking-wider" style={{ color: 'var(--ops-success)' }}>CHAIN VERIFIED — INTEGRITY CONFIRMED</h3><p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>No tampering detected across {chainVerification.verified_blocks} blocks</p></div></>
                ) : (
                  <><AlertTriangle size={24} style={{ color: 'var(--ops-critical)' }} /><div><h3 className="text-sm font-bold tracking-wider" style={{ color: 'var(--ops-critical)' }}>CHAIN TAMPERING DETECTED</h3><p className="text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>{chainVerification.error_message}</p></div></>
                )}
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg" style={{ background: 'var(--ops-bg-secondary)' }}>
                  <p className="text-[9px] font-mono uppercase tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>Blocks Checked</p>
                  <p className="text-lg font-bold" style={{ color: 'var(--ops-text-primary)' }}>{chainVerification.total_blocks}</p>
                </div>
                <div className="p-3 rounded-lg" style={{ background: 'var(--ops-bg-secondary)' }}>
                  <p className="text-[9px] font-mono uppercase tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>Verified OK</p>
                  <p className="text-lg font-bold" style={{ color: 'var(--ops-success)' }}>{chainVerification.verified_blocks}</p>
                </div>
                <div className="p-3 rounded-lg" style={{ background: 'var(--ops-bg-secondary)' }}>
                  <p className="text-[9px] font-mono uppercase tracking-wider mb-1" style={{ color: 'var(--ops-text-muted)' }}>Verification Time</p>
                  <p className="text-lg font-bold" style={{ color: 'var(--ops-text-primary)' }}>{chainVerification.duration_ms?.toFixed(1)}ms</p>
                </div>
              </div>

              {!chainVerification.is_valid && chainVerification.tampered_audit_log_id && (
                <div className="mt-4 p-3 rounded-lg border" style={{ background: 'var(--ops-critical-bg)', borderColor: 'rgba(255, 71, 87, 0.2)' }}>
                  <p className="text-[10px] font-mono" style={{ color: 'var(--ops-critical)' }}>
                    Tampered Block Index: #{chainVerification.first_tampered_block_index}
                  </p>
                  <p className="text-[10px] font-mono" style={{ color: 'var(--ops-critical)' }}>
                    Audit Log ID: {chainVerification.tampered_audit_log_id}
                  </p>
                  <p className="text-[10px] font-mono mt-1" style={{ color: 'var(--ops-text-muted)' }}>
                    Expected: {chainVerification.expected_hash?.slice(0, 32)}...
                  </p>
                  <p className="text-[10px] font-mono" style={{ color: 'var(--ops-critical)' }}>
                    Found: {chainVerification.actual_hash?.slice(0, 32)}...
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Explanation */}
          <div className="ops-panel p-4">
            <h4 className="text-[11px] font-bold tracking-wider mb-2" style={{ color: 'var(--ops-text-primary)' }}>HOW IT WORKS</h4>
            <div className="space-y-2 text-[10px]" style={{ color: 'var(--ops-text-muted)' }}>
              <p>• Every audit log entry is SHA-256 hashed and chained to the previous entry</p>
              <p>• Each block stores the hash of the prior block, forming an immutable chain</p>
              <p>• Any modification to a historical entry breaks the chain and is detected on verification</p>
              <p>• New entries added after verification are automatically chained</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
