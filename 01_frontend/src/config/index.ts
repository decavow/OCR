// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api/v1'

// Polling intervals (ms)
export const POLLING_INTERVAL = 3000
export const HEARTBEAT_INTERVAL = 30000

// File constraints
export const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
export const MAX_BATCH_SIZE = 20
export const MAX_TOTAL_BATCH_SIZE = 200 * 1024 * 1024 // 200MB total
export const ALLOWED_FILE_TYPES = ['image/jpeg', 'image/png', 'image/tiff', 'application/pdf']

// Output formats
export const OUTPUT_FORMATS = ['txt', 'json', 'md'] as const

// Retention options (hours)
export const RETENTION_OPTIONS = [1, 6, 12, 24, 168, 720] // 1h, 6h, 12h, 24h, 7d, 30d

// OCR method options
export const METHOD_OPTIONS = [
  { value: 'ocr_paddle_text', label: 'PaddleOCR Text', description: 'Extract raw text using PaddleOCR (GPU)' },
  { value: 'ocr_tesseract_text', label: 'Tesseract Text', description: 'Extract raw text using Tesseract (CPU)' },
  { value: 'structured_extract', label: 'Structured Extract (PaddleVL)', description: 'Layout analysis + structured data extraction' },
] as const

// Tier options
export const TIER_OPTIONS = [
  { value: 0, label: 'Basic (No SLA)', description: 'Local processing, no SLA guarantee' },
  { value: 1, label: 'Standard SLA 99.0%', description: 'Standard processing with 99.0% uptime' },
  { value: 2, label: 'Enhanced SLA 99.5%', description: 'Priority processing with 99.5% uptime' },
] as const

// Pricing per page (VND) - keyed by "method:tier"
export const PRICING: Record<string, number> = {
  'ocr_paddle_text:0': 1000,
  'ocr_paddle_text:1': 2500,
  'ocr_paddle_text:2': 4000,
  'ocr_tesseract_text:0': 800,
  'ocr_tesseract_text:1': 2000,
  'ocr_tesseract_text:2': 3500,
  'structured_extract:0': 3000,
  'structured_extract:1': 5000,
  'structured_extract:2': 8000,
}
