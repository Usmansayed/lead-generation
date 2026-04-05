const variants = {
  default: 'border-transparent bg-primary text-primary-foreground',
  secondary: 'border-transparent bg-secondary text-secondary-foreground',
  outline: 'text-foreground border-border',
  success: 'border-transparent bg-emerald-500/20 text-emerald-400',
  warning: 'border-transparent bg-amber-500/20 text-amber-400',
  destructive: 'border-transparent bg-destructive/20 text-destructive',
}

export function Badge({ variant = 'default', className = '', ...props }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-medium ${variants[variant] || variants.default} ${className}`}
      {...props}
    />
  )
}
