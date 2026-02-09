import RegisterForm from '../components/auth/RegisterForm'

export default function RegisterPage() {
  return (
    <div className="auth-page">
      <div className="auth-container">
        <h1>Create Account</h1>
        <p className="auth-subtitle">Sign up to start using OCR Platform</p>
        <RegisterForm />
      </div>
    </div>
  )
}
