import { Outlet, Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  Filter,
  Sparkles,
  Mail,
  ShieldOff,
  Clock,
  Target,
} from 'lucide-react'

const navItems = [
  { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/raw-posts', icon: FileText, label: 'Raw Posts' },
  { path: '/filter-results', icon: Filter, label: 'Filter Results' },
  { path: '/qualified', icon: Sparkles, label: 'AI Qualified' },
  { path: '/email-queue', icon: Mail, label: 'Email Queue' },
  { path: '/suppression', icon: ShieldOff, label: 'Suppression List' },
  { path: '/pipeline-state', icon: Clock, label: 'Pipeline State' },
]

function Layout() {
  const location = useLocation()
  const isActive = (path) => location.pathname === path

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-card/90 backdrop-blur-md">
        <div className="flex h-14 items-center px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
              <Target className="h-5 w-5 text-primary" />
            </span>
            <h1 className="text-xl font-semibold tracking-tight">
              Lead Gen Pipeline
            </h1>
          </div>
        </div>
      </header>

      <div className="flex">
        <aside className="w-56 shrink-0 border-r border-border bg-card/50 hidden lg:block">
          <nav className="flex flex-col gap-0.5 p-3">
            {navItems.map((item) => {
              const Icon = item.icon
              const active = isActive(item.path)
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    active
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  }`}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {item.label}
                </Link>
              )
            })}
          </nav>
        </aside>

        <main className="flex-1 overflow-auto p-4 lg:p-6">
          {/* Mobile nav: horizontal scroll */}
          <nav className="flex gap-1 overflow-x-auto pb-3 mb-4 lg:hidden border-b border-border -mx-4 px-4">
            {navItems.map((item) => {
              const Icon = item.icon
              const active = isActive(item.path)
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`shrink-0 flex items-center gap-1.5 rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                    active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {item.label}
                </Link>
              )
            })}
          </nav>
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default Layout
