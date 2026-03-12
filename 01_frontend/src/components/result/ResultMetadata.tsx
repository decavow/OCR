import { JobResultMetadata } from '../../types'

interface ResultMetadataProps {
  metadata: JobResultMetadata
}

export default function ResultMetadata({ metadata }: ResultMetadataProps) {
  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-border">
      {metadata.engine_name && (
        <span className="inline-flex items-center rounded-full bg-accent text-accent-foreground px-2 py-0.5 text-xs font-medium">
          {metadata.engine_name}
        </span>
      )}
      <span className="inline-flex items-center rounded-full bg-primary/20 text-primary px-2 py-0.5 text-xs font-medium">
        {metadata.method}
      </span>
      <span className="inline-flex items-center rounded-full bg-muted text-muted-foreground px-2 py-0.5 text-xs font-medium">
        Tier {metadata.tier}
      </span>
      <span className="inline-flex items-center rounded-full bg-muted text-muted-foreground px-2 py-0.5 text-xs font-medium">
        {metadata.processing_time_ms}ms
      </span>
      <span className="inline-flex items-center rounded-full bg-muted text-muted-foreground px-2 py-0.5 text-xs font-medium">
        v{metadata.service_version}
      </span>
    </div>
  )
}
