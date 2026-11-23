import type { PropRow } from "@/docs/types";

function PropsTable({ rows }: { rows: PropRow[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-border border-b text-left text-[11.5px] text-muted-foreground uppercase tracking-wide">
            <th className="px-4 py-2.5 font-medium">Prop</th>
            <th className="px-4 py-2.5 font-medium">Type</th>
            <th className="px-4 py-2.5 font-medium">Default</th>
            <th className="px-4 py-2.5 font-medium">Description</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              className="border-border border-b align-top last:border-b-0"
              key={row.name}
            >
              <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[12.5px] text-foreground">
                {row.name}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[12px] text-muted-foreground">
                {row.type}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[12px] text-muted-foreground">
                {row.defaultValue}
              </td>
              <td className="min-w-[200px] px-4 py-2.5 text-foreground/80 leading-relaxed">
                {row.description}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export { PropsTable };
