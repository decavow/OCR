import { Button as ShadcnButton } from '@/components/ui/button'

interface CancelButtonProps {
  batchId: string
  disabled?: boolean
  onCancel: () => void
}

export default function CancelButton({ batchId, disabled, onCancel }: CancelButtonProps) {
  return (
    <ShadcnButton
      variant="destructive"
      size="sm"
      disabled={disabled}
      onClick={onCancel}
      title={`Cancel batch ${batchId}`}
    >
      Cancel Batch
    </ShadcnButton>
  )
}
