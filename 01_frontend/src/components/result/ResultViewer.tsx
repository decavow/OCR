import OriginalPreview from './OriginalPreview'
import ExtractedText from './ExtractedText'
import ResultToolbar from './ResultToolbar'
import ResultMetadata from './ResultMetadata'
import FileNavigator from './FileNavigator'
import TextCursor from './TextCursor'
import { JobResult, FileInfo } from '../../types'

interface ResultViewerProps {
  file: FileInfo
  result: JobResult | null
  currentIndex: number
  totalFiles: number
  onPrev: () => void
  onNext: () => void
  onBack: () => void
}

export default function ResultViewer({
  file,
  result,
  currentIndex,
  totalFiles,
  onPrev,
  onNext,
  onBack,
}: ResultViewerProps) {
  return (
    <div className="flex flex-col h-full">
      <FileNavigator
        fileName={file.original_name}
        currentIndex={currentIndex}
        totalFiles={totalFiles}
        onPrev={onPrev}
        onNext={onNext}
        onBack={onBack}
      />

      <div className="flex flex-1 gap-4 overflow-hidden mt-3">
        <div className="flex-1 flex flex-col bg-card border border-border rounded-md overflow-hidden">
          <OriginalPreview fileId={file.id} />
        </div>

        <div className="flex-1 flex flex-col bg-card border border-border rounded-md overflow-hidden">
          <ResultToolbar fileId={file.id} />
          {result && (
            <>
              <ResultMetadata metadata={result.metadata} />
              <ExtractedText text={result.text} />
            </>
          )}
        </div>
      </div>

      <TextCursor line={1} column={1} />
    </div>
  )
}
