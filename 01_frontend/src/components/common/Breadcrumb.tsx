interface BreadcrumbProps {
  items: { label: string; href?: string }[]
  onNavigate?: (href: string) => void
}

export default function Breadcrumb({ items, onNavigate }: BreadcrumbProps) {
  return (
    <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
      {items.map((item, index) => (
        <span key={index} className="flex items-center gap-1.5">
          {item.href ? (
            <a
              onClick={() => onNavigate?.(item.href!)}
              className="cursor-pointer hover:text-foreground transition-colors"
            >
              {item.label}
            </a>
          ) : (
            <span className="text-foreground">{item.label}</span>
          )}
          {index < items.length - 1 && <span className="text-muted-foreground">/</span>}
        </span>
      ))}
    </nav>
  )
}
