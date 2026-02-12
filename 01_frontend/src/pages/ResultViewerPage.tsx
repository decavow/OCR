import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useKeyboard } from '../hooks/useKeyboard'
import { FileInfo, JobResult, Job } from '../types'
import { getBatch } from '../api/batches'
import { getJobResult } from '../api/jobs'
import { getFile, getOriginalUrl } from '../api/files'
import { Button as ShadcnButton } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, ArrowLeft, Copy } from 'lucide-react'
import Loading from '../components/common/Loading'
import ErrorMessage from '../components/common/ErrorMessage'

export default function ResultViewerPage() {
  const { batchId, fileId } = useParams<{ batchId: string; fileId: string }>()
  const navigate = useNavigate()

  const [file, setFile] = useState<FileInfo | null>(null)
  const [result, setResult] = useState<JobResult | null>(null)
  const [originalUrl, setOriginalUrl] = useState<string | null>(null)
  const [allJobs, setAllJobs] = useState<Job[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchBatch = async () => {
      if (!batchId) return
      try {
        const batch = await getBatch(batchId)
        const completedJobs = batch.jobs.filter((j) => j.status === 'COMPLETED')
        setAllJobs(completedJobs)
        const idx = completedJobs.findIndex((j) => j.file_id === fileId)
        if (idx !== -1) setCurrentIndex(idx)
      } catch {
        setError('Failed to load batch')
      }
    }
    fetchBatch()
  }, [batchId, fileId])

  useEffect(() => {
    const fetchFileAndResult = async () => {
      if (!fileId) return
      setLoading(true)
      try {
        const fileInfo = await getFile(fileId)
        setFile(fileInfo)
        const urlResponse = await getOriginalUrl(fileId)
        setOriginalUrl(urlResponse.url)
        const currentJob = allJobs.find((j) => j.file_id === fileId)
        if (currentJob) {
          const resultData = await getJobResult(currentJob.id)
          setResult(resultData)
        }
      } catch {
        setError('Failed to load result')
      } finally {
        setLoading(false)
      }
    }
    fetchFileAndResult()
  }, [fileId, allJobs])

  const goNext = useCallback(() => {
    if (currentIndex < allJobs.length - 1) {
      const nextJob = allJobs[currentIndex + 1]
      navigate(`/batches/${batchId}/files/${nextJob.file_id}`)
    }
  }, [currentIndex, allJobs, batchId, navigate])

  const goPrev = useCallback(() => {
    if (currentIndex > 0) {
      const prevJob = allJobs[currentIndex - 1]
      navigate(`/batches/${batchId}/files/${prevJob.file_id}`)
    }
  }, [currentIndex, allJobs, batchId, navigate])

  const hasNext = currentIndex < allJobs.length - 1
  const hasPrev = currentIndex > 0

  useKeyboard({
    onLeft: hasPrev ? goPrev : undefined,
    onRight: hasNext ? goNext : undefined,
  })

  const handleBack = () => navigate(`/batches/${batchId}`)

  const handleCopyText = () => {
    if (result?.text) navigator.clipboard.writeText(result.text)
  }

  if (loading) return <Loading text="Loading..." />
  if (error) return <ErrorMessage message={error} />
  if (!file || !result) return <ErrorMessage message="Result not found" />

  return (
    <div className="flex flex-col h-[calc(100vh-48px)] -m-6 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <ShadcnButton variant="ghost" size="sm" onClick={handleBack}>
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Batch
        </ShadcnButton>
        <h1 className="text-sm font-medium text-foreground">{file.original_name}</h1>
        <div className="flex items-center gap-2">
          <ShadcnButton variant="ghost" size="icon" className="h-8 w-8" onClick={goPrev} disabled={!hasPrev}>
            <ChevronLeft className="h-4 w-4" />
          </ShadcnButton>
          <span className="text-sm text-muted-foreground">
            {currentIndex + 1} / {allJobs.length}
          </span>
          <ShadcnButton variant="ghost" size="icon" className="h-8 w-8" onClick={goNext} disabled={!hasNext}>
            <ChevronRight className="h-4 w-4" />
          </ShadcnButton>
        </div>
      </div>

      {/* Split panel */}
      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* Original */}
        <div className="flex-1 flex flex-col bg-card border border-border rounded-md overflow-hidden">
          <div className="px-4 py-2 border-b border-border">
            <h3 className="text-sm font-medium text-foreground">Original</h3>
          </div>
          <div className="flex-1 flex items-center justify-center p-4 overflow-auto">
            {originalUrl && (
              <img src={originalUrl} alt={file.original_name} className="max-w-full max-h-full object-contain" />
            )}
          </div>
        </div>

        {/* Result */}
        <div className="flex-1 flex flex-col bg-card border border-border rounded-md overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-border">
            <h3 className="text-sm font-medium text-foreground">Extracted Text</h3>
            <ShadcnButton variant="ghost" size="sm" onClick={handleCopyText}>
              <Copy className="h-3 w-3 mr-1" />
              Copy
            </ShadcnButton>
          </div>
          <pre className="flex-1 p-4 text-sm font-mono leading-6 whitespace-pre-wrap text-foreground overflow-auto">
            {result.text}
          </pre>
          <div className="flex items-center gap-4 px-4 py-2 border-t border-border text-xs text-muted-foreground">
            <span>Lines: {result.lines}</span>
            <span>Time: {result.metadata.processing_time_ms}ms</span>
            <span>Method: {result.metadata.method}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
