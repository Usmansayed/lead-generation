export function DataTable({ columns, data, keyField = '_id', emptyMessage = 'No data' }) {
  return (
    <div className="rounded-xl border border-border overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40">
            {columns.map((col) => (
              <th
                key={col.id}
                className="h-11 px-4 text-left align-middle font-medium text-muted-foreground text-xs uppercase tracking-wider"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {!data || data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row) => (
              <tr
                key={row[keyField] ?? row.id ?? Math.random()}
                className="border-b border-border/80 transition-colors hover:bg-muted/30"
              >
                {columns.map((col) => (
                  <td key={col.id} className="px-4 py-3 align-middle">
                    {col.cell ? col.cell(row) : row[col.id]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
