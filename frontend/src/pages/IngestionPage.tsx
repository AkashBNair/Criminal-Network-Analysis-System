import { useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { ArrowLeft, Upload, FileText, CheckCircle, AlertCircle, X } from 'lucide-react'

export default function IngestionPage() {
  const { caseId } = useParams()
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [sourceType, setSourceType] = useState('general')
  const [uploading, setUploading] = useState(false)
  const [results, setResults] = useState<any[]>([])
  const [textInput, setTextInput] = useState({ title: '', content: '' })
  const [showTextInput, setShowTextInput] = useState(false)
  const [dragOver, setDragOver] = useState(false)

  const handleFileUpload = async (files: FileList | null) => { if (!files || !caseId) return; setUploading(true); for (const file of Array.from(files)) { try { const result = await api.uploadFile(caseId, file, sourceType); setResults(prev => [...prev, { filename: file.name, ...result, success: true }]) } catch (err: any) { setResults(prev => [...prev, { filename: file.name, error: err.message, success: false }]) } } setUploading(false) }

  const handleDrop = (e: React.DragEvent) => { e.preventDefault(); setDragOver(false); handleFileUpload(e.dataTransfer.files) }

  const handleTextUpload = async (e: React.FormEvent) => { e.preventDefault(); if (!caseId || !textInput.content.trim()) return; setUploading(true); try { const result = await api.uploadText(caseId, textInput.title, textInput.content, sourceType); setResults(prev => [...prev, { filename: textInput.title || 'Text', ...result, success: true }]); setTextInput({ title: '', content: '' }); setShowTextInput(false) } catch (err: any) { setResults(prev => [...prev, { filename: 'Text', error: err.message, success: false }]) } setUploading(false) }

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <button onClick={() => navigate(`/cases/${caseId}`)} className="btn-ops mb-4"><ArrowLeft size={14} /> Back</button>
      <h1 className="text-lg font-bold tracking-wide mb-5" style={{ color: 'var(--ops-text-primary)' }}>DATA INGESTION</h1>

      <div className="ops-panel p-5 mb-5">
        <h2 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>SOURCE TYPE</h2>
        <div className="flex flex-wrap gap-2">{[
          { value: 'general', label: 'General' }, { value: 'fir', label: 'FIR' }, { value: 'cdr', label: 'CDR' }, { value: 'financial', label: 'Financial' }, { value: 'report', label: 'Intel Report' },
        ].map(type => (
          <button key={type.value} onClick={() => setSourceType(type.value)} className="btn-ops px-4 py-2 rounded-lg text-[11px] font-semibold" style={sourceType === type.value ? { background: 'var(--ops-accent-bg)', borderColor: 'rgba(0, 229, 255, 0.2)', color: 'var(--ops-accent)' } : {}}>
            {type.label}
          </button>
        ))}</div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
        <div className={`rounded-xl p-8 text-center cursor-pointer transition-all duration-200`} style={{ background: dragOver ? 'var(--ops-accent-bg)' : 'var(--ops-bg-panel)', border: `2px dashed ${dragOver ? 'var(--ops-accent)' : 'var(--ops-border)'}` }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }} onDragLeave={() => setDragOver(false)} onDrop={handleDrop} onClick={() => fileInputRef.current?.click()}>
          <Upload size={36} style={{ color: dragOver ? 'var(--ops-accent)' : 'var(--ops-text-muted)', opacity: 0.4, margin: '0 auto 12px' }} />
          <p className="text-[11px] font-semibold" style={{ color: 'var(--ops-text-primary)' }}>DRAG & DROP FILES</p>
          <p className="text-[10px] mt-1" style={{ color: 'var(--ops-text-muted)' }}>or click to browse</p>
          <input ref={fileInputRef} type="file" multiple accept=".csv,.txt,.pdf,.docx,.json" onChange={(e) => handleFileUpload(e.target.files)} className="hidden" />
        </div>

        <div className="ops-panel p-5">
          <h3 className="text-[11px] font-semibold mb-2" style={{ color: 'var(--ops-text-primary)' }}>OR PASTE TEXT</h3>
          <p className="text-[10px] mb-3" style={{ color: 'var(--ops-text-muted)' }}>Paste FIR text, report content, or any document for extraction.</p>
          <button onClick={() => setShowTextInput(true)} className="btn-ops w-full py-3 rounded-lg text-[11px] font-semibold text-center"><FileText size={14} className="inline mr-2" />OPEN EDITOR</button>
        </div>
      </div>

      {showTextInput && (
        <div className="modal-overlay"><div className="modal-panel" style={{ maxWidth: 640 }}>
          <div className="flex items-center justify-between mb-4"><h3 className="text-sm font-bold tracking-wider" style={{ color: 'var(--ops-text-primary)' }}>PASTE DOCUMENT</h3><button onClick={() => setShowTextInput(false)}><X size={16} style={{ color: 'var(--ops-text-muted)' }} /></button></div>
          <form onSubmit={handleTextUpload} className="space-y-4">
            <div><label className="block text-[9px] font-bold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>TITLE</label><input type="text" value={textInput.title} onChange={(e) => setTextInput({ ...textInput, title: e.target.value })} className="input-ops" style={{ paddingLeft: 12 }} placeholder="e.g. FIR-2026-045" /></div>
            <div><label className="block text-[9px] font-bold tracking-wider mb-1.5" style={{ color: 'var(--ops-text-muted)' }}>CONTENT *</label><textarea value={textInput.content} onChange={(e) => setTextInput({ ...textInput, content: e.target.value })} className="input-ops" style={{ paddingLeft: 12, fontFamily: "'JetBrains Mono', monospace" }} rows={10} placeholder="Paste document text here..." required /></div>
            <div className="flex gap-3"><button type="button" onClick={() => setShowTextInput(false)} className="btn-ops flex-1 py-2.5 rounded-lg text-[11px] font-semibold text-center">CANCEL</button><button type="submit" disabled={uploading || !textInput.content.trim()} className="btn-ops-primary flex-1 py-2.5 rounded-lg text-[11px] font-semibold text-center disabled:opacity-40">{uploading ? 'PROCESSING...' : 'EXTRACT'}</button></div>
          </form>
        </div></div>
      )}

      {uploading && (
        <div className="rounded-xl p-3 mb-5 flex items-center gap-3" style={{ background: 'var(--ops-accent-bg)', border: '1px solid rgba(0, 229, 255, 0.15)' }}>
          <div className="loading-spinner" style={{ width: 16, height: 16, borderWidth: 1.5 }} />
          <span className="text-[11px]" style={{ color: 'var(--ops-accent)' }}>Processing documents...</span>
        </div>
      )}

      {results.length > 0 && (
        <div className="ops-panel p-5">
          <h2 className="text-[10px] font-bold tracking-wider mb-3" style={{ color: 'var(--ops-text-secondary)' }}>RESULTS</h2>
          <div className="space-y-2">{results.map((result, i) => (
            <div key={i} className="flex items-center gap-3 p-3 rounded-lg" style={{ background: result.success ? 'var(--ops-success-bg)' : 'var(--ops-critical-bg)' }}>
              {result.success ? <CheckCircle size={16} style={{ color: 'var(--ops-success)' }} /> : <AlertCircle size={16} style={{ color: 'var(--ops-critical)' }} />}
              <div className="flex-1">
                <p className="text-[11px] font-medium" style={{ color: 'var(--ops-text-primary)' }}>{result.filename}</p>
                <p className="text-[9px]" style={{ color: result.success ? 'var(--ops-text-secondary)' : 'var(--ops-critical)' }}>
                  {result.success ? `Extracted ${result.entities_extracted} entities, ${result.relationship_created || 0} rels` : result.error}
                </p>
              </div>
              {result.success && <button onClick={() => navigate(`/cases/${caseId}/entities`)} className="text-[10px] font-semibold" style={{ color: 'var(--ops-accent-dim)' }}>VIEW →</button>}
            </div>
          ))}</div>
        </div>
      )}
    </div>
  )
}
