import { ButtonHTMLAttributes, ReactNode } from 'react'
import { Button as ShadcnButton } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode
  label?: string
}

export default function IconButton({ icon, label, className, ...props }: IconButtonProps) {
  return (
    <ShadcnButton
      variant="ghost"
      size="icon"
      aria-label={label}
      className={cn(className)}
      {...props}
    >
      {icon}
    </ShadcnButton>
  )
}
