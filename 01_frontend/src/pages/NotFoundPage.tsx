import { Link } from 'react-router-dom'
import { Button as ShadcnButton } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4">
      <h1 className="text-6xl font-bold text-foreground">404</h1>
      <p className="text-lg text-muted-foreground">Page not found</p>
      <Link to="/">
        <ShadcnButton>Go to Dashboard</ShadcnButton>
      </Link>
    </div>
  )
}
