import { UploadConfig as Config } from '../../types'
import {
  OUTPUT_FORMATS,
  RETENTION_OPTIONS,
  METHOD_OPTIONS,
  TIER_OPTIONS,
  PRICING,
} from '../../config'

interface UploadConfigProps {
  config: Config
  onChange: (config: Config) => void
  fileCount: number
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

export default function UploadConfig({ config, onChange, fileCount }: UploadConfigProps) {
  const ratePerPage = getRatePerPage(config.method, config.tier)
  const estimatedPrice = fileCount * ratePerPage

  const currentMethod = METHOD_OPTIONS.find((m) => m.value === config.method)
  const currentTier = TIER_OPTIONS.find((t) => t.value === config.tier)

  return (
    <div className="upload-config-panel">
      {/* Configuration Section */}
      <div className="config-card">
        <h3 className="config-card-title">
          <span className="config-icon">&#9881;</span>
          Configuration
        </h3>

        <div className="config-group">
          <label htmlFor="ocr-method">OCR Service Engine</label>
          <select
            id="ocr-method"
            value={config.method}
            onChange={(e) => onChange({ ...config, method: e.target.value })}
          >
            {METHOD_OPTIONS.map((opt) => (
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
          >
            {TIER_OPTIONS.map((opt) => (
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
