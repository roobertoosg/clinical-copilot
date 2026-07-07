import { Routes, Route } from 'react-router-dom'
import './App.css'
import MainLayout from './components/MainLayout'
import ClinicalWorkspace from './pages/ClinicalWorkspace'
import PlaceholderPage from './pages/PlaceholderPage'

function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<ClinicalWorkspace />} />
        <Route
          path="dashboard"
          element={
            <PlaceholderPage
              title="Dashboard"
              description="Panel general con métricas y actividad reciente."
            />
          }
        />
        <Route
          path="pacientes"
          element={
            <PlaceholderPage
              title="Pacientes"
              description="Directorio y fichas de pacientes."
            />
          }
        />
        <Route
          path="consultas"
          element={
            <PlaceholderPage
              title="Consultas"
              description="Listado de consultas registradas."
            />
          }
        />
        <Route
          path="historial"
          element={
            <PlaceholderPage
              title="Historial"
              description="Historial clínico y notas previas."
            />
          }
        />
      </Route>
    </Routes>
  )
}

export default App
