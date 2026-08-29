import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  Home, FolderOpen, LogOut, Search, Shield, FileText, Users,
  MapPin, AlertTriangle, ChevronLeft, ChevronRight, Radio, Activity, Brain, Crosshair
} from 'lucide-react'
import { useState } from 'react'

const navItems = [
  { to: '/', icon: Home, label: 'Dashboard', section: 'MONITOR' },
  { to: '/cases', icon: FolderOpen, label: 'Cases', section: 'MONITOR' },
  { to: '/people-network', icon: Users, label: 'People Graph', section: 'ANALYZE' },
  { to: '/threat-scores', icon: AlertTriangle, label: 'Threat Assessment', section: 'INTEL' },
  { to: '/patterns', icon: Activity, label: 'Suspicious Patterns', section: 'INTEL' },
  { to: '/intelligence', icon: Brain, label: 'Actionable Intel', section: 'INTEL' },
  { to: '/reports', icon: FileText, label: 'Common Links', section: 'INTEL' },
  { to: '/serial-patterns', icon: Crosshair, label: 'Serial Patterns', section: 'ANALYZE' },
  { to: '/admin', icon: Shield, label: 'Admin', adminOnly: true, section: 'SYS' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [collapsed, setCollapsed] = useState(false)

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/cases?search=${encodeURIComponent(searchQuery.trim())}`)
    }
  }

  // Group nav items by section
  const sections = navItems.reduce((acc, item) => {
    if (item.adminOnly && user?.role !== 'system_admin') return acc
    if (!acc[item.section]) acc[item.section] = []
    acc[item.section].push(item)
    return acc
  }, {} as Record<string, typeof navItems>)

  return (
    <div className="flex h-screen" style={{ background: 'var(--ops-bg-void)' }}>
      {/* Sidebar */}
      <aside
        className={`flex flex-col border-r transition-all duration-300 ease-in-out`}
        style={{
          width: collapsed ? 64 : 220,
          background: 'linear-gradient(180deg, #0a0d14 0%, #07090e 100%)',
          borderColor: 'var(--ops-border)',
        }}
      >
        {/* Logo / Brand */}
        <div
          className="flex items-center gap-3 px-4 py-4 border-b relative"
          style={{ borderColor: 'var(--ops-border)' }}
        >
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{
              background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(0, 229, 255, 0.05))',
              border: '1px solid rgba(0, 229, 255, 0.25)',
              boxShadow: 'var(--ops-glow-cyan)',
            }}
          >
            <Radio size={16} style={{ color: 'var(--ops-accent)' }} />
          </div>
          {!collapsed && (
            <div className="animate-fade-in overflow-hidden">
              <h1
                className="text-sm font-bold tracking-wide"
                style={{ color: 'var(--ops-accent)', fontFamily: "'JetBrains Mono', monospace" }}
              >
                CRIMENET
              </h1>
              <p className="text-[9px] tracking-widest" style={{ color: 'var(--ops-text-muted)' }}>
                INTEL OPS
              </p>
            </div>
          )}
          {/* Collapse toggle */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center"
            style={{
              background: 'var(--ops-bg-elevated)',
              border: '1px solid var(--ops-border-active)',
              color: 'var(--ops-text-secondary)',
            }}
          >
            {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
          {Object.entries(sections).map(([section, items]) => (
            <div key={section}>
              {!collapsed && (
                <p
                  className="px-3 mb-2 text-[9px] font-bold tracking-[0.15em]"
                  style={{ color: 'var(--ops-text-muted)' }}
                >
                  {section}
                </p>
              )}
              <div className="space-y-0.5">
                {items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    className={
                      `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group relative ${
                        collapsed ? 'justify-center' : ''
                      }`
                    }
                    style={({ isActive }) => ({
                      background: isActive
                        ? 'linear-gradient(90deg, rgba(0, 229, 255, 0.1), rgba(0, 229, 255, 0.03))'
                        : 'transparent',
                      borderLeft: isActive ? '2px solid var(--ops-accent)' : '2px solid transparent',
                      color: isActive ? 'var(--ops-accent)' : 'var(--ops-text-secondary)',
                      boxShadow: isActive ? 'var(--ops-glow-cyan)' : 'none',
                    })}
                    title={collapsed ? item.label : undefined}
                  >
                    <item.icon size={18} className="flex-shrink-0" />
                    {!collapsed && (
                      <span className="text-xs font-medium truncate">{item.label}</span>
                    )}

                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Live indicator */}
        {!collapsed && (
          <div
            className="mx-3 mb-3 px-3 py-2 rounded-lg flex items-center gap-2"
            style={{
              background: 'var(--ops-accent-bg)',
              border: '1px solid rgba(0, 229, 255, 0.1)',
            }}
          >
            <div className="glow-dot" />
            <span className="text-[10px] font-medium" style={{ color: 'var(--ops-text-secondary)' }}>
              SYSTEM ACTIVE
            </span>
          </div>
        )}

        {/* User profile */}
        <div
          className="px-3 py-3 border-t flex items-center gap-3"
          style={{ borderColor: 'var(--ops-border)' }}
        >
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold"
            style={{
              background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(0, 229, 255, 0.05))',
              border: '1px solid rgba(0, 229, 255, 0.2)',
              color: 'var(--ops-accent)',
            }}
          >
            {user?.full_name?.[0] || 'U'}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate" style={{ color: 'var(--ops-text-primary)' }}>
                {user?.full_name}
              </p>
              <p className="text-[10px] truncate" style={{ color: 'var(--ops-text-muted)' }}>
                {user?.role?.replace('_', ' ').toUpperCase()}
              </p>
            </div>
          )}
          <button
            onClick={logout}
            className="flex-shrink-0 p-1.5 rounded-lg transition-colors"
            style={{ color: 'var(--ops-text-muted)' }}
            title="Logout"
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--ops-critical)'
              e.currentTarget.style.background = 'var(--ops-critical-bg)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--ops-text-muted)'
              e.currentTarget.style.background = 'transparent'
            }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header
          className="px-6 py-3 flex items-center gap-4 border-b relative"
          style={{
            background: 'linear-gradient(180deg, rgba(10, 13, 20, 0.98), rgba(7, 9, 14, 0.95))',
            borderColor: 'var(--ops-border)',
          }}
        >
          <form onSubmit={handleSearch} className="flex-1 max-w-md relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: 'var(--ops-text-muted)' }}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search entities, cases, alerts..."
              className="input-ops"
              style={{ paddingLeft: 32 }}
            />
          </form>

          {/* Right-side status indicators */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="glow-dot-success" />
              <span className="text-[10px] font-medium" style={{ color: 'var(--ops-text-muted)' }}>
                ONLINE
              </span>
            </div>
            <div
              className="text-[10px] font-mono"
              style={{ color: 'var(--ops-text-muted)', fontFamily: "'JetBrains Mono', monospace" }}
            >
              {new Date().toLocaleTimeString('en-US', { hour12: false })}
            </div>
          </div>

          {/* Bottom glow line */}
          <div className="absolute bottom-0 left-0 right-0 h-px" style={{
            background: 'linear-gradient(90deg, transparent, rgba(0, 229, 255, 0.15), transparent)'
          }} />
        </header>

        {/* Page content */}
        <main
          className="flex-1 overflow-auto p-6"
          style={{ background: 'var(--ops-bg-void)' }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}


