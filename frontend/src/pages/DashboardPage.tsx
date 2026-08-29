import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext'

import {
  FolderOpen, ArrowRight,
  Users, Network, Bell
} from 'lucide-react'

export default function DashboardPage() {
  const { user } = useAuth()
  
  

  const [cases, setCases] = useState<any[]>([])
  const [alertStats, setAlertStats] = useState<any>(null)
  
  const [loading, setLoading] = useState(true)
  

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    try {
      const [casesData, alertData] = await Promise.all([
        api.getCases(),
        api.getAlertStats(),
      ])
      setCases(casesData)
      setAlertStats(alertData)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }



  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
      </div>
    )
  }

  const totalEntities = cases.reduce((sum, c) => sum + (c.entity_count || 0), 0)
  const totalRelationships = cases.reduce((sum, c) => sum + (c.relationship_count || 0), 0)
  const totalAlerts = alertStats?.total || 0

  const metrics = [
    { label: 'ACTIVE CASES', value: cases.length, icon: FolderOpen, color: 'var(--ops-accent)' },
    { label: 'ENTITIES', value: totalEntities, icon: Users, color: '#0891b2' },
    { label: 'LINKS', value: totalRelationships, icon: Network, color: '#8b5cf6' },
    { label: 'ALERTS', value: totalAlerts, icon: Bell, color: 'var(--ops-high)' },
  ]

  return (
    <div className="max-w-[1400px] mx-auto space-y-4 animate-fade-in">
      {/* Welcome header */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-lg font-bold tracking-wide" style={{ color: 'var(--ops-text-primary)' }}>
            INTELLIGENCE OVERVIEW
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--ops-text-muted)' }}>
            Welcome back, {user?.full_name} • Last session refresh: {new Date().toLocaleTimeString('en-US', { hour12: false })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="glow-dot" />
          <span className="text-[10px] font-mono tracking-wider" style={{ color: 'var(--ops-text-secondary)', fontFamily: "'JetBrains Mono', monospace" }}>
            LIVE
          </span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-4 gap-3">
        {metrics.map((m) => (
          <div key={m.label} className="metric-card group">
            <div className="flex items-center gap-2 mb-2">
              <m.icon size={14} style={{ color: m.color }} />
              <span className="text-[9px] font-bold tracking-[0.12em]" style={{ color: 'var(--ops-text-muted)' }}>
                {m.label}
              </span>
            </div>
            <div className="flex items-end justify-between">
              <span
                className="text-2xl font-bold"
                style={{ color: m.color, fontFamily: "'JetBrains Mono', monospace" }}
              >
                {m.value}
              </span>
              <div className="glow-dot" style={{ background: m.color, boxShadow: `0 0 8px ${m.color}40` }} />
            </div>
          </div>
        ))}
      </div>

    </div>
  )
}