interface TintControlProps {
  onChange: (value: number) => void;
  value: number;
}

function TintControl({ value, onChange }: TintControlProps) {
  const pct = Math.round(value * 100);
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="font-medium text-[13.5px] text-foreground">
        Liquid Glass tint
      </div>
      <div className="mt-3 flex items-center gap-3">
        <span className="text-[12px] text-muted-foreground">Clear</span>
        <input
          aria-label="Tint for the demos on this page"
          className="docs-range flex-1"
          max={1}
          min={0}
          onChange={(e) => onChange(Number(e.target.value))}
          step={0.01}
          style={{
            background: `linear-gradient(to right, #a8a2f5 0 ${pct}%, color-mix(in srgb, var(--muted-foreground) 25%, transparent) ${pct}% 100%)`,
          }}
          type="range"
          value={value}
        />
        <span className="text-[12px] text-muted-foreground">Tinted</span>
        <span className="w-10 text-right font-mono text-[12.5px] text-foreground/85 tabular-nums">
          {value.toFixed(2)}
        </span>
      </div>
    </div>
  );
}

export { TintControl };
