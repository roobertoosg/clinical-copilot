import { Routes, Route } from 'react-router-dom'
import './App.css'
import MainLayout from './components/MainLayout'
import ClinicalWorkspace from './pages/ClinicalWorkspace'
import DashboardPage from './pages/DashboardPage'
import PatientsPage from './pages/PatientsPage'
import ConsultationsPage from './pages/ConsultationsPage'
import HistoryPage from './pages/HistoryPage'
import PlaceholderPage from './pages/PlaceholderPage'

function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<ClinicalWorkspace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="pacientes" element={<PatientsPage />} />
        <Route path="consultas" element={<ConsultationsPage />} />
        <Route path="historial" element={<HistoryPage />} />
        <Route
          path="configuracion"
          element={
            <PlaceholderPage
              title="Configuración"
              description="La configuración del sistema estará disponible próximamente."
            />
          }
        />
      </Route>
    </Routes>
  )
}

export default App
