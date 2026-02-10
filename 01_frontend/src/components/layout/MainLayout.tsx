import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

// Layout wrapper (sidebar + content area)
export default function MainLayout() {
  return (
    <div className="main-layout">
      <Sidebar />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
