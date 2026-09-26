import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/context/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { AppLayout } from '@/layouts/AppLayout'
import { AuthLayout } from '@/layouts/AuthLayout'
import { LoginPage } from '@/features/auth/LoginPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { InventoryBalancesPage } from '@/features/inventory/InventoryBalancesPage'
import { ItemsPage } from '@/features/inventory/ItemsPage'
import { TransactionsListPage } from '@/features/transactions/TransactionsListPage'
import { GRVPage } from '@/features/transactions/GRVPage'
import { SIVPage } from '@/features/transactions/SIVPage'
import { ISTVPage } from '@/features/transactions/ISTVPage'
import { ISTRVPage } from '@/features/transactions/ISTRVPage'
import { SRVPage } from '@/features/transactions/SRVPage'
import { AdjustmentPage } from '@/features/transactions/AdjustmentPage'
import { TrialBalancePage } from '@/features/reports/TrialBalancePage'
import { InTransitPage } from '@/features/reports/InTransitPage'
import { ReconciliationPage } from '@/features/reconciliation/ReconciliationPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Authentication Routes */}
            <Route element={<AuthLayout />}>
              <Route path="/login" element={<LoginPage />} />
            </Route>

            {/* Protected Application Routes guarded by ProtectedRoute */}
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/inventory" element={<InventoryBalancesPage />} />
                <Route path="/items" element={<ItemsPage />} />

                {/* Transactions */}
                <Route path="/transactions" element={<TransactionsListPage />} />
                <Route path="/transactions/grv" element={<GRVPage />} />
                <Route path="/transactions/siv" element={<SIVPage />} />
                <Route path="/transactions/istv" element={<ISTVPage />} />
                <Route path="/transactions/istrv" element={<ISTRVPage />} />
                <Route path="/transactions/srv" element={<SRVPage />} />
                <Route path="/transactions/adjustment" element={<AdjustmentPage />} />

                {/* Reports & Audit */}
                <Route path="/reports/trial-balance" element={<TrialBalancePage />} />
                <Route path="/reports/in-transit" element={<InTransitPage />} />
                <Route path="/reconciliation" element={<ReconciliationPage />} />
              </Route>
            </Route>

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
