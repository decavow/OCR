import client, { setToken, clearToken, getToken } from './client'
import { LoginRequest, RegisterRequest, AuthResponse, User } from '../types'

export async function login(data: LoginRequest): Promise<AuthResponse> {
  const response = await client.post<AuthResponse>('/auth/login', data)
  setToken(response.data.token)
  return response.data
}

export async function register(data: RegisterRequest): Promise<AuthResponse> {
  const response = await client.post<AuthResponse>('/auth/register', data)
  setToken(response.data.token)
  return response.data
}

export async function logout(): Promise<void> {
  try {
    await client.post('/auth/logout')
  } finally {
    clearToken()
  }
}

export async function getMe(): Promise<User> {
  const response = await client.get<User>('/auth/me')
  return response.data
}

export function isAuthenticated(): boolean {
  return getToken() !== null
}
