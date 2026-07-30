import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardPlus,
  Search,
  Target,
  TrendingUp,
  UserPlus,
  Users,
  AlertTriangle,
} from 'lucide-react'
import { API_BASE } from '../config'

const DOCTOR_NAME = 'Dr. Ricardo Mendoza'

function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('es-MX', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function DashboardPage() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')

  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(true)

  const [recent, setRecent] = useState([])
  const [recentLoading, setRecentLoading] = useState(true)

  const [alerts, setAlerts] = useState([])
  const [alertsLoading, setAlertsLoading] = useState(true)

  useEffect(() => {
    let active = true

    const load = async (path, setData, setLoading) => {
      setLoading(true)
      try {
        const response = await fetch(`${API_BASE}${path}`)
        if (!response.ok) throw new Error(`Error ${response.status}`)
        const data = await response.json()
        if (active) setData(data)
      } catch {
        if (active) setData(null)
      } finally {
        if (active) setLoading(false)
      }
    }

    load('/dashboard/stats', setStats, setStatsLoading)
    load('/dashboard/recent-consultations', (d) => setRecent(d || []), setRecentLoading)
    load('/dashboard/critical-alerts', (d) => setAlerts(d || []), setAlertsLoading)

    return () => {
      active = false
    }
  }, [])

  const handleSearch = (event) => {
    event.preventDefault()
    const q = searchQuery.trim()
    if (q) navigate(`/pacientes?search=${encodeURIComponent(q)}`)
    else navigate('/pacientes')
  }

  const patientsTotal = stats?.total_patients ?? 4
  const consultationsToday = stats?.consultations_today ?? 0
  const consultationsMonth = stats?.consultations_month ?? 18

  // Precisión IA dinámica (backend: current_ai_accuracy / ai_accuracy_trend)
  const aiPrecision = Math.round(stats?.current_ai_accuracy ?? 100)
  const aiTrendRaw = Number(stats?.ai_accuracy_trend ?? 0)
  const aiTrendRounded = Math.round(aiTrendRaw)
  const aiTrendSign = aiTrendRounded > 0 ? '+' : ''
  const aiTrendText = `${aiTrendSign}${aiTrendRounded}% vs. mes anterior`
  const aiTrendTone = aiTrendRounded > 0 ? 'up' : 'muted'

  const statCards = [
    {
      key: 'patients',
      label: 'Pacientes Totales',
      value: patientsTotal,
      icon: Users,
      accent: 'stat-card--green',
      trend: { text: '+12% vs. mes anterior', tone: 'up' },
    },
    {
      key: 'today',
      label: 'Consultas Hoy',
      value: consultationsToday,
      icon: CalendarDays,
      accent: 'stat-card--green',
      trend: {
        text: consultationsToday > 0 ? 'En curso hoy' : 'Sin consultas hoy',
        tone: 'muted',
      },
    },
    {
      key: 'month',
      label: 'Consultas del Mes',
      value: consultationsMonth,
      icon: TrendingUp,
      accent: 'stat-card--green',
      trend: { text: '+8% vs. mes anterior', tone: 'up' },
    },
    {
      key: 'ai',
      label: 'Precisión IA',
      value: `${aiPrecision}%`,
      icon: Target,
      accent: 'stat-card--rose',
      trend: { text: aiTrendText, tone: aiTrendTone },
    },
  ]

  return (
    <div className="dashboard-page">
      <section className="dashboard-hero">
        <div className="dashboard-hero-text">
          <p className="dashboard-hero-eyebrow">Bienvenido de nuevo</p>
          <h1 className="dashboard-hero-title">
            Hola, {DOCTOR_NAME}{' '}
            <span aria-hidden="true">👋</span>
          </h1>
          <p className="dashboard-hero-subtitle">
            Este es el resumen de tu actividad clínica.
          </p>
        </div>

        <div className="dashboard-hero-tools">
          <form className="dashboard-search" onSubmit={handleSearch} role="search">
            <Search className="dashboard-search-icon" size={18} strokeWidth={2} aria-hidden="true" />
            <input
              type="search"
              className="dashboard-search-input"
              placeholder="Buscar pacientes, consultas..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Buscar pacientes, consultas"
            />
          </form>
          <button type="button" className="dashboard-bell" aria-label="Notificaciones">
            <Bell size={18} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>

        <div className="dashboard-actions">
          <button
            type="button"
            className="action-button action-button--primary"
            onClick={() => navigate('/')}
          >
            <span className="action-button-icon" aria-hidden="true">
              <ClipboardPlus size={20} strokeWidth={2} />
            </span>
            <span className="action-button-text">
              <span className="action-button-title">Iniciar Consulta</span>
              <span className="action-button-desc">Abrir el workspace clínico</span>
            </span>
          </button>
          <button
            type="button"
            className="action-button action-button--ghost"
            onClick={() => navigate('/pacientes')}
          >
            <span className="action-button-icon" aria-hidden="true">
              <UserPlus size={20} strokeWidth={2} />
            </span>
            <span className="action-button-text">
              <span className="action-button-title">
                Registrar Paciente
                <ChevronDown size={14} strokeWidth={2.5} aria-hidden="true" />
              </span>
              <span className="action-button-desc">Alta y gestión de pacientes</span>
            </span>
          </button>
        </div>
      </section>

      <section className="dashboard-stats">
        {statCards.map((card) => {
          const Icon = card.icon
          return (
            <div key={card.key} className={`stat-card ${card.accent}`}>
              <span className="stat-card-icon" aria-hidden="true">
                <Icon size={20} strokeWidth={2} />
              </span>
              <div className="stat-card-body">
                <span className="stat-card-label">{card.label}</span>
                {statsLoading ? (
                  <span className="skeleton skeleton-stat" aria-hidden="true" />
                ) : (
                  <span className="stat-card-value">{card.value}</span>
                )}
                <span className={`stat-card-trend stat-card-trend--${card.trend.tone}`}>
                  {card.trend.text}
                </span>
              </div>
            </div>
          )
        })}
      </section>

      <div className="dashboard-grid">
        <section className="dashboard-panel">
          <div className="dashboard-panel-head">
            <h2 className="dashboard-panel-title">Consultas Recientes</h2>
            <button
              type="button"
              className="link-button"
              onClick={() => navigate('/consultas')}
            >
              Ver todas <ChevronRight size={14} strokeWidth={2.5} aria-hidden="true" />
            </button>
          </div>

          {recentLoading ? (
            <div className="skeleton-list">
              {[0, 1, 2, 3].map((i) => (
                <span key={i} className="skeleton skeleton-row" aria-hidden="true" />
              ))}
            </div>
          ) : recent.length > 0 ? (
            <div className="recent-list">
              {recent.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className="recent-item"
                  onClick={() => navigate('/consultas')}
                  title="Ver detalle en Consultas"
                >
                  <span className="recent-item-main">
                    <span className="recent-item-folio">
                      {c.folio || `#${c.id}`}
                    </span>
                    <span className="recent-item-patient">{c.patient_name}</span>
                  </span>
                  <span className="recent-item-side">
                    <span className="recent-item-date">
                      {formatDateTime(c.date)}
                    </span>
                    <span className="recent-item-arrow" aria-hidden="true">
                      <ChevronRight size={16} strokeWidth={2} />
                    </span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-results">
              <div className="empty-icon" aria-hidden="true" />
              <p>Aún no hay consultas procesadas.</p>
            </div>
          )}
        </section>

        <div className="dashboard-side-stack">
          <section className="dashboard-panel dashboard-panel--alerts">
            <div className="dashboard-panel-head">
              <h2 className="dashboard-panel-title">
                <AlertTriangle
                  className="alerts-title-icon"
                  size={18}
                  strokeWidth={2}
                  aria-hidden="true"
                />
                Alertas Críticas
              </h2>
            </div>

            {alertsLoading ? (
              <div className="skeleton-list">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="skeleton skeleton-row skeleton-row--tall"
                    aria-hidden="true"
                  />
                ))}
              </div>
            ) : alerts.length > 0 ? (
              <ul className="critical-alert-list">
                {alerts.map((a) => (
                  <li key={a.id} className="critical-alert-item">
                    <div className="critical-alert-head">
                      <span className="critical-alert-patient">
                        {a.patient_name}
                      </span>
                      <span className="critical-alert-badge">
                        {a.severity || 'Alta'}
                      </span>
                    </div>
                    <p className="critical-alert-desc">{a.description}</p>
                    <div className="critical-alert-foot">
                      {a.alert_type && (
                        <span className="critical-alert-type">{a.alert_type}</span>
                      )}
                      <span className="critical-alert-date">
                        {formatDateTime(a.date)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="critical-alert-empty">
                <span className="critical-alert-empty-icon" aria-hidden="true">
                  <CheckCircle2 size={22} strokeWidth={2} />
                </span>
                <p>Sin alertas críticas recientes. Todo en orden.</p>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
