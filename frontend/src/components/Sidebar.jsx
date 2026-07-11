import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/', label: 'Clinical Workspace', icon: '✚', end: true },
  { to: '/pacientes', label: 'Pacientes', icon: '☺' },
  { to: '/consultas', label: 'Consultas', icon: '❐' },
  { to: '/historial', label: 'Historial', icon: '↺' },
]

function Sidebar({ isCollapsed, toggleSidebar }) {
  return (
    <aside className={`sidebar${isCollapsed ? ' sidebar--collapsed' : ''}`}>
      <div className="sidebar-brand">
        <div className="brand-icon" aria-hidden="true" />
        <div className="sidebar-brand-text">
          <span className="sidebar-brand-title">Clinical Copilot</span>
          <span className="sidebar-brand-subtitle">Asistente clínico</span>
        </div>
      </div>

      <button
        type="button"
        className="sidebar-toggle"
        onClick={toggleSidebar}
        aria-label={isCollapsed ? 'Expandir menú' : 'Colapsar menú'}
        title={isCollapsed ? 'Expandir menú' : 'Colapsar menú'}
      >
        <span className="sidebar-toggle-icon" aria-hidden="true">
          {isCollapsed ? '»' : '«'}
        </span>
      </button>

      <nav className="sidebar-nav" aria-label="Navegación principal">
        {navItems.map(({ to, label, icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `sidebar-link${isActive ? ' sidebar-link--active' : ''}`
            }
            title={label}
          >
            <span className="sidebar-link-icon" aria-hidden="true">
              {icon}
            </span>
            <span className="sidebar-link-text">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="header-badge">
          <span className="header-badge-dot" aria-hidden="true" />
          <span className="sidebar-link-text">IA activa</span>
        </span>
      </div>
    </aside>
  )
}

export default Sidebar
