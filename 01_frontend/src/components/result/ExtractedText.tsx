interface ExtractedTextProps {
  text: string
}

export default function ExtractedText({ text }: ExtractedTextProps) {
  const lines = text.split('\n')

  return (
    <div className="flex flex-1 overflow-auto font-mono text-sm">
      <div className="flex flex-col items-end px-3 py-3 text-muted-foreground select-none border-r border-border bg-muted/30">
        {lines.map((_, i) => (
          <span key={i} className="text-xs leading-6">{i + 1}</span>
        ))}
      </div>
      <pre className="flex-1 p-3 leading-6 whitespace-pre-wrap text-foreground">{text}</pre>
    </div>
  )
}
