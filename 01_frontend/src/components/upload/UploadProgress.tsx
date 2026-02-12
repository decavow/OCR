import { Progress } from '@/components/ui/progress'

interface UploadProgressProps {
  progress: number
  uploading: boolean
}

export default function UploadProgress({ progress, uploading }: UploadProgressProps) {
  if (!uploading) return null

  return (
    <div className="space-y-1">
      <Progress value={progress} className="h-2" />
      <p className="text-xs text-muted-foreground text-right">{progress}%</p>
    </div>
  )
}
