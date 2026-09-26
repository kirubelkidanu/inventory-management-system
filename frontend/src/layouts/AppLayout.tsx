import React, { useState } from 'react'
import { Outlet, NavLink, useNavigate, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import {
  Boxes,
  LayoutDashboard,
  PackageCheck,
  Tags,
  ClipboardList,
  ArrowDownToLine,
  ArrowUpFromLine,
  Truck,
  PackageOpen,
  Undo2,
  Sliders,
  Scale,
  MapPin,
  CheckSquare,
  LogOut,
  Menu,
  X,
  Warehouse as WarehouseIcon,
  Briefcase,
  ShieldCheck,
} from 'lucide-react'

interface NavItem {
  name: string
  href: string
  icon: React.ElementType
  badge?: string
}

interface NavSection {
  section: string
  items: NavItem[]
}

const navigationSections: NavSection[] = [
  {
    section: 'Overview',
    items: [
      { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    ],
  },
  {
    section: 'Inventory & Catalog',
    items: [
      { name: 'Inventory Balances', href: '/inventory', icon: PackageCheck },
      { name: 'Item Master', href: '/items', icon: Tags },
    ],
  },
  {
    section: 'Transactions',
    items: [
      { name: 'Transactions Ledger', href: '/transactions', icon: ClipboardList },
      { name: 'GRV (Receiving)', href: '/transactions/grv', icon: ArrowDownToLine },
      { name: 'SIV (Issuing)', href: '/transactions/siv', icon: ArrowUpFromLine },
      { name: 'ISTV (Transfer Out)', href: '/transactions/istv', icon: Truck },
      { name: 'ISTRV (Transfer In)', href: '/transactions/istrv', icon: PackageOpen },
      { name: 'SRV (Return)', href: '/transactions/srv', icon: Undo2 },
      { name: 'Stock Adjustment', href: '/transactions/adjustment', icon: Sliders },
    ],
  },
  {
    section: 'Reports & Reconciliation',
    items: [
      { name: 'Trial Balance Ledger', href: '/reports/trial-balance', icon: Scale },
      { name: 'In-Transit Tracking', href: '/reports/in-transit', icon: MapPin },
      { name: 'Physical Reconciliation', href: '/reconciliation', icon: CheckSquare },
    ],
  },
]

export const AppLayout: React.FC = () => {
  const { user, isAuthenticated, isLoading, logout } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-slate-900">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-sky-400 border-t-transparent" />
          <p className="text-sm font-medium text-slate-300">Loading workspace...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const getRoleBadgeColor = (role?: string) => {
    switch (role) {
      case 'ADMIN':
        return 'bg-purple-100 text-purple-700 border-purple-200'
      case 'INVENTORY_MANAGER':
        return 'bg-sky-100 text-sky-700 border-sky-200'
      case 'STORE_KEEPER':
        return 'bg-amber-100 text-amber-700 border-amber-200'
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200'
    }
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/60 backdrop-blur-xs lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-slate-900 transition-transform duration-200 ease-in-out lg:static lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Sidebar Header */}
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800 px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500 text-white shadow-md shadow-sky-500/20">
              <Boxes className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-white">Enterprise IMS</h1>
              <p className="text-xs text-slate-400">Inventory Management</p>
            </div>
          </div>
          <button
            type="button"
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 space-y-6 overflow-y-auto px-4 py-5">
          {navigationSections.map((sec) => (
            <div key={sec.section}>
              <h3 className="px-3 text-xs font-semibold tracking-wider text-slate-400 uppercase">
                {sec.section}
              </h3>
              <div className="mt-2 space-y-1">
                {sec.items.map((item) => (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    end={item.href === '/'}
                    onClick={() => setSidebarOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                        isActive
                          ? 'bg-sky-600 text-white shadow-xs'
                          : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{item.name}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Sidebar Footer / User role */}
        <div className="border-t border-slate-800 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-white">
                {user?.full_name?.charAt(0) || 'U'}
              </div>
              <div className="truncate">
                <p className="truncate text-xs font-semibold text-white">{user?.full_name}</p>
                <p className="truncate text-[10px] text-slate-400">{user?.email}</p>
              </div>
            </div>
            <span
              className={cn(
                'inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium tracking-tight',
                getRoleBadgeColor(user?.role)
              )}
            >
              {user?.role?.replace('_', ' ')}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Header */}
        <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 shadow-xs sm:px-6 lg:px-8">
          <div className="flex items-center gap-4">
            <button
              type="button"
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900 lg:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Environment / Context Pills */}
            <div className="hidden items-center gap-3 sm:flex">
              <div className="flex items-center gap-1.5 rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                <WarehouseIcon className="h-3.5 w-3.5 text-slate-500" />
                <span>Central Logistics WH</span>
              </div>
              <div className="flex items-center gap-1.5 rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                <Briefcase className="h-3.5 w-3.5 text-slate-500" />
                <span>All Projects</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-1 text-xs text-slate-500 md:flex">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
              <span>Dual-Write Engine Active</span>
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-red-600"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </header>

        {/* Main View Container */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppLayout
