import { useEffect, useState } from 'react'
import { NavLink, Link, useNavigate } from 'react-router-dom'
import { Bell, LogOut, LayoutGrid, Search, PackagePlus, Activity } from 'lucide-react'
import api from '../api.js'
import { useAuth } from '../context/AuthContext.jsx'
import ThemeToggle from './ThemeToggle.jsx'

function initialsOf(name) {
  return name
    .split(' ')
    .filter(Boolean)
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

export default function Nav() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [unread, setUnread] = useState(0)
  const [isAdmin, setIsAdmin] = useState(false)
  const [profileName, setProfileName] = useState('')

  useEffect(() => {
    let stop = false
    const poll = () =>
      api
        .get('/notifications')
        .then((r) => !stop && setUnread(r.data.unread_count))
        .catch(() => {})
    poll()
    const timer = setInterval(poll, 30000)
    window.addEventListener('notifications-changed', poll)
    api
      .get('/auth/me')
      .then((r) => {
        if (stop) return
        setIsAdmin(r.data.user.role === 'admin')
        setProfileName(r.data.user.name || '')
      })
      .catch(() => {})
    return () => {
      stop = true
      clearInterval(timer)
      window.removeEventListener('notifications-changed', poll)
    }
  }, [])

  const emailName = user?.email ? user.email.split('@')[0].replace(/[._]/g, ' ') : ''
  const name = profileName || emailName.replace(/\b\w/g, (c) => c.toUpperCase())

  async function handleSignOut() {
    await signOut()
    navigate('/')
  }

  const link = ({ isActive }) => `toplink${isActive ? ' is-active' : ''}`
  const tab = ({ isActive }) => `tab${isActive ? ' is-active' : ''}`

  return (
    <>
      <header className="topbar">
        <div className="topbar__inner">
          <Link to="/feed" className="brand" aria-label="LostLink home">
            <span className="brand__mark" />
            LostLink
          </Link>
          <nav className="topbar__links" aria-label="Main">
            <NavLink to="/feed" className={link}>Feed</NavLink>
            <NavLink to="/report/lost" className={link}>Report lost</NavLink>
            <NavLink to="/report/found" className={link}>Report found</NavLink>
            <NavLink to="/my" className={link}>My activity</NavLink>
            {isAdmin && <NavLink to="/admin" className={link}>Admin</NavLink>}
          </nav>
          <div className="topbar__right">
            <ThemeToggle />
            <Link to="/notifications" className="iconbtn" aria-label={`Alerts, ${unread} unread`}>
              <Bell size={20} />
              {unread > 0 && <span className="iconbtn__dot">{unread > 9 ? '9+' : unread}</span>}
            </Link>
            <div className="who">
              <span>{name}</span>
              <span className="avatar" aria-hidden="true">{initialsOf(name) || '?'}</span>
            </div>
            <button className="signout" onClick={handleSignOut} aria-label="Sign out">
              <LogOut size={18} />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <nav className="tabbar" aria-label="Main">
        <NavLink to="/feed" className={tab}><LayoutGrid size={22} />Feed</NavLink>
        <NavLink to="/report/lost" className={tab}><Search size={22} />Lost</NavLink>
        <NavLink to="/report/found" className={tab}><PackagePlus size={22} />Found</NavLink>
        <NavLink to="/my" className={tab}><Activity size={22} />Activity</NavLink>
      </nav>
    </>
  )
}
