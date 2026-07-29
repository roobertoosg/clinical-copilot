import { NavLink } from 'react-router-dom'
import {
  ChevronDown,
  ClipboardPlus,
  FileText,
  History,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  Users,
} from 'lucide-react'
import logoUrl from '../assets/logo.svg'

const navItems = [
  { to: '/dashboard', label: 'Inicio', icon: Home },
  { to: '/', label: 'Nueva Consulta', icon: ClipboardPlus, end: true },
  { to: '/consultas', label: 'Consultas', icon: FileText },
  { to: '/pacientes', label: 'Pacientes', icon: Users },
  { to: '/historial', label: 'Historial', icon: History },
]

function Sidebar({ isCollapsed, toggleSidebar }) {
  const handleSidebarClick = () => {
    if (isCollapsed) {
      toggleSidebar()
    }
  }

  const handleToggleClick = (event) => {
    event.stopPropagation()
    toggleSidebar()
  }

  return (
    <aside
      className={`sidebar${isCollapsed ? ' sidebar--collapsed' : ''}`}
      onClick={handleSidebarClick}
      role={isCollapsed ? 'button' : undefined}
      tabIndex={isCollapsed ? 0 : undefined}
      onKeyDown={
        isCollapsed
          ? (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                toggleSidebar()
              }
            }
          : undefined
      }
      aria-label={isCollapsed ? 'Expandir barra lateral' : undefined}
    >
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <img
            className="brand-logo"
            src={logoUrl}
            alt="Aura Clinical Copilot"
            width={38}
            height={40}
          />
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-title">AURA CLINICAL</span>
            <span className="sidebar-brand-subtitle">COPILOT</span>
          </div>
        </div>

        <button
          type="button"
          className="sidebar-toggle"
          onClick={handleToggleClick}
          aria-label={isCollapsed ? 'Expandir menú' : 'Colapsar menú'}
          title={isCollapsed ? 'Expandir menú' : 'Colapsar menú'}
        >
          {isCollapsed ? (
            <PanelLeftOpen size={16} strokeWidth={2.25} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={16} strokeWidth={2.25} aria-hidden="true" />
          )}
        </button>
      </div>

      <nav className="sidebar-nav" aria-label="Navegación principal">
        {navItems.map(({ to, label, icon: Icon, end }) => (
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
              <Icon size={18} strokeWidth={2} />
            </span>
            <span className="sidebar-link-text">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button type="button" className="sidebar-profile" title="Perfil del médico">
          <img
            className="sidebar-profile-avatar"
            src="https://i.pravatar.cc/80?img=12"
            alt=""
            width={40}
            height={40}
          />
          <span className="sidebar-profile-info">
            <span className="sidebar-profile-name">Dr. Ricardo Mendoza</span>
            <span className="sidebar-profile-role">Médico General</span>
          </span>
          <ChevronDown
            className="sidebar-profile-chevron"
            size={16}
            strokeWidth={2}
            aria-hidden="true"
          />
        </button>

        <div className="sidebar-status-card">
          <span className="sidebar-status-dot" aria-hidden="true" />
          <span className="sidebar-status-text">
            <span className="sidebar-status-title">Sistema operativo</span>
            <span className="sidebar-status-desc">Todos los servicios activos</span>
          </span>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
