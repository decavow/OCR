// Bottom-right: "Ln 22, Col 1" indicator

interface TextCursorProps {
  line: number
  column: number
}

export default function TextCursor({ line, column }: TextCursorProps) {
  return (
    <div className="text-cursor">
      Ln {line}, Col {column}
    </div>
  )
}
