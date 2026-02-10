// Right panel: OCR text result with line numbers, scroll sync

interface ExtractedTextProps {
  text: string
}

export default function ExtractedText({ text }: ExtractedTextProps) {
  const lines = text.split('\n')

  return (
    <div className="extracted-text">
      <div className="line-numbers">
        {lines.map((_, i) => (
          <span key={i} className="line-number">{i + 1}</span>
        ))}
      </div>
      <pre className="text-content">{text}</pre>
    </div>
  )
}
