interface LoadingProps {
  size?: 'small' | 'medium' | 'large'
  text?: string
}

export default function Loading({ size = 'medium', text }: LoadingProps) {
  return (
    <div className={`loading loading-${size}`}>
      <div className="spinner" />
      {text && <span>{text}</span>}
    </div>
  )
}
