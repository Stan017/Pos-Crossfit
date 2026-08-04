import { useState, lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Login from './components/Login'
import { getClave, setSesionInvalidaHandler } from './services/api'

const Dashboard        = lazy(() => import('./pages/Dashboard'))
const Gyms              = lazy(() => import('./pages/Gyms'))
const PagosPendientes   = lazy(() => import('./pages/PagosPendientes'))

function PageLoader() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: '#aaa', fontSize: '0.9rem' }}>
      Cargando…
    </div>
  )
}

const NAV = [
  { to: '/',                label: 'Dashboard',       icon: 'monitoring'     },
  { to: '/gyms',             label: 'Establecimientos', icon: 'domain'         },
  { to: '/pagos-pendientes', label: 'Pagos pendientes', icon: 'receipt_long'  },
]

export default function App() {
  // null = verificando, false = sin sesión, true = autenticado
  const [autenticado, setAutenticado] = useState(getClave() ? null : false)

  useEffect(() => {
    setSesionInvalidaHandler(() => setAutenticado(false))
  }, [])

  useEffect(() => {
    document.title = 'DarkCross Admin'
  }, [])

  // Si ya hay una clave guardada, la primera petición de la página que se
  // cargue confirma o revoca la sesión vía el interceptor de 403 — no hace
  // falta un ping explícito acá, alcanza con optimistamente mostrar la app.
  useEffect(() => {
    if (autenticado === null) setAutenticado(true)
  }, [autenticado])

  if (autenticado === null) return <PageLoader />

  if (!autenticado) {
    return <Login onLogin={() => setAutenticado(true)} />
  }

  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <div className="logo">DarkCross</div>
          <ul>
            {NAV.map(({ to, label, icon }) => (
              <li key={to}>
                <NavLink to={to} end className={({ isActive }) => isActive ? 'active' : ''}>
                  <span className="material-symbols-outlined nav-icon">{icon}</span>
                  <span>{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
          <button className="btn-cerrar-sesion" onClick={() => { localStorage.removeItem('darkcross_admin_key'); setAutenticado(false) }}>
            <span className="material-symbols-outlined nav-icon">logout</span>
            <span>Cerrar sesión</span>
          </button>
        </nav>
        <main className="content">
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/"                 element={<Dashboard />}      />
              <Route path="/gyms"              element={<Gyms />}           />
              <Route path="/pagos-pendientes"  element={<PagosPendientes />} />
              <Route path="*"                  element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </BrowserRouter>
  )
}
