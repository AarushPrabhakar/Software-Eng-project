import axios from 'axios'
import { supabase } from './supabaseClient'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
})

api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data?.session?.access_token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api

// FastAPI returns errors as { detail: "..." } (or a list for validation errors).
export function errMsg(err, fallback = 'Something went wrong.') {
  const d = err?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d) && d[0]?.msg) return d[0].msg
  return err?.message || fallback
}
