import { createContext, useContext, useState, useCallback } from 'react'

interface CrossGraphState {
  highlightedSuspect: { id: string; name: string } | null
  timelineDateRange: [string, string] | null  // [startISO, endISO]
  timelinePlaying: boolean
  highlightSuspect: (id: string, name: string) => void
  clearHighlight: () => void
  setTimelineRange: (range: [string, string] | null) => void
  setTimelinePlaying: (playing: boolean) => void
}

const CrossGraphContext = createContext<CrossGraphState>({
  highlightedSuspect: null,
  timelineDateRange: null,
  timelinePlaying: false,
  highlightSuspect: () => {},
  clearHighlight: () => {},
  setTimelineRange: () => {},
  setTimelinePlaying: () => {},
})

export function CrossGraphProvider({ children }: { children: React.ReactNode }) {
  const [highlightedSuspect, setHighlightedSuspect] = useState<{ id: string; name: string } | null>(null)
  const [timelineDateRange, setTimelineDateRange] = useState<[string, string] | null>(null)
  const [timelinePlaying, setTimelinePlaying] = useState(false)

  const highlightSuspect = useCallback((id: string, name: string) => {
    setHighlightedSuspect({ id, name })
  }, [])

  const clearHighlight = useCallback(() => {
    setHighlightedSuspect(null)
    setTimelineDateRange(null)
    setTimelinePlaying(false)
  }, [])

  const setTimelineRange = useCallback((range: [string, string] | null) => {
    setTimelineDateRange(range)
  }, [])

  return (
    <CrossGraphContext.Provider value={{
      highlightedSuspect, timelineDateRange, timelinePlaying,
      highlightSuspect, clearHighlight, setTimelineRange, setTimelinePlaying,
    }}>
      {children}
    </CrossGraphContext.Provider>
  )
}

export const useCrossGraph = () => useContext(CrossGraphContext)
