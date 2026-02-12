import RegisterForm from '../components/auth/RegisterForm'

export default function RegisterPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-[400px] p-8 bg-card rounded-lg border border-border">
        <h1 className="text-2xl font-bold text-foreground mb-2">Create Account</h1>
        <p className="text-sm text-muted-foreground mb-6">Sign up to start using OCR Platform</p>
        <RegisterForm />
      </div>
    </div>
  )
}
