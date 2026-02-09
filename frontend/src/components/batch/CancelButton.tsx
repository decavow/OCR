// Cancel batch (only if QUEUED jobs remain)

interface CancelButtonProps {
  batchId: string
  disabled?: boolean
  onCancel: () => void
}

export default function CancelButton({ batchId, disabled, onCancel }: CancelButtonProps) {
  return (
    <button
      className="cancel-button"
      disabled={disabled}
      onClick={onCancel}
      title={`Cancel batch ${batchId}`}
    >
      Cancel Batch
    </button>
  )
}
