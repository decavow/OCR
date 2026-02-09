import { JobResultMetadata } from '../../types'

// Service, Tier, Processing Time, Version badges

interface ResultMetadataProps {
  metadata: JobResultMetadata
}

export default function ResultMetadata({ metadata }: ResultMetadataProps) {
  return (
    <div className="result-metadata">
      <span>SERVICE: {metadata.method}</span>
      <span>TIER: {metadata.tier}</span>
      <span>TIME: {metadata.processing_time_ms}ms</span>
      <span>VERSION: {metadata.version}</span>
    </div>
  )
}
