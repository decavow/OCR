import { ButtonHTMLAttributes, ReactNode } from 'react'
import { Button as ShadcnButton } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger'
  children: ReactNode
}

const variantMap = {
  primary: 'default',
  secondary: 'secondary',
  danger: 'destructive',
} as const

export default function Button({ variant = 'primary', children, className, ...props }: ButtonProps) {
  return (
    <ShadcnButton variant={variantMap[variant]} className={cn(className)} {...props}>
      {children}
    </ShadcnButton>
  )
}
