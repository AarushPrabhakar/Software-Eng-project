// Light/dark theme. Follows the device setting until the person picks one;
// after that their choice is remembered in this browser.
const KEY = 'lostlink-theme'

function stored() {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

export function systemTheme() {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function currentTheme() {
  return stored() || systemTheme()
}

export function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', theme === 'dark' ? '#0a0e1c' : '#2438F0')
}

export function saveTheme(theme) {
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    /* private mode: the choice just won't persist */
  }
  applyTheme(theme)
}

export function followsSystem() {
  return stored() === null
}
