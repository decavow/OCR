import { useState, useEffect } from 'react'
import { UploadConfig as Config } from '../../types'
import {
  OUTPUT_FORMATS,
  RETENTION_OPTIONS,
  METHOD_OPTIONS,
  TIER_OPTIONS,
  PRICING,
} from '../../config'
import { getAvailableServices, AvailableService } from '../../api/services'

interface UploadConfigProps {
  config: Config
  onChange: (config: Config) => void
  fileCount: number
  onServicesLoaded?: (available: boolean) => void
}

const RETENTION_LABELS: Record<number, string> = {
  24: '1 day',
  72: '3 days',
  168: '1 week',
  720: '30 days',
}

function getRatePerPage(method: string, tier: number): number {
  return PRICING[`${method}:${tier}`] ?? 0
}

function formatVND(amount: number): string {
  return amount.toLocaleString('vi-VN') + ' VND'
}

// Build method+tier options from available services
function buildOptions(services: AvailableService[]) {
  const methods = new Set<string>()
  const tiers = new Set<number>()

  for (const svc of services) {
    for (const m of svc.allowed_methods) methods.add(m)
    for (const t of svc.allowed_tiers) tiers.add(t)
  }

  const methodOpts = METHOD_OPTIONS.filter((m) => methods.has(m.value))
  const tierOpts = TIER_OPTIONS.filter((t) => tiers.has(t.value))

  return { methodOpts, tierOpts }
}

export default function UploadConfig({ config, onChange, fileCount, onServicesLoaded }: UploadConfigProps) {
  const [services, setServices] = useState<AvailableService[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAvailableServices()
      .then((res) => {
        setServices(res.items)
        onServicesLoaded?.(res.items.length > 0)
      })
      .catch(() => {
        setServices([])
        onServicesLoaded?.(false)
      })
      .finally(() => setLoading(false))
  }, [])

  // Dynamic options from API — only show approved services
  const { methodOpts, tierOpts } = services.length > 0
    ? buildOptions(services)
    : { methodOpts: [], tierOpts: [] }

  const ratePerPage = getRatePerPage(config.method, config.tier)
  const estimatedPrice = fileCount * ratePerPage

  const currentMethod = methodOpts.find((m) => m.value === config.method)
  const currentTier = tierOpts.find((t) => t.value === config.tier)

  const noServices = !loading && services.length === 0

  return (
    <div className="upload-config-panel">
      {/* Configuration Section */}
      <div className="config-card">
        <h3 className="config-card-title">
          <span className="config-icon">&#9881;</span>
          Configuration
        </h3>

        {noServices && (
          <div className="config-warning">
            No OCR services are currently available. Please contact admin.
          </div>
        )}

        <div className="config-group">
          <label htmlFor="ocr-method">OCR Service Engine</label>
          <select
            id="ocr-method"
            value={config.method}
            onChange={(e) => onChange({ ...config, method: e.target.value })}
            disabled={loading || noServices}
          >
            {loading && <option>Loading...</option>}
            {noServices && <option value="">No services available</option>}
            {methodOpts.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          {currentMethod && (
            <span className="config-hint">{currentMethod.description}</span>
          )}
        </div>

        <div className="config-group">
          <label htmlFor="ocr-tier">Processing Tier</label>
          <select
            id="ocr-tier"
            value={config.tier}
            onChange={(e) => onChange({ ...config, tier: parseInt(e.target.value, 10) })}
            disabled={loading || noServices}
          >
            {loading && <option>Loading...</option>}
            {noServices && <option value="">No services available</option>}
            {tierOpts.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          {currentTier && (
            <span className="config-hint">{currentTier.description}</span>
          )}
        </div>

        <div className="config-row">
          <div className="config-group">
            <label htmlFor="output-format">Output Format</label>
            <select
              id="output-format"
              value={config.output_format}
              onChange={(e) =>
                onChange({ ...config, output_format: e.target.value as 'txt' | 'json' })
              }
            >
              {OUTPUT_FORMATS.map((format) => (
                <option key={format} value={format}>
                  {format.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          <div className="config-group">
            <label htmlFor="retention">Retention</label>
            <select
              id="retention"
              value={config.retention_hours}
              onChange={(e) =>
                onChange({ ...config, retention_hours: parseInt(e.target.value, 10) })
              }
            >
              {RETENTION_OPTIONS.map((hours) => (
                <option key={hours} value={hours}>
                  {RETENTION_LABELS[hours] || `${hours} hours`}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Cost Estimation Section */}
      <div className="config-card">
        <h3 className="config-card-title">
          <span className="config-icon">&#128176;</span>
          Cost Estimation
        </h3>

        <div className="cost-breakdown">
          <div className="cost-row">
            <span className="cost-label">Total Files</span>
            <span className="cost-value">{fileCount}</span>
          </div>
          <div className="cost-row">
            <span className="cost-label">Rate per Page</span>
            <span className="cost-value">{formatVND(ratePerPage)}</span>
          </div>
          <div className="cost-divider"></div>
          <div className="cost-row cost-total">
            <span className="cost-label">Estimated Price</span>
            <span className="cost-value">{formatVND(estimatedPrice)}</span>
          </div>
        </div>

        <div className="cost-notice">
          Pricing is estimated. Actual cost may vary based on page count per file.
        </div>
      </div>

      {/* Active Model Badge */}
      <div className="active-model-badge">
        <span className="model-badge-label">Active Model</span>
        <span className="model-badge-value">
          {currentMethod?.label ?? config.method} &middot; {currentTier?.label ?? `Tier ${config.tier}`}
        </span>
      </div>
    </div>
  )
}
