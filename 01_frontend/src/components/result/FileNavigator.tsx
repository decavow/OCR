import { Button as ShadcnButton } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, ArrowLeft } from 'lucide-react'

interface FileNavigatorProps {
  fileName: string
  currentIndex: number
  totalFiles: number
  onPrev: () => void
  onNext: () => void
  onBack: () => void
}

export default function FileNavigator({
  fileName,
  currentIndex,
  totalFiles,
  onPrev,
  onNext,
  onBack,
}: FileNavigatorProps) {
  return (
    <div className="flex items-center justify-between">
      <ShadcnButton variant="ghost" size="sm" onClick={onBack}>
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back to Batch
      </ShadcnButton>

      <span className="text-sm font-medium text-foreground">{fileName}</span>

      <div className="flex items-center gap-2">
        <ShadcnButton variant="ghost" size="icon" className="h-8 w-8" onClick={onPrev} disabled={currentIndex === 0}>
          <ChevronLeft className="h-4 w-4" />
        </ShadcnButton>
        <span className="text-sm text-muted-foreground">
          File {currentIndex + 1} of {totalFiles}
        </span>
        <ShadcnButton variant="ghost" size="icon" className="h-8 w-8" onClick={onNext} disabled={currentIndex === totalFiles - 1}>
          <ChevronRight className="h-4 w-4" />
        </ShadcnButton>
      </div>
    </div>
  )
}
