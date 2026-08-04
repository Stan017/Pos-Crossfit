import { useState, lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Login from './components/Login'
import Registro from './components/Registro'
import { authAPI, setSessionExpiredHandler } from './services/api'

const Dashboard  = lazy(() => import('./pages/Dashboard'))
const CheckIn    = lazy(() => import('./pages/CheckIn'))
const Miembros   = lazy(() => import('./pages/Miembros'))
const Membresias = lazy(() => import('./pages/Membresias'))
const Planes     = lazy(() => import('@shared/pages/Planes'))
const POS        = lazy(() => import('@shared/pages/POS'))
const Inventario = lazy(() => import('@shared/pages/Inventario'))
const Finanzas   = lazy(() => import('./pages/Finanzas'))
const Usuarios   = lazy(() => import('@shared/pages/Usuarios'))
const Ajustes    = lazy(() => import('./pages/Ajustes'))
const Abonos     = lazy(() => import('./pages/Abonos'))
const Horarios     = lazy(() => import('./pages/Horarios'))
const Cobros       = lazy(() => import('./pages/Cobros'))
const Instructores = lazy(() => import('./pages/Instructores'))

function PageLoader() {
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'60vh', color:'#aaa', fontSize:'0.9rem' }}>
      Cargando…
    </div>
  )
}

const NAV = [
  { to: '/dashboard',  label: 'Dashboard',  icon: 'dashboard'            },
  { to: '/horarios',   label: 'Horarios',   icon: 'calendar_month'       },
  { to: '/instructores', label: 'Terapeutas', icon: 'badge'              },
  { to: '/checkin',    label: 'Check-in',   icon: 'how_to_reg'           },
  { to: '/miembros',   label: 'Pacientes',  icon: 'group'                },
  { to: '/membresias', label: 'Membresías', icon: 'card_membership'      },
  { to: '/planes',     label: 'Planes',     icon: 'assignment'           },
  { to: '/',           label: 'POS',        icon: 'point_of_sale'        },
  { to: '/cobros',     label: 'Cobros',     icon: 'receipt_long'         },
  { to: '/inventario', label: 'Inventario', icon: 'inventory_2'          },
  { to: '/abonos',     label: 'Abonos',     icon: 'payments'             },
  { to: '/finanzas',   label: 'Finanzas',   icon: 'account_balance_wallet', adminOnly: true },
  { to: '/usuarios',   label: 'Usuarios',   icon: 'manage_accounts',        adminOnly: true },
  { to: '/ajustes',    label: 'Ajustes',    icon: 'settings',               adminOnly: true },
]

export default function App() {
  // null = verificando sesión, false = sin sesión, objeto = autenticado
  const [sesion, setSesion] = useState(null)

  useEffect(() => {
    setSessionExpiredHandler(() => setSesion(false))
    authAPI.me()
      .then(({ data }) => setSesion(data))
      .catch(() => setSesion(false))
  }, [])

  useEffect(() => {
    document.title = sesion ? (sesion.gym_nombre || 'Clínica') : 'Clínica'
  }, [sesion])

  async function cerrarSesion() {
    try { await authAPI.logout() } catch {}
    setSesion(false)
  }

  if (sesion === null) {
    return <PageLoader />
  }

  if (!sesion) {
    // Sin BrowserRouter no existe ninguna ruta — antes de loguearse solo
    // había un componente fijo (Login). Ahora hace falta distinguir entre
    // Login y Registro, así que el router se necesita también acá, no solo
    // en la app autenticada de abajo.
    return (
      <BrowserRouter>
        <Routes>
          <Route path="/registro" element={<Registro onRegistrado={setSesion} />} />
          <Route path="*" element={<Login onLogin={setSesion} />} />
        </Routes>
      </BrowserRouter>
    )
  }

  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <div className="logo">{sesion.gym_nombre || 'Clínica'}</div>
          <ul>
            {NAV.filter(item => !item.adminOnly || sesion.rol === 'admin').map(({ to, label, icon }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) => isActive ? 'active' : ''}
                >
                  <span className="material-symbols-outlined nav-icon">{icon}</span>
                  <span>{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
          <button className="btn-cerrar-sesion" onClick={cerrarSesion}>
            <span className="material-symbols-outlined nav-icon">logout</span>
            <span>Cerrar sesión</span>
          </button>
        </nav>
        <main className="content">
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="/"           element={<POS />}        />
              <Route path="/dashboard"  element={<Dashboard />}  />
              <Route path="/horarios"   element={<Horarios />}   />
              <Route path="/instructores" element={<Instructores />} />
              <Route path="/checkin"    element={<CheckIn />}    />
              <Route path="/miembros"   element={<Miembros />}   />
              <Route path="/membresias" element={<Membresias />} />
              <Route path="/planes"     element={<Planes />}     />
              <Route path="/cobros"     element={<Cobros />}     />
              <Route path="/inventario" element={<Inventario />} />
              <Route path="/abonos"     element={<Abonos />}     />
              <Route path="/finanzas"   element={<Finanzas />}   />
              <Route path="/usuarios"   element={<Usuarios />}   />
              <Route path="/ajustes"    element={
                <Ajustes onNombreActualizado={nombre => setSesion(s => ({ ...s, gym_nombre: nombre }))} />
              } />
            </Routes>
          </Suspense>
        </main>
      </div>
    </BrowserRouter>
  )
}
