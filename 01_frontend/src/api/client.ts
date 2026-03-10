import axios from 'axios'
import { API_BASE_URL } from '../config'

const TOKEN_KEY = 'ocr_token'

// Axios instance with interceptors
const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add auth token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Custom event for toast notifications from API errors
function emitApiError(message: string) {
  window.dispatchEvent(new CustomEvent('api-error', { detail: message }))
}

// Response interceptor - handle errors + emit toast events
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      window.location.href = '/login'
    } else if (error.response?.status === 429) {
      emitApiError('Too many requests, please slow down')
    } else if (error.response?.status >= 500) {
      emitApiError('Server error, please try again')
    } else if (!error.response) {
      emitApiError('Connection lost, please check your network')
    }
    return Promise.reject(error)
  }
)

// Token management helpers
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export default client
