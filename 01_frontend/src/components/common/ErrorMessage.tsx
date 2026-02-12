import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button as ShadcnButton } from '@/components/ui/button'

interface ErrorMessageProps {
  message: string
  onRetry?: () => void
}

export default function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  return (
    <Alert variant="destructive">
      <AlertDescription className="flex items-center justify-between">
        <span>{message}</span>
        {onRetry && (
          <ShadcnButton variant="outline" size="sm" onClick={onRetry}>
            Retry
          </ShadcnButton>
        )}
      </AlertDescription>
    </Alert>
  )
}
