import { UploadFile } from '../../types'
import FileItem from './FileItem'

interface FileListProps {
  files: UploadFile[]
  onRemove: (id: string) => void
}

export default function FileList({ files, onRemove }: FileListProps) {
  return (
    <div className="flex flex-col gap-2">
      {files.map((file) => (
        <FileItem key={file.id} file={file} onRemove={() => onRemove(file.id)} />
      ))}
    </div>
  )
}
