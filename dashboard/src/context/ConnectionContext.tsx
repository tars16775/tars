import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'
import { WebSocketManager } from '../lib/ws'
import { sendBrowserNotification } from '../lib/notifications'
import type {
  TarsEvent, ConnectionState, SubsystemStatus, TarsStats,
  TaskItem, ThinkingBlock, ChatMessage, ActionLogEntry,
} from '../lib/types'

interface TarsContextValue {
  // Connection
  connectionState: ConnectionState
  subsystems: SubsystemStatus
  // Data
  tasks: TaskItem[]
  thinkingBlocks: ThinkingBlock[]
  messages: ChatMessage[]
  actionLog: ActionLogEntry[]
  stats: TarsStats
  currentModel: string
  // Memory
  memoryContext: string
  memoryPreferences: string
  // Actions
  sendTask: (task: string) => void
  sendMessage: (msg: string) => void
  killAgent: () => void
  updateConfig: (key: string, value: any) => void
  saveMemory: (field: string, content: string) => void
  requestMemory: () => void
  requestStats: () => void
  setWsUrl: (url: string) => void
  setAuthToken: (token: string) => void
}

const defaultStats: TarsStats = {
  total_events: 0, total_tokens_in: 0, total_tokens_out: 0,
  total_cost: 0, actions_success: 0, actions_failed: 0,
  start_time: Date.now() / 1000, uptime_seconds: 0,
  tool_usage: {}, model_usage: {},
}

const TarsContext = createContext<TarsContextValue | null>(null)

export function useTars() {
  const ctx = useContext(TarsContext)
  if (!ctx) throw new Error('useTars must be used within TarsProvider')
  return ctx
}

function getDefaultWsUrl(): string {
  // In production (cloud), use the relay URL
  // In dev, connect to local TARS
  const host = window.location.hostname
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  if (host === 'localhost' || host === '127.0.0.1') {
    return `ws://${host}:8421`
  }
  // Cloud: WebSocket on same host
  return `${protocol}//${window.location.host}/ws`
}

