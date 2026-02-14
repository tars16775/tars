import { useState, useRef, useEffect, useCallback } from 'react'
import { useTars } from '../context/ConnectionContext'
import { MessageSquare, Send, Radio } from 'lucide-react'
import clsx from 'clsx'

export default function MessagePanel() {
  const { messages, sendMessage, connectionState } = useTars()
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || connectionState !== 'connected') return
    sendMessage(text)
    setInput('')
    setSending(true)
    setTimeout(() => setSending(false), 800)
  }, [input, sendMessage, connectionState])

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

      {/* Messages */}
      <div ref={containerRef} className="flex-1 overflow-y-auto p-3 space-y-1">
        {groupedMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-600">
            <MessageSquare size={28} className="mb-2 opacity-30" />
            <p className="text-[10px]">No messages yet</p>
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

      {/* Input */}
      <div className="px-2 py-2 border-t border-panel-border shrink-0">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Message TARS..."
            className="flex-1 bg-void-800 border border-panel-border rounded-full px-3 py-1.5 text-xs text-star-white placeholder-slate-600 outline-none focus:border-signal-blue/50 transition-colors"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || connectionState !== 'connected'}
            className={clsx(
              'w-7 h-7 rounded-full flex items-center justify-center transition-all shrink-0',
              sending
                ? 'bg-signal-green text-void-950 shadow-glow-green'
                : 'bg-signal-blue text-white hover:shadow-glow-blue disabled:bg-slate-800 disabled:text-slate-600'
            )}
          >
            {sending ? <Radio size={12} className="animate-pulse" /> : <Send size={11} />}
          </button>
        </div>
      </div>
    </div>
  )
}
