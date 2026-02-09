import { ButtonHTMLAttributes, ReactNode } from 'react'

// For nav arrows, copy, download icons
interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode
  label?: string
}

export default function IconButton({ icon, label, ...props }: IconButtonProps) {
  return (
    <button className="icon-button" aria-label={label} {...props}>
      {icon}
    </button>
  )
}
