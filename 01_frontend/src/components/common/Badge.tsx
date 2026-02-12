import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
  children: ReactNode
}

const variantStyles = {
  default: 'bg-muted text-muted-foreground',
  success: 'bg-success/20 text-success',
  warning: 'bg-warning/20 text-warning',
  error: 'bg-destructive/20 text-destructive',
  info: 'bg-primary/20 text-primary',
}

export default function Badge({ variant = 'default', children }: BadgeProps) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium', variantStyles[variant])}>
      {children}
    </span>
  )
}
