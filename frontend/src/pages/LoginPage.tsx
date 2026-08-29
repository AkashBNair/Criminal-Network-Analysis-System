import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Radio, AlertTriangle } from 'lucide-react'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/')
    } catch (err: any) {
      setError(err.message || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden" style={{ background: 'var(--ops-bg-void)' }}>
      {/* Background grid effect */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `linear-gradient(var(--ops-accent) 1px, transparent 1px), linear-gradient(90deg, var(--ops-accent) 1px, transparent 1px)`,
        backgroundSize: '40px 40px',
      }} />
      
      {/* Radial glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full" style={{
        background: 'radial-gradient(circle, rgba(0, 229, 255, 0.06) 0%, transparent 70%)',
      }} />

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{
              background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(0, 229, 255, 0.05))',
              border: '1px solid rgba(0, 229, 255, 0.25)',
              boxShadow: 'var(--ops-accent-glow-strong)',
            }}
          >
            <Radio size={32} style={{ color: 'var(--ops-accent)' }} />
          </div>
          <h1 className="text-2xl font-bold tracking-wide" style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}>
            CRIMENET
          </h1>
          <p className="mt-1 text-sm tracking-widest" style={{ color: 'var(--ops-text-muted)' }}>
            INTELLIGENCE OPERATIONS SYSTEM
          </p>
        </div>

        {/* Login card */}
        <div className="ops-panel-glow p-8">
          <h2 className="text-sm font-semibold tracking-wider mb-6" style={{ color: 'var(--ops-text-secondary)' }}>
            AUTHENTICATE
          </h2>

          {error && (
            <div
              className="flex items-center gap-2 p-3 rounded-lg mb-4 text-xs"
              style={{ background: 'var(--ops-critical-bg)', border: '1px solid rgba(255, 61, 113, 0.2)', color: 'var(--ops-critical)' }}
            >
              <AlertTriangle size={14} />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[10px] font-semibold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>
                OPERATOR ID
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input-ops"
                style={{ paddingLeft: 12, fontFamily: "'JetBrains Mono', monospace" }}
                placeholder="Enter operator ID"
                required
              />
            </div>
            <div>
              <label className="block text-[10px] font-semibold tracking-wider mb-2" style={{ color: 'var(--ops-text-muted)' }}>
                ACCESS CODE
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-ops"
                style={{ paddingLeft: 12, fontFamily: "'JetBrains Mono', monospace" }}
                placeholder="Enter access code"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-lg text-sm font-semibold tracking-wider transition-all duration-200 disabled:opacity-50"
              style={{
                background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(0, 229, 255, 0.08))',
                border: '1px solid rgba(0, 229, 255, 0.3)',
                color: 'var(--ops-accent)',
                boxShadow: 'var(--ops-glow-cyan)',
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="loading-spinner" style={{ width: 14, height: 14, borderWidth: 1.5 }} />
                  AUTHENTICATING...
                </span>
              ) : (
                'AUTHENTICATE'
              )}
            </button>
          </form>

          <div className="mt-6 pt-4" style={{ borderTop: '1px solid var(--ops-border)' }}>
            <p className="text-[10px] text-center" style={{ color: 'var(--ops-text-muted)' }}>
              Demo: <span style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>admin</span> / <span style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>admin123</span>
            </p>
          </div>
        </div>

        <p className="text-center text-[10px] mt-4 tracking-wider" style={{ color: 'var(--ops-text-muted)' }}>
          AUTHORIZED USE ONLY • ALL ACTIVITY LOGGED
        </p>
      </div>
    </div>
  )
}
