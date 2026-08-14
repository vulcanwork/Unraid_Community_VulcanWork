import { Routes, Route, NavLink } from 'react-router-dom';
import { useAuth } from './auth.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Grows from './pages/Grows.jsx';
import GrowDetail from './pages/GrowDetail.jsx';
import Strains from './pages/Strains.jsx';
import StrainDetail from './pages/StrainDetail.jsx';
import Seeds from './pages/Seeds.jsx';
import Breeding from './pages/Breeding.jsx';
import InfusionCalculator from './pages/InfusionCalculator.jsx';

export default function App() {
  const { isAuthed, username, openLogin, logout } = useAuth();

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-title">SeedBreed</div>
          <div className="sidebar-brand-sub">grow · breed · trace</div>
        </div>

        <nav className="nav">
          <div className="nav-section">Tracking</div>
          <NavLink to="/" end>
            <span className="nav-icon">◆</span> Dashboard
          </NavLink>
          <NavLink to="/grows">
            <span className="nav-icon">❀</span> Grows
          </NavLink>

          <div className="nav-section">Genetics</div>
          <NavLink to="/strains">
            <span className="nav-icon">⚘</span> Strains
          </NavLink>
          <NavLink to="/seeds">
            <span className="nav-icon">●</span> Seeds
          </NavLink>
          <NavLink to="/breeding">
            <span className="nav-icon">⚭</span> Breeding
          </NavLink>

          <div className="nav-section">Utilities</div>
          <NavLink to="/infusion-calculator">
            <span className="nav-icon">⚗</span> Infusion Calculator
          </NavLink>
        </nav>

        <div className="sidebar-logo">
          <img
            className="sidebar-logo-img"
            src="/vulcanwork-logo.png"
            alt="VulcanWork"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
          <div className="sidebar-logo-note">Brought to you by VulcanWork</div>
        </div>

        <div className="sidebar-auth">
          {isAuthed ? (
            <>
              <div className="sidebar-auth-user" title="Logged in — you can make changes">
                <span className="nav-icon">●</span> {username}
              </div>
              <button className="small-btn" onClick={logout}>Log out</button>
            </>
          ) : (
            <>
              <div className="sidebar-auth-note">Read-only · browsing as guest</div>
              <button className="small-btn" onClick={openLogin}>Log in to edit</button>
            </>
          )}
        </div>
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/grows" element={<Grows />} />
          <Route path="/grows/:id" element={<GrowDetail />} />
          <Route path="/strains" element={<Strains />} />
          <Route path="/strains/:id" element={<StrainDetail />} />
          <Route path="/seeds" element={<Seeds />} />
          <Route path="/breeding" element={<Breeding />} />
          <Route path="/infusion-calculator" element={<InfusionCalculator />} />
        </Routes>
      </main>
    </div>
  );
}
