import LoginForm from '../components/auth/LoginForm'

export default function LoginPage() {
  return (
    <div className="auth-page">
      <div className="auth-container">
        <h1>Welcome Back</h1>
        <p className="auth-subtitle">Sign in to your OCR Platform account</p>
        <LoginForm />
      </div>
    </div>
  )
}
