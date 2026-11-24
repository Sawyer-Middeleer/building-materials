interface LocatorDiagramProps {
  mode: "building" | "window";
  caption?: string;
}

export function LocatorDiagram({ mode, caption }: LocatorDiagramProps) {
  if (mode === "window") {
    return (
      <div className="locator-svg-wrap" title={caption}>
        <svg width="116" height="84" viewBox="0 0 116 84" fill="none" aria-label="Window section locator">
          {/* Minimalist axonometric window frame outline */}
          <path
            d="M20 12 L52 4 L52 62 L20 70 Z"
            stroke="#181715"
            strokeWidth="1.2"
            fill="#ebe6da"
          />
          <path
            d="M20 70 L52 62 L94 74 L62 82 Z"
            stroke="#181715"
            strokeWidth="1.2"
            fill="#f5f2ea"
          />
          <line x1="36" y1="16" x2="36" y2="66" stroke="#181715" strokeWidth="0.9" />
          <line x1="42" y1="14" x2="42" y2="64" stroke="#181715" strokeWidth="0.9" />
          <path d="M52 16 L88 26 L88 70 L52 60" stroke="#181715" strokeWidth="0.9" />
          {/* Vermilion locator circle on outer glass pane */}
          <circle cx="66" cy="36" r="10" stroke="#c93d24" strokeWidth="1.6" fill="rgba(201,61,36,0.10)" />
          <circle cx="66" cy="36" r="2.2" fill="#c93d24" />
        </svg>
      </div>
    );
  }

  return (
    <div className="locator-svg-wrap" title={caption}>
      <svg width="210" height="72" viewBox="0 0 210 72" fill="none" aria-label="Building envelope locator">
        {/* Ground line */}
        <line x1="2" y1="64" x2="208" y2="64" stroke="#181715" strokeWidth="1.2" />
        {/* Main two-story section silhouette */}
        <path
          d="M22 64 L22 14 L126 14 L126 38 L174 38 L174 64"
          stroke="#181715"
          strokeWidth="1.5"
          fill="#f7f4ed"
        />
        {/* Floor slab */}
        <rect x="22" y="38" width="104" height="4" fill="#181715" />
        {/* Roof slab */}
        <rect x="22" y="14" width="104" height="3.5" fill="#181715" />
        {/* Interior partitions & stair */}
        <line x1="68" y1="17" x2="68" y2="38" stroke="#181715" strokeWidth="1" />
        <line x1="94" y1="42" x2="94" y2="64" stroke="#181715" strokeWidth="1" />
        <path d="M98 46 H112 M98 50 H112 M98 54 H112 M98 58 H112" stroke="#78736a" strokeWidth="0.8" />
        {/* Window opening on upper-left envelope */}
        <rect x="20" y="21" width="5" height="11" fill="#f5f2ea" stroke="#c93d24" strokeWidth="1.2" />
        {/* Surgical vermilion locator dot */}
        <circle cx="22" cy="26.5" r="8.5" stroke="#c93d24" strokeWidth="1.3" fill="rgba(201,61,36,0.12)" />
        <circle cx="22" cy="26.5" r="2.8" fill="#c93d24" />
      </svg>
    </div>
  );
}
