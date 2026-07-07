import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/', label: 'Clinical Workspace', icon: '✚', end: true },
  { to: '/pacientes', label: 'Pacientes', icon: '☺' },
  { to: '/consultas', label: 'Consultas', icon: '❐' },
  { to: '/historial', label: 'Historial', icon: '↺' },
]

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon" aria-hidden="true" />
        <div className="sidebar-brand-text">
          <span className="sidebar-brand-title">Clinical Copilot</span>
          <span className="sidebar-brand-subtitle">Asistente clínico</span>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Navegación principal">
        {navItems.map(({ to, label, icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `sidebar-link${isActive ? ' sidebar-link--active' : ''}`
            }
          >
            <span className="sidebar-link-icon" aria-hidden="true">
              {icon}
            </span>
            <span className="sidebar-link-label">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="header-badge">
          <span className="header-badge-dot" aria-hidden="true" />
          IA activa
        </span>
      </div>
    </aside>
  )
}

export default Sidebar
