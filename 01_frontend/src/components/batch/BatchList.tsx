import { Batch } from '../../types'
import BatchCard from './BatchCard'

// List/grid of batches on Batches page
interface BatchListProps {
  batches: Batch[]
  onSelect: (batch: Batch) => void
}

export default function BatchList({ batches, onSelect }: BatchListProps) {
  // TODO: Render batch list
  return (
    <div className="batch-list">
      {batches.map((batch) => (
        <BatchCard key={batch.id} batch={batch} onClick={() => onSelect(batch)} />
      ))}
    </div>
  )
}
