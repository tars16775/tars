import { useRef, useEffect } from 'react'
import { useTars } from '../context/ConnectionContext'
import { MessageSquare } from 'lucide-react'
import clsx from 'clsx'

export default function MessagePanel() {
  const { messages } = useTars()
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [messages])

  // Group messages by time proximity (60s window)
  const groupedMessages = messages.reduce<Array<{ messages: typeof messages; showTime: boolean }>>((acc, msg, i) => {
    const prev = i > 0 ? messages[i - 1] : null
    const sameGroup = prev && prev.sender === msg.sender && (msg.timestamp - prev.timestamp) < 60000
    if (sameGroup) {
      acc[acc.length - 1].messages.push(msg)
    } else {
      acc.push({ messages: [msg], showTime: true })
    }
    return acc
  }, [])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-panel-border bg-panel-surface/50 shrink-0">
        <div className="flex items-center gap-2">
          <MessageSquare size={13} className="text-signal-blue" />
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">iMessage</span>
        </div>
        <span className="text-[10px] text-slate-600">{messages.length}</span>
      </div>

      {/* Messages — conversation only */}
      <div ref={containerRef} className="flex-1 overflow-y-auto p-3 space-y-1">
        {groupedMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-600">
            <MessageSquare size={28} className="mb-2 opacity-30" />
            <p className="text-[10px]">No conversations yet</p>
            <p className="text-[9px] text-slate-700 mt-1">iMessage conversations will appear here</p>
          </div>
        ) : (
          groupedMessages.map((group, gi) => (
            <div key={gi} className="space-y-0.5">
              {group.showTime && group.messages[0] && (
                <div className={clsx(
                  'text-[9px] text-slate-700 mt-2 mb-1 px-1',
                  group.messages[0].sender === 'user' ? 'text-right' : 'text-left'
                )}>
                  {group.messages[0].time}
                </div>
              )}
              {group.messages.map((msg) => (
                <div
                  key={msg.id}
                  className={clsx(
                    'flex animate-fade-in',
                    msg.sender === 'user' ? 'justify-end' : 'justify-start'
                  )}
                >
                  <div className={clsx(
                    'max-w-[85%] px-3 py-2 text-[13px] leading-relaxed break-words',
                    msg.sender === 'user'
                      ? 'bg-signal-blue rounded-2xl rounded-br-sm text-white shadow-glow-blue'
                      : 'bg-void-700 rounded-2xl rounded-bl-sm text-slate-200 border border-panel-border'
                  )}>
                    {msg.text}
                  </div>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
