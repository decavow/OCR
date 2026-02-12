interface TextCursorProps {
  line: number
  column: number
}

export default function TextCursor({ line, column }: TextCursorProps) {
  return (
    <div className="text-xs text-muted-foreground text-right py-1 px-4">
      Ln {line}, Col {column}
    </div>
  )
}
