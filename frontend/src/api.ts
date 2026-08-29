const API_BASE = '/api/v1'

async function request(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (response.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(error.detail || 'Request failed')
  }

  // Handle file downloads
  const contentType = response.headers.get('content-type')
  if (contentType && (contentType.includes('text/plain') || contentType.includes('application/pdf'))) {
    return response
  }

  return response.json()
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  getMe: () => request('/auth/me'),

  // Cases
  getCases: (status?: string) => {
    const qs = status ? `?status=${status}` : ''
    return request(`/cases${qs}`)
  },
  getArchivedCases: () => request('/cases/archived'),
  getCase: (id: string) => request(`/cases/${id}`),
  createCase: (data: any) => request('/cases', { method: 'POST', body: JSON.stringify(data) }),
  updateCase: (id: string, data: any) =>
    request(`/cases/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  closeCase: (id: string) => request(`/cases/${id}/close`, { method: 'POST' }),
  reopenCase: (id: string) => request(`/cases/${id}/reopen`, { method: 'POST' }),
  assignUser: (caseId: string, userId: string) =>
    request(`/cases/${caseId}/assign`, { method: 'POST', body: JSON.stringify({ user_id: userId }) }),
  unassignUser: (caseId: string, userId: string) =>
    request(`/cases/${caseId}/unassign`, { method: 'POST', body: JSON.stringify({ user_id: userId }) }),

  // Entities
  getEntities: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request(`/entities${qs}`)
  },
  getEntity: (id: string) => request(`/entities/${id}`),
  createEntity: (data: any) => request('/entities', { method: 'POST', body: JSON.stringify(data) }),
  updateEntity: (id: string, data: any) => request(`/entities/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  mergeEntities: (primaryId: string, secondaryId: string) =>
    request('/entities/merge', { method: 'POST', body: JSON.stringify({ primary_entity_id: primaryId, secondary_entity_id: secondaryId }) }),
  findMatches: (entityId: string, threshold = 0.6) =>
    request(`/entities/${entityId}/matches?threshold=${threshold}`),

  // People Graph
  getPeopleGraph: (caseId: string, params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request(`/graph/people/${caseId}${qs}`)
  },
  getMultiPeopleGraph: (caseIds: string[], params?: Record<string, string>) =>
    request('/graph/people/multi', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds, ...params }),
    }),

  // Location Graph
  getLocationGraph: (caseId: string, params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request(`/graph/location/${caseId}${qs}`)
  },
  getMultiLocationGraph: (caseIds: string[]) =>
    request('/graph/location/multi', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds }),
    }),

  // Graph (legacy combined)
  getGraph: (caseId: string, params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request(`/graph/${caseId}${qs}`)
  },
  getMultiCaseGraph: (caseIds: string[], params?: Record<string, string>) =>
    request('/graph/multi', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds, ...params }),
    }),
  getCentrality: (caseId: string) => request(`/graph/${caseId}/centrality`),
  getMultiCentrality: (caseIds: string[]) =>
    request('/graph/multi/centrality', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds }),
    }),
  getCommunities: (caseId: string) => request(`/graph/${caseId}/communities`),
  findPath: (source: string, target: string) =>
    request(`/graph/path?source=${source}&target=${target}`),
  getGraphStats: (caseId: string) => request(`/graph/stats/${caseId}`),

  // Ingestion
  uploadFile: async (caseId: string, file: File, sourceType: string) => {
    const formData = new FormData()
    formData.append('case_id', caseId)
    formData.append('source_type', sourceType)
    formData.append('file', file)
    return request('/ingestion/upload', { method: 'POST', body: formData })
  },
  uploadText: (caseId: string, title: string, content: string, sourceType: string) => {
    const formData = new FormData()
    formData.append('case_id', caseId)
    formData.append('title', title)
    formData.append('content', content)
    formData.append('source_type', sourceType)
    return request('/ingestion/upload-text', { method: 'POST', body: formData })
  },
  autoRegisterCase: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request('/ingestion/auto-register', { method: 'POST', body: formData })
  },
  confirmAutoRegister: async (data: {
    case_number: string; name: string; description?: string;
    jurisdiction?: string; date_filed?: string; police_station?: string;
    accused_persons_json?: string; file: File
  }) => {
    const formData = new FormData()
    formData.append('case_number', data.case_number)
    formData.append('name', data.name)
    formData.append('description', data.description || '')
    formData.append('jurisdiction', data.jurisdiction || '')
    formData.append('date_filed', data.date_filed || '')
    formData.append('police_station', data.police_station || '')
    formData.append('accused_persons_json', data.accused_persons_json || '[]')
    formData.append('file', data.file)
    return request('/ingestion/auto-register/confirm', { method: 'POST', body: formData })
  },

  // Alerts
  getAlerts: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request(`/alerts${qs}`)
  },
  getAlertStats: () => request('/alerts/stats'),
  updateAlertStatus: (id: string, status: string, notes?: string) =>
    request(`/alerts/${id}/status`, { method: 'PUT', body: JSON.stringify({ status, notes }) }),
  runDetection: () => request('/alerts/run-detection', { method: 'POST' }),
  getDetectionRules: () => request('/alerts/rules'),
  updateDetectionRule: (id: string, data: any) =>
    request(`/alerts/rules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  // Admin
  getUsers: () => request('/admin/users'),
  createUser: (data: any) => request('/admin/users', { method: 'POST', body: JSON.stringify(data) }),
  updateUser: (id: string, data: any) => request(`/admin/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  getAuditLog: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request(`/admin/audit-log${qs}`)
  },

  // Reports
  exportReport: async (caseId: string, reportType: string, _entityId?: string) => {
    const response = await request(`/reports/export?case_id=${caseId}&report_type=${reportType}`)
    return response
  },
  findCommonLinks: (caseIds: string[]) =>
    request('/reports/common-links', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds }),
    }),
  exportCommonLinksPdf: async (caseIds: string[]) => {
    const response = await fetch(`${API_BASE}/reports/common-links/pdf`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({ case_ids: caseIds }),
    })
    return response
  },
  generateCaseSummary: (caseIds: string[]) =>
    request('/reports/case-summary', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds }),
    }),

  // Threat Scores
  getThreatScores: (caseIds?: string[]) =>
    request('/reports/threat-scores', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds || null }),
    }),
  getPersonThreatScore: (entityId: string) =>
    request(`/reports/threat-scores/${entityId}`),

  // Investigative Briefs
  getInvestigativeBrief: (entityId: string) =>
    request(`/reports/brief/${entityId}`),

  // Graph Connectivity & Validation
  getGraphConnectivity: () => request('/reports/graph-connectivity'),
  validateConsistency: () => request('/reports/validate-consistency'),

  // Resolution Audit
  getResolutionAudit: (entityId?: string, limit = 50) => {
    const params = new URLSearchParams()
    if (entityId) params.set('entity_id', entityId)
    params.set('limit', String(limit))
    return request(`/reports/audit-log?${params}`)
  },

  // Case Linkage & Pattern Recognition
  getCaseLinkageCases: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request(`/case-linkage/cases${qs}`)
  },
  getCaseLinkageCase: (caseId: string) => request(`/case-linkage/cases/${caseId}`),
  getCaseLinkageClusters: (minConfidence?: number) => {
    const qs = minConfidence != null ? `?min_confidence=${minConfidence}` : ''
    return request(`/case-linkage/clusters${qs}`)
  },
  getCaseLinkageClusterDetail: (clusterId: number) =>
    request(`/case-linkage/clusters/${clusterId}`),
  getCaseLinkageCaseLinks: (caseId: string, minScore = 50) =>
    request(`/case-linkage/case/${caseId}/links?min_score=${minScore}`),
  getCaseLinkageStats: () => request('/case-linkage/stats'),

  // Serial Pattern Detection
  analyzeSerialPatterns: (caseIds?: string[], useLlm = false) =>
    request('/reports/serial-patterns', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds || null, use_llm: useLlm }),
    }),
  analyzeSerialPatternsLLM: (caseIds?: string[]) =>
    request('/reports/serial-patterns/llm', {
      method: 'POST',
      body: JSON.stringify({ case_ids: caseIds || null }),
    }),
  getCasePatternContext: (caseId: string) =>
    request(`/reports/serial-patterns/${caseId}`),
}
