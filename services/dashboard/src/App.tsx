import { Routes, Route, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  GitBranch,
  Database,
  Mail,
  UserPlus,
  Settings as SettingsIcon,
  ChevronRight,
} from 'lucide-react'
import Overview from './pages/Overview'
import Pipeline from './pages/Pipeline'
import Data from './pages/Data'
import Settings from './pages/Settings'
import EmailControl from './pages/EmailControl'
import ManualOutreach from './pages/ManualOutreach'

const navItems = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/pipeline', label: 'Pipeline', icon: GitBranch },
  { to: '/data', label: 'Data', icon: Database },
  { to: '/email', label: 'Email', icon: Mail },
  { to: '/manual-outreach', label: 'No email', icon: UserPlus },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

function Nav() {
  return (
    <nav className="flex flex-col gap-0.5 px-2 py-2">
      {navItems.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-200 cursor-pointer ${
              isActive
                ? 'bg-primary/15 text-primary border border-primary/20'
                : 'text-sidebar-foreground/80 hover:bg-sidebar-border/50 hover:text-sidebar-foreground border border-transparent'
            }`
          }
        >
          <Icon className="h-5 w-5 shrink-0" strokeWidth={2} />
          <span className="truncate">{label}</span>
          <ChevronRight className="ml-auto h-4 w-4 shrink-0 opacity-50" />
        </NavLink>
      ))}
    </nav>
  )
}

export default function App() {
  return (
    <div className="min-h-screen flex bg-background">
      {/* Sidebar */}
      <aside className="hidden lg:flex w-56 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
        <div className="flex h-14 shrink-0 items-center gap-2 border-b border-sidebar-border px-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20 text-primary">
            <LayoutDashboard className="h-4 w-4" strokeWidth={2.5} />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold tracking-tight text-sidebar-foreground">Lead Gen</span>
            <span className="text-xs text-sidebar-foreground/60">Dashboard</span>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto py-4">
          <Nav />
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col min-w-0">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-4 border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80 lg:px-8">
          <div className="flex flex-1 items-center gap-4">
            <span className="text-sm font-medium text-muted-foreground lg:hidden">Lead Gen</span>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 lg:px-8 lg:py-8">
          <div className="mx-auto max-w-6xl">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/pipeline" element={<Pipeline />} />
              <Route path="/data" element={<Data />} />
              <Route path="/email" element={<EmailControl />} />
              <Route path="/manual-outreach" element={<ManualOutreach />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </div>
        </main>
      </div>

      {/* Mobile nav bar at bottom */}
      <nav className="fixed bottom-0 left-0 right-0 z-30 flex items-center justify-around border-t border-border bg-card/95 py-2 backdrop-blur lg:hidden">
        {navItems.slice(0, 5).map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors duration-200 ${
                isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
              }`
            }
          >
            <Icon className="h-5 w-5" strokeWidth={2} />
            <span className="truncate max-w-[4rem]">{label}</span>
          </NavLink>
        ))}
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
            }`
          }
        >
          <SettingsIcon className="h-5 w-5" strokeWidth={2} />
          <span>Settings</span>
        </NavLink>
      </nav>

      {/* Spacer for mobile bottom nav */}
      <div className="h-16 lg:hidden" aria-hidden />
    </div>
  )
}
