import { useState, useCallback } from 'react'
import { FileInfo } from '../types'

// Navigate between files in a batch (prev/next)
export function useBatchNavigation(files: FileInfo[]) {
  const [currentIndex, setCurrentIndex] = useState(0)

  const currentFile = files[currentIndex] || null
  const hasNext = currentIndex < files.length - 1
  const hasPrev = currentIndex > 0

  const goNext = useCallback(() => {
    if (hasNext) setCurrentIndex((i) => i + 1)
  }, [hasNext])

  const goPrev = useCallback(() => {
    if (hasPrev) setCurrentIndex((i) => i - 1)
  }, [hasPrev])

  const goTo = useCallback((index: number) => {
    if (index >= 0 && index < files.length) {
      setCurrentIndex(index)
    }
  }, [files.length])

  return {
    currentFile,
    currentIndex,
    total: files.length,
    hasNext,
    hasPrev,
    goNext,
    goPrev,
    goTo,
  }
}
