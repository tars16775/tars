import { useState, useCallback } from 'react'
import { ShieldAlert, ShieldOff } from 'lucide-react'
import { useTars } from '../context/ConnectionContext'
import clsx from 'clsx'

export default function KillSwitch() {
  const { killAgent, subsystems } = useTars()
  const [armed, setArmed] = useState(false)

  const handleClick = useCallback(() => {
    if (!armed) {
      setArmed(true)
      // Auto-disarm after 5 seconds
      setTimeout(() => setArmed(false), 5000)
    } else {
      killAgent()
      setArmed(false)
    }
  }, [armed, killAgent])

  if (subsystems.agent === 'killed') {
    return (
      <button
        disabled
        className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-widest bg-signal-red/10 text-signal-red/50 border border-signal-red/20 cursor-not-allowed"
      >
        <ShieldOff size={12} />
        KILLED
      </button>
    )
  }

  return (
    <button
      onClick={handleClick}
      className={clsx(
        'flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-widest transition-all duration-200',
        armed
          ? 'bg-signal-red/30 text-signal-red border border-signal-red shadow-glow-red animate-pulse'
          : 'bg-signal-red/10 text-signal-red/70 border border-signal-red/30 hover:bg-signal-red/20 hover:border-signal-red/50'
      )}
    >
      <ShieldAlert size={12} />
      {armed ? 'CONFIRM KILL' : 'KILL'}
    </button>
  )
}
