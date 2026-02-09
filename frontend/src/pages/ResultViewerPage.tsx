// Split-panel result viewer (from sample UI)

import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useKeyboard } from '../hooks/useKeyboard'
import { FileInfo, JobResult, Job } from '../types'
import { getBatch } from '../api/batches'
import { getJobResult } from '../api/jobs'
import { getFile, getOriginalUrl } from '../api/files'

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

  // Fetch batch to get all jobs
  useEffect(() => {
    const fetchBatch = async () => {
      if (!batchId) return
      try {
        const batch = await getBatch(batchId)
        const completedJobs = batch.jobs.filter((j) => j.status === 'COMPLETED')
        setAllJobs(completedJobs)

        // Find current file index
        const idx = completedJobs.findIndex((j) => j.file_id === fileId)
        if (idx !== -1) setCurrentIndex(idx)
      } catch {
        setError('Failed to load batch')
      }
    }
    fetchBatch()
  }, [batchId, fileId])

  // Fetch current file and result
  useEffect(() => {
    const fetchFileAndResult = async () => {
      if (!fileId) return
      setLoading(true)
      try {
        // Fetch file info
        const fileInfo = await getFile(fileId)
        setFile(fileInfo)

        // Get original file URL for preview
        const urlResponse = await getOriginalUrl(fileId)
        setOriginalUrl(urlResponse.url)

        // Find job for this file
        const currentJob = allJobs.find((j) => j.file_id === fileId)
        if (currentJob) {
          // Fetch result
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

  // Keyboard navigation
  useKeyboard({
    onLeft: hasPrev ? goPrev : undefined,
    onRight: hasNext ? goNext : undefined,
  })

  const handleBack = () => {
    navigate(`/batches/${batchId}`)
  }

  const handleCopyText = () => {
    if (result?.text) {
      navigator.clipboard.writeText(result.text)
    }
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error) return <div className="error-message">{error}</div>
  if (!file || !result) return <div className="error-message">Result not found</div>

  return (
    <div className="result-viewer-page">
      <div className="viewer-header">
        <button className="back-btn" onClick={handleBack}>
          Back to Batch
        </button>
        <h1>{file.original_name}</h1>
        <div className="navigation">
          <button onClick={goPrev} disabled={!hasPrev}>
            Prev
          </button>
          <span>
            {currentIndex + 1} / {allJobs.length}
          </span>
          <button onClick={goNext} disabled={!hasNext}>
            Next
          </button>
        </div>
      </div>

      <div className="viewer-content">
        <div className="original-panel">
          <h3>Original</h3>
          <div className="panel-content">
            {originalUrl && (
              <img
                src={originalUrl}
                alt={file.original_name}
                className="original-image"
              />
            )}
          </div>
        </div>

        <div className="result-panel">
          <div className="result-header">
            <h3>Extracted Text</h3>
            <button onClick={handleCopyText}>Copy</button>
          </div>
          <pre className="result-text">{result.text}</pre>
          <div className="result-meta">
            <span>Lines: {result.lines}</span>
            <span>Time: {result.metadata.processing_time_ms}ms</span>
            <span>Method: {result.metadata.method}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
