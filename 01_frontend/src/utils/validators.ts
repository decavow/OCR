// Client-side file validation

import { MAX_FILE_SIZE, MAX_BATCH_SIZE, MAX_TOTAL_BATCH_SIZE, ALLOWED_FILE_TYPES } from '../config'

export interface ValidationError {
  file: File
  error: string
}

export function validateFile(file: File): string | null {
  // Check file type
  if (!ALLOWED_FILE_TYPES.includes(file.type)) {
    return `File type ${file.type} is not supported`
  }

  // Check file size
  if (file.size > MAX_FILE_SIZE) {
    return `File size exceeds ${MAX_FILE_SIZE / 1024 / 1024}MB limit`
  }

  return null
}

export function validateBatch(files: File[]): ValidationError[] {
  const errors: ValidationError[] = []

  // Check batch size
  if (files.length > MAX_BATCH_SIZE) {
    // Return error for excess files
    files.slice(MAX_BATCH_SIZE).forEach((file) => {
      errors.push({ file, error: `Batch limit is ${MAX_BATCH_SIZE} files` })
    })
  }

  // Check total batch size
  const totalSize = files.reduce((sum, f) => sum + f.size, 0)
  if (totalSize > MAX_TOTAL_BATCH_SIZE) {
    errors.push({
      file: files[0],
      error: `Total batch size ${Math.round(totalSize / 1024 / 1024)}MB exceeds ${MAX_TOTAL_BATCH_SIZE / 1024 / 1024}MB limit`,
    })
    return errors
  }

  // Validate each file
  files.slice(0, MAX_BATCH_SIZE).forEach((file) => {
    const error = validateFile(file)
    if (error) {
      errors.push({ file, error })
    }
  })

  return errors
}
