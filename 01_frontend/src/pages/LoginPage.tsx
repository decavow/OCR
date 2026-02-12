import LoginForm from '../components/auth/LoginForm'

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-[400px] p-8 bg-card rounded-lg border border-border">
        <h1 className="text-2xl font-bold text-foreground mb-2">Welcome Back</h1>
        <p className="text-sm text-muted-foreground mb-6">Sign in to your OCR Platform account</p>
        <LoginForm />
      </div>
    </div>
  )
}
