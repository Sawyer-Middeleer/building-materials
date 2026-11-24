import { Component, type ReactNode } from "react";
import { PaperTexture } from "@paper-design/shaders-react";

class ShaderBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export function PaperGround() {
  return (
    <>
      <ShaderBoundary>
        <div className="paper-shader-bg" aria-hidden="true">
          <PaperTexture
            style={{ width: "100%", height: "100%" }}
            colorBack="#f5f2ea"
            colorFront="#ece7da"
            contrast={0.18}
            roughness={0.34}
            fiber={0.28}
            fiberSize={0.45}
            crumples={0}
            folds={0}
            drops={0}
            fade={0}
            seed={4}
            scale={1.1}
          />
        </div>
      </ShaderBoundary>
      <svg className="paper-grain-overlay" aria-hidden="true" width="100%" height="100%">
        <filter id="cotton-paper-tooth">
          <feTurbulence type="fractalNoise" baseFrequency="0.82" numOctaves="3" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#cotton-paper-tooth)" />
      </svg>
    </>
  );
}
