import { useId } from "react";

function ShowcaseGrid() {
  const raw = useId();
  const id = `showcase-grid-${raw.replace(/:/g, "")}`;
  return (
    <div className="absolute inset-0">
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(135deg, #eef4ff 0%, #d4e4fc 46%, #aecbf6 100%)",
        }}
      />
      <svg
        aria-hidden="true"
        className="absolute inset-0 h-full w-full text-[#3f78e0]/60"
      >
        <defs>
          <pattern
            height="52"
            id={id}
            patternUnits="userSpaceOnUse"
            width="52"
          >
            <path
              d="M 52 0 L 0 0 L 0 52"
              fill="none"
              stroke="currentColor"
              strokeDasharray="4 5"
              strokeWidth="1.25"
            />
          </pattern>
        </defs>
        <rect fill={`url(#${id})`} height="100%" width="100%" />
      </svg>
    </div>
  );
}

export { ShowcaseGrid };
