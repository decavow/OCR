// "← Back to Batch #1024" pattern

interface BreadcrumbProps {
  items: { label: string; href?: string }[]
  onNavigate?: (href: string) => void
}

export default function Breadcrumb({ items, onNavigate }: BreadcrumbProps) {
  return (
    <nav className="breadcrumb">
      {items.map((item, index) => (
        <span key={index}>
          {item.href ? (
            <a onClick={() => onNavigate?.(item.href!)}>{item.label}</a>
          ) : (
            <span>{item.label}</span>
          )}
          {index < items.length - 1 && <span className="separator">/</span>}
        </span>
      ))}
    </nav>
  )
}
