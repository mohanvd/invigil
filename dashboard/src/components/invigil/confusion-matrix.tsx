import type { ConfusionMatrix as Matrix } from "@/data/types"

interface ConfusionMatrixProps<L extends string> {
  matrix: Matrix<L>
  caption: string
}

/**
 * One hue, from paper-sunken (zero) to navy (the largest count), with the
 * count printed in every cell. Rows are the true label, columns the prediction.
 */
export function ConfusionMatrix<L extends string>({ matrix, caption }: ConfusionMatrixProps<L>) {
  const max = Math.max(1, ...matrix.counts.flat())

  return (
    <figure className="flex flex-col gap-3">
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0.5 text-[13px]">
          <thead>
            <tr>
              <th className="w-24 p-0 pb-1 text-left align-bottom label-caps text-muted-foreground">Actual</th>
              {matrix.labels.map((label) => (
                <th key={label} scope="col" className="p-0 pb-1 text-center label-caps text-muted-foreground">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.labels.map((actual, i) => (
              <tr key={actual}>
                <th scope="row" className="pr-2 text-left label-caps font-medium">
                  {actual}
                </th>
                {matrix.counts[i].map((count, j) => {
                  const share = count / max
                  return (
                    <td
                      key={matrix.labels[j]}
                      className="h-11 min-w-14 rounded-sm text-center data"
                      style={{
                        backgroundColor: `color-mix(in oklab, var(--navy) ${Math.round(share * 100)}%, var(--paper-sunken))`,
                        color: share > 0.5 ? "var(--on-navy)" : "var(--foreground)",
                      }}
                      title={`Actual ${actual}, predicted ${matrix.labels[j]}: ${count}`}
                    >
                      {count}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figcaption className="text-[13px] text-muted-foreground">{caption}</figcaption>
    </figure>
  )
}
