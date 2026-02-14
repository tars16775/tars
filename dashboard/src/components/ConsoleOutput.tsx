import { useRef, useEffect, useState, useCallback } from 'react'
import { useTars } from '../context/ConnectionContext'
import { Terminal as TermIcon, ChevronDown, Trash2, Download } from 'lucide-react'
import clsx from 'clsx'

export default function ConsoleOutput() {
  const { outputLog, clearOutput, tarsProcess } = useTars()
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState<'all' | 'stdout' | 'stderr' | 'system'>('all')

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [outputLog, autoScroll])

  // Detect manual scroll
  const handleScroll = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
    setAutoScroll(atBottom)
  }, [])

  const jumpToBottom = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
      setAutoScroll(true)
    }
  }, [])

  const handleDownload = useCallback(() => {
    const text = outputLog.map(l => `[${l.stream}] ${l.text}`).join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `tars-output-${new Date().toISOString().slice(0, 19)}.log`
    a.click()
    URL.revokeObjectURL(url)
  }, [outputLog])

  const filteredLog = filter === 'all' ? outputLog : outputLog.filter(l => l.stream === filter)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-panel-border bg-panel-surface/50 shrink-0">
        <div className="flex items-center gap-2">
          <TermIcon size={13} className="text-signal-green" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Console</span>
          {tarsProcess.running && (
            <div className="w-1.5 h-1.5 rounded-full bg-signal-green animate-pulse" />
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Filter buttons */}
          <div className="flex items-center gap-px bg-void-800 rounded overflow-hidden">
            {(['all', 'stdout', 'stderr', 'system'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={clsx(
                  'px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider transition-colors',
                  filter === f
                    ? 'bg-panel-border text-star-white'
                    : 'text-slate-600 hover:text-slate-400'
                )}
              >
                {f}
              </button>
            ))}
          </div>
          <button onClick={handleDownload} className="text-slate-600 hover:text-slate-300" title="Download log">
            <Download size={11} />
          </button>
          <button onClick={clearOutput} className="text-slate-600 hover:text-slate-300" title="Clear">
            <Trash2 size={11} />
          </button>
          <span className="text-[10px] text-slate-600">{filteredLog.length}</span>
        </div>
      </div>

      {/* Output */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto overflow-x-hidden font-mono text-[11px] leading-[18px] bg-void-950 p-2"
      >
        {filteredLog.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-700">
            <TermIcon size={28} className="mb-2 opacity-30" />
            <p className="text-[10px]">
              {tarsProcess.running ? 'Waiting for output...' : 'Start TARS to see output'}
            </p>
          </div>
        ) : (
          filteredLog.map((line, i) => (
            <div
              key={i}
              className={clsx(
                'whitespace-pre-wrap break-all px-1 hover:bg-white/[0.02]',
                line.stream === 'stderr' && 'text-signal-red/80',
                line.stream === 'system' && 'text-signal-cyan/70 italic',
                line.stream === 'stdout' && 'text-slate-300',
              )}
            >
              {line.text}
            </div>
          ))
        )}
      </div>

      {/* Jump to bottom */}
      {!autoScroll && (
        <button
          onClick={jumpToBottom}
          className="absolute bottom-2 right-4 z-10 flex items-center gap-1 px-2.5 py-1 rounded-full glass text-[10px] font-semibold text-signal-green border border-signal-green/30 hover:bg-signal-green/10 transition-colors"
        >
          <ChevronDown size={10} />
          Latest
        </button>
      )}
    </div>
  )
}
