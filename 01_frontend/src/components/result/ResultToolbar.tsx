import { Button as ShadcnButton } from '@/components/ui/button'
import { Download, Copy } from 'lucide-react'

interface ResultToolbarProps {
  fileId: string
}

export default function ResultToolbar({ fileId }: ResultToolbarProps) {
  const handleDownloadTxt = () => {
    window.open(`/api/v1/files/${fileId}/download?format=txt`, '_blank')
  }

  const handleDownloadJson = () => {
    window.open(`/api/v1/files/${fileId}/download?format=json`, '_blank')
  }

  const handleCopy = () => {
    // Copy handled by parent component
  }

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-border">
      <span className="text-sm font-medium text-foreground">Extracted Text Result</span>
      <div className="flex items-center gap-1">
        <ShadcnButton variant="ghost" size="sm" onClick={handleDownloadTxt}>
          <Download className="h-3 w-3 mr-1" />
          TXT
        </ShadcnButton>
        <ShadcnButton variant="ghost" size="sm" onClick={handleDownloadJson}>
          <Download className="h-3 w-3 mr-1" />
          JSON
        </ShadcnButton>
        <ShadcnButton variant="ghost" size="sm" onClick={handleCopy}>
          <Copy className="h-3 w-3 mr-1" />
          Copy
        </ShadcnButton>
      </div>
    </div>
  )
}
