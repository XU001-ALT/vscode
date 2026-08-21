interface Props {
  columns: string[]
  rows: unknown[][]
}

export default function DataTable({ columns, rows }: Props) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          {columns.map(c => (
            <th key={c} title={c}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => (
              <td key={j} title={cell == null ? '' : String(cell)}>
                {cell == null ? '—' : typeof cell === 'object' ? JSON.stringify(cell) : String(cell)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
