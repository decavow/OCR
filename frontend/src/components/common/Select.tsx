import { SelectHTMLAttributes } from 'react'

// For output format selection
interface SelectOption {
  value: string
  label: string
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  options: SelectOption[]
}

export default function Select({ label, options, ...props }: SelectProps) {
  return (
    <div className="select-wrapper">
      {label && <label>{label}</label>}
      <select {...props}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
