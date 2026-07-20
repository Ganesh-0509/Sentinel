import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Alerts } from './pages/Alerts'
import { Analytics } from './pages/Analytics'
import { Compliance } from './pages/Compliance'
import { Evidence } from './pages/Evidence'
import { Incidents } from './pages/Incidents'
import { MapPage } from './pages/MapPage'
import { Overview } from './pages/Overview'
import { Permits } from './pages/Permits'
import { ZoneDetailPage } from './pages/ZoneDetailPage'
import { Zones } from './pages/Zones'
import { PlantProvider } from './state/PlantContext'

export default function App() {
  return (
    <PlantProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="map" element={<MapPage />} />
          <Route path="zones" element={<Zones />} />
          <Route path="zones/:zoneId" element={<ZoneDetailPage />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="permits" element={<Permits />} />
          <Route path="compliance" element={<Compliance />} />
          <Route path="evidence" element={<Evidence />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </PlantProvider>
  )
}
