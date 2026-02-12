import { Batch } from '../../types'
import BatchCard from './BatchCard'

interface BatchListProps {
  batches: Batch[]
  onSelect: (batch: Batch) => void
}

export default function BatchList({ batches, onSelect }: BatchListProps) {
  return (
    <div className="flex flex-col gap-2">
      {batches.map((batch) => (
        <BatchCard key={batch.id} batch={batch} onClick={() => onSelect(batch)} />
      ))}
    </div>
  )
}
