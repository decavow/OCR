import { UploadFile } from '../../types'
import FileItem from './FileItem'

// Selected files before upload
interface FileListProps {
  files: UploadFile[]
  onRemove: (id: string) => void
}

export default function FileList({ files, onRemove }: FileListProps) {
  // TODO: Render list of files
  return (
    <div className="file-list">
      {files.map((file) => (
        <FileItem key={file.id} file={file} onRemove={() => onRemove(file.id)} />
      ))}
    </div>
  )
}
