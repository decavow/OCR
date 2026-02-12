import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface LoadingProps {
  size?: 'small' | 'medium' | 'large'
  text?: string
}

const sizeMap = {
  small: 'h-4 w-4',
  medium: 'h-8 w-8',
  large: 'h-12 w-12',
}

export default function Loading({ size = 'medium', text }: LoadingProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-8">
      <Loader2 className={cn('animate-spin text-primary', sizeMap[size])} />
      {text && <span className="text-sm text-muted-foreground">{text}</span>}
    </div>
  )
}
