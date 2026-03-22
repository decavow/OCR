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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { Settings, DollarSign } from 'lucide-react'

interface UploadConfigProps {
  config: Config
  onChange: (config: Config) => void
  fileCount: number
  onServicesLoaded?: (available: boolean) => void
}

const RETENTION_LABELS: Record<number, string> = {
  1: '1 hour',
  6: '6 hours',
  12: '12 hours',
  24: '1 day (default)',
  168: '7 days',
  720: '30 days',
}

function getRatePerPage(method: string, tier: number): number {
  return PRICING[`${method}:${tier}`] ?? 0
}

function formatVND(amount: number): string {
  return amount.toLocaleString('vi-VN') + ' VND'
}

function getEngineName(services: AvailableService[]): string | null {
  for (const svc of services) {
    if (svc.engine_info?.name) return svc.engine_info.name
  }
  return null
}

function getEngineVersion(services: AvailableService[]): string | null {
  for (const svc of services) {
    if (svc.engine_info?.version) return svc.engine_info.version
  }
  return null
}

function buildOptions(services: AvailableService[]) {
  const methods = new Set<string>()
  const tiers = new Set<number>()
  for (const svc of services) {
    for (const m of svc.allowed_methods) methods.add(m)
    for (const t of svc.allowed_tiers) tiers.add(t)
  }
  return {
    methodOpts: METHOD_OPTIONS.filter((m) => methods.has(m.value)),
    tierOpts: TIER_OPTIONS.filter((t) => tiers.has(t.value)),
  }
}

const selectClass = cn(
  'flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm',
  'ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
  'disabled:cursor-not-allowed disabled:opacity-50'
)

export default function UploadConfig({ config, onChange, fileCount, onServicesLoaded }: UploadConfigProps) {
  const [services, setServices] = useState<AvailableService[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getAvailableServices()
      .then((res) => {
        setServices(res.items)
        onServicesLoaded?.(res.items.length > 0)

        // Auto-select first available method if current is not available
        if (res.items.length > 0) {
          const availableMethods = new Set<string>()
          const availableTiers = new Set<number>()
          for (const svc of res.items) {
            for (const m of svc.allowed_methods) availableMethods.add(m)
            for (const t of svc.allowed_tiers) availableTiers.add(t)
          }
          const updates: Partial<Config> = {}
          if (!availableMethods.has(config.method)) {
            updates.method = [...availableMethods][0]
          }
          if (!availableTiers.has(config.tier)) {
            updates.tier = [...availableTiers][0]
          }
          if (Object.keys(updates).length > 0) {
            onChange({ ...config, ...updates })
          }
        }
      })
      .catch(() => {
        setServices([])
        onServicesLoaded?.(false)
      })
      .finally(() => setLoading(false))
  }, [])

  const { methodOpts, tierOpts } = services.length > 0
    ? buildOptions(services)
    : { methodOpts: [], tierOpts: [] }

  const ratePerPage = getRatePerPage(config.method, config.tier)
  const estimatedPrice = fileCount * ratePerPage
  const currentMethod = methodOpts.find((m) => m.value === config.method)
  const currentTier = tierOpts.find((t) => t.value === config.tier)
  const engineName = getEngineName(services)
  const engineVersion = getEngineVersion(services)
  const noServices = !loading && services.length === 0

  return (
    <div className="flex flex-col gap-4">
      {/* Configuration */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Settings className="h-4 w-4" />
            Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {noServices && (
            <div className="text-sm text-warning bg-warning/10 border border-warning/30 rounded-md p-3">
              No OCR services are currently available. Please contact admin.
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="ocr-method">OCR Service Engine</Label>
            <select
              id="ocr-method"
              className={selectClass}
              value={config.method}
              onChange={(e) => onChange({ ...config, method: e.target.value })}
              disabled={loading || noServices}
            >
              {loading && <option>Loading...</option>}
              {noServices && <option value="">No services available</option>}
              {methodOpts.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            {currentMethod && (
              <p className="text-xs text-muted-foreground">{currentMethod.description}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="ocr-tier">Processing Tier</Label>
            <select
              id="ocr-tier"
              className={selectClass}
              value={config.tier}
              onChange={(e) => onChange({ ...config, tier: parseInt(e.target.value, 10) })}
              disabled={loading || noServices}
            >
              {loading && <option>Loading...</option>}
              {noServices && <option value="">No services available</option>}
              {tierOpts.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            {currentTier && (
              <p className="text-xs text-muted-foreground">{currentTier.description}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="output-format">Output Format</Label>
              <select
                id="output-format"
                className={selectClass}
                value={config.output_format}
                onChange={(e) => onChange({ ...config, output_format: e.target.value as 'txt' | 'json' | 'md' })}
              >
                {OUTPUT_FORMATS.map((format) => (
                  <option key={format} value={format}>{format.toUpperCase()}</option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="retention">Retention</Label>
              <select
                id="retention"
                className={selectClass}
                value={config.retention_hours}
                onChange={(e) => onChange({ ...config, retention_hours: parseInt(e.target.value, 10) })}
              >
                {RETENTION_OPTIONS.map((hours) => (
                  <option key={hours} value={hours}>{RETENTION_LABELS[hours] || `${hours} hours`}</option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Cost Estimation */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <DollarSign className="h-4 w-4" />
            Cost Estimation
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Total Files</span>
            <span className="text-foreground">{fileCount}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Rate per Page</span>
            <span className="text-foreground">{formatVND(ratePerPage)}</span>
          </div>
          <Separator />
          <div className="flex justify-between text-sm font-semibold">
            <span>Estimated Price</span>
            <span className="text-primary">{formatVND(estimatedPrice)}</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Pricing is estimated. Actual cost may vary based on page count per file.
          </p>
        </CardContent>
      </Card>

      {/* Active Model Badge */}
      <div className="flex items-center justify-between rounded-md bg-primary/10 border border-primary/20 px-4 py-3">
        <span className="text-xs text-muted-foreground">Active Model</span>
        <div className="flex items-center gap-2">
          {engineName && (
            <span className="inline-flex items-center rounded-full bg-accent text-accent-foreground px-2 py-0.5 text-xs font-medium">
              {engineName}{engineVersion ? ` v${engineVersion}` : ''}
            </span>
          )}
          <span className="text-sm font-medium text-primary">
            {currentMethod?.label ?? config.method} &middot; {currentTier?.label ?? `Tier ${config.tier}`}
          </span>
        </div>
      </div>
    </div>
  )
}
