import { useState, useEffect } from 'react'
import { api } from '../api'
import { Shield, Users, ScrollText, Plus } from 'lucide-react'

export default function AdminPage() {
  const [tab, setTab] = useState<'users' | 'audit'>('users')
  const [users, setUsers] = useState<any[]>([])
  const [auditLogs, setAuditLogs] = useState<any[]>([])
  const [showCreateUser, setShowCreateUser] = useState(false)
  const [newUser, setNewUser] = useState({ username: '', email: '', full_name: '', password: '', role: 'investigating_officer' })

  useEffect(() => { if (tab === 'users') loadUsers(); else loadAuditLogs() }, [tab])
  const loadUsers = async () => { try { const data = await api.getUsers(); setUsers(data) } catch (err) { console.error(err) } }
  const loadAuditLogs = async () => { try { const data = await api.getAuditLog(); setAuditLogs(data) } catch (err) { console.error(err) } }

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
    </div>
  )
}
