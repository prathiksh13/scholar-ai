import { Outlet } from 'react-router-dom'
import Waves from './Waves'

export default function Layout() {
  return (
    <div className="relative min-h-screen">
      <div className="waves-background">
        <Waves
          lineColor="rgba(125, 211, 252, 0.35)"
          backgroundColor="transparent"
          waveSpeedX={0.02}
          waveSpeedY={0.01}
          waveAmpX={40}
          waveAmpY={20}
          friction={0.9}
          tension={0.01}
          maxCursorMove={120}
          xGap={12}
          yGap={36}
        />
      </div>
      <div className="relative z-10">
        <Outlet />
      </div>
    </div>
  )
}
