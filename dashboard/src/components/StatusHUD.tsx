import { useTars } from '../context/ConnectionContext'
import { Wifi, WifiOff, Monitor, Brain, Bot, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'

interface StatusItemProps {
  label: string
  status: string
  icon: React.ReactNode
}

function StatusItem({ label, status, icon }: StatusItemProps) {
  const color = status === 'connected' || status === 'online' || status === 'reachable' || status === 'active'
    ? 'text-signal-green'
    : status === 'working' || status === 'reconnecting' || status === 'idle'
    ? 'text-signal-amber'
    : status === 'killed'
    ? 'text-signal-red'
    : 'text-signal-red'

  const dotColor = status === 'connected' || status === 'online' || status === 'reachable' || status === 'active'
    ? 'bg-signal-green'
    : status === 'working' || status === 'reconnecting' || status === 'idle'
    ? 'bg-signal-amber'
    : 'bg-signal-red'

  const shouldPulse = status === 'working' || status === 'reconnecting' || status === 'active'

  return (
    <div className="flex items-center gap-2 px-2 py-1" title={`${label}: ${status}`}>
      <span className={clsx('w-4 h-4', color)}>{icon}</span>
      <span className="text-[10px] uppercase tracking-wider text-slate-500 hidden lg:inline">{label}</span>
      <div className="flex items-center gap-1.5">
        <div className={clsx(
          'w-1.5 h-1.5 rounded-full',
          dotColor,
          shouldPulse && 'animate-pulse'
        )} />
        <span className={clsx('text-[10px] uppercase tracking-wider font-semibold', color)}>
          {status}
        </span>
      </div>
    </div>
  )
}

export default function StatusHUD() {
  const { subsystems } = useTars()

  return (
    <div className="flex items-center gap-1 divide-x divide-panel-border">
      <StatusItem
        label="Link"
        status={subsystems.websocket}
        icon={subsystems.websocket === 'connected' ? <Wifi size={13} /> : <WifiOff size={13} />}
      />
      <StatusItem
        label="Agent"
        status={subsystems.agent}
        icon={<Bot size={13} />}
      />
      <StatusItem
        label="Mac"
        status={subsystems.mac}
        icon={<Monitor size={13} />}
      />
      <StatusItem
        label="Claude"
        status={subsystems.claude}
        icon={<Brain size={13} />}
      />
    </div>
  )
}
