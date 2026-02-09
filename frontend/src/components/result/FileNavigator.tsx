// Breadcrumb: "← Back to Batch #1024"
// File name + Processed badge
// "< File 3 of 15 >" prev/next arrows

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
    <div className="file-navigator">
      <button onClick={onBack}>← Back to Batch</button>
      <span className="file-name">{fileName}</span>
      <div className="nav-arrows">
        <button onClick={onPrev} disabled={currentIndex === 0}>
          &lt;
        </button>
        <span>
          File {currentIndex + 1} of {totalFiles}
        </span>
        <button onClick={onNext} disabled={currentIndex === totalFiles - 1}>
          &gt;
        </button>
      </div>
    </div>
  )
}
