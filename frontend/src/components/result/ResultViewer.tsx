import OriginalPreview from './OriginalPreview'
import ExtractedText from './ExtractedText'
import ResultToolbar from './ResultToolbar'
import ResultMetadata from './ResultMetadata'
import FileNavigator from './FileNavigator'
import TextCursor from './TextCursor'
import { JobResult, FileInfo } from '../../types'

// Main split-panel component: Left = OriginalPreview, Right = ExtractedText
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
  // TODO: Implement split-panel layout
  return (
    <div className="result-viewer">
      <FileNavigator
        fileName={file.original_name}
        currentIndex={currentIndex}
        totalFiles={totalFiles}
        onPrev={onPrev}
        onNext={onNext}
        onBack={onBack}
      />

      <div className="split-panel">
        <div className="left-panel">
          <OriginalPreview fileId={file.id} />
        </div>

        <div className="right-panel">
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