export function TarsProvider({ children }: { children: React.ReactNode }) {
  const wsRef = useRef<WebSocketManager | null>(null)
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')
  const [subsystems, setSubsystems] = useState<SubsystemStatus>({
    websocket: 'disconnected', agent: 'offline', mac: 'unreachable', claude: 'idle',
  })
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [thinkingBlocks, setThinkingBlocks] = useState<ThinkingBlock[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [actionLog, setActionLog] = useState<ActionLogEntry[]>([])
  const [stats, setStats] = useState<TarsStats>(defaultStats)
  const [currentModel, setCurrentModel] = useState('--')
  const [memoryContext, setMemoryContext] = useState('')
  const [memoryPreferences, setMemoryPreferences] = useState('')

  const taskIdRef = useRef(0)
  const msgIdRef = useRef(0)
  const actionIdRef = useRef(0)
  const blockIdRef = useRef(0)
  const currentThinkRef = useRef<string | null>(null)

  const handleEvent = useCallback((event: TarsEvent) => {
    const { type, data, timestamp } = event
    const time = new Date(timestamp).toLocaleTimeString()

    switch (type) {
      case 'task_received': {
        taskIdRef.current++
        const task: TaskItem = {
          id: taskIdRef.current,
          text: data.task,
          time,
          source: data.source || 'imessage',
          status: 'active',
          startedAt: Date.now(),
        }
        setTasks(prev => {
          const updated = prev.map(t => t.status === 'active' ? { ...t, status: 'completed' as const, completedAt: Date.now() } : t)
          return [task, ...updated]
        })
        setSubsystems(s => ({ ...s, agent: 'working' }))
        sendBrowserNotification('TARS // New Task', data.task)
        break
      }
      case 'task_completed':
        setTasks(prev => prev.map(t => t.status === 'active' ? { ...t, status: 'completed', completedAt: Date.now() } : t))
        setSubsystems(s => ({ ...s, agent: 'online' }))
        sendBrowserNotification('TARS // Task Complete', data.response?.substring(0, 100) || 'Done')
        break

      case 'thinking_start': {
        blockIdRef.current++
        const id = `think-${blockIdRef.current}`
        currentThinkRef.current = id
        setThinkingBlocks(prev => [...prev, {
          id, type: 'thinking', model: data.model || '', text: '',
        }])
        setCurrentModel(data.model || '')
        setSubsystems(s => ({ ...s, claude: 'active' }))
        break
      }
      case 'thinking':
        setThinkingBlocks(prev => {
          const idx = prev.findIndex(b => b.id === currentThinkRef.current)
          if (idx < 0) return prev
          const updated = [...prev]
          updated[idx] = { ...updated[idx], text: (updated[idx].text || '') + data.text }
          return updated
        })
        break

      case 'tool_called': {
        blockIdRef.current++
        currentThinkRef.current = null
        setThinkingBlocks(prev => [...prev, {
          id: `tool-${blockIdRef.current}`,
          type: 'tool_call',
          toolName: data.tool_name,
          toolInput: data.tool_input,
          time,
        }])
        break
      }
      case 'tool_result': {
        blockIdRef.current++
        setThinkingBlocks(prev => [...prev, {
          id: `result-${blockIdRef.current}`,
          type: 'tool_result',
          toolName: data.tool_name,
          content: data.content,
          success: data.success,
          duration: data.duration,
          time,
        }])
        actionIdRef.current++
        setActionLog(prev => [...prev, {
          id: actionIdRef.current,
          toolName: data.tool_name || '--',
          detail: String(data.content || '').substring(0, 200),
          success: data.success,
          duration: data.duration || null,
          time,
        }])
        setSubsystems(s => ({ ...s, claude: 'idle' }))
        break
      }

      case 'imessage_sent':
        msgIdRef.current++
        setMessages(prev => [...prev, {
          id: msgIdRef.current, text: data.message, sender: 'tars', time, timestamp: Date.now(),
        }])
        break
      case 'imessage_received':
        msgIdRef.current++
        setMessages(prev => [...prev, {
          id: msgIdRef.current, text: data.message, sender: 'user', time, timestamp: Date.now(),
        }])
        sendBrowserNotification('TARS // iMessage', data.message)
        break

      case 'api_call':
        setCurrentModel(data.model || '')
        setStats(prev => ({
          ...prev,
          total_tokens_in: prev.total_tokens_in + (data.tokens_in || 0),
          total_tokens_out: prev.total_tokens_out + (data.tokens_out || 0),
        }))
        break

      case 'status_change':
        setSubsystems(s => ({ ...s, agent: data.status || 'online' }))
        break

      case 'error':
        blockIdRef.current++
        setThinkingBlocks(prev => [...prev, {
          id: `err-${blockIdRef.current}`, type: 'error', text: data.message || data.error || 'Unknown error',
        }])
        break

      case 'stats':
        setStats(data as TarsStats)
        break

      case 'memory_data':
        setMemoryContext(data.context || '')
        setMemoryPreferences(data.preferences || '')
        break

      case 'kill_switch':
        setSubsystems(s => ({ ...s, agent: 'killed' }))
        sendBrowserNotification('TARS // KILLED', 'Kill switch activated')
        break
    }
  }, [])

  // Initialize WebSocket
  useEffect(() => {
    const ws = new WebSocketManager(getDefaultWsUrl())
    wsRef.current = ws

    ws.onStateChange((state) => {
      setConnectionState(state)
      setSubsystems(s => ({
        ...s,
        websocket: state === 'connected' ? 'connected' : state === 'reconnecting' ? 'reconnecting' : 'disconnected',
        mac: state === 'connected' ? 'reachable' : 'unreachable',
      }))
    })

    ws.onEvent(handleEvent)
    ws.connect()

    return () => ws.disconnect()
  }, [handleEvent])

  // Periodic stats refresh
  useEffect(() => {
    const interval = setInterval(() => {
      if (connectionState === 'connected') {
        wsRef.current?.send({ type: 'get_stats' })
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [connectionState])

  const sendTask = useCallback((task: string) => {
    wsRef.current?.send({ type: 'send_task', task })
  }, [])

  const sendMessage = useCallback((msg: string) => {
    wsRef.current?.send({ type: 'send_task', task: msg })
    msgIdRef.current++
    setMessages(prev => [...prev, {
      id: msgIdRef.current, text: msg, sender: 'user', time: new Date().toLocaleTimeString(), timestamp: Date.now(),
    }])
  }, [])

  const killAgent = useCallback(() => {
    wsRef.current?.send({ type: 'kill' })
    setSubsystems(s => ({ ...s, agent: 'killed' }))
  }, [])

  const updateConfig = useCallback((key: string, value: any) => {
    wsRef.current?.send({ type: 'update_config', key, value })
  }, [])

  const saveMemory = useCallback((field: string, content: string) => {
    wsRef.current?.send({ type: 'save_memory', field, content })
  }, [])

  const requestMemoryFn = useCallback(() => {
    wsRef.current?.send({ type: 'get_memory' })
  }, [])

  const requestStatsFn = useCallback(() => {
    wsRef.current?.send({ type: 'get_stats' })
  }, [])

  const setWsUrl = useCallback((url: string) => {
    wsRef.current?.updateUrl(url)
  }, [])

  const setAuthToken = useCallback((token: string) => {
    wsRef.current?.updateToken(token)
  }, [])

  return (
    <TarsContext.Provider value={{
      connectionState, subsystems,
      tasks, thinkingBlocks, messages, actionLog, stats, currentModel,
      memoryContext, memoryPreferences,
      sendTask, sendMessage, killAgent, updateConfig, saveMemory,
      requestMemory: requestMemoryFn, requestStats: requestStatsFn,
      setWsUrl, setAuthToken,
    }}>
      {children}
    </TarsContext.Provider>
  )
}
