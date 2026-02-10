// Auth types

export interface User {
  id: string
  email: string
  is_admin: boolean
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
}

export interface AuthResponse {
  user: User
  token: string
  expires_at: string
}
