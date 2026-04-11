interface EmptyStateProps {
  title: string
  description: string
  icon?: React.ReactNode
  action?: React.ReactNode
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16">
      {icon && <div className="text-muted-foreground">{icon}</div>}
      <div className="text-center">
        <h3 className="text-lg font-medium">{title}</h3>
        <p className="text-muted-foreground text-sm mt-1">{description}</p>
      </div>
      {action}
    </div>
  )
}
