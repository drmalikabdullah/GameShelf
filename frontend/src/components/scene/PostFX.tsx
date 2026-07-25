import { EffectComposer, DepthOfField } from '@react-three/postprocessing';

// A very subtle depth blur (~1px on the immediately-adjacent covers) so
// only the focused cover reads perfectly sharp - much lighter than the
// bloom/vignette/DoF stack that crashed the GPU earlier, since the scene
// itself is now just flat planes and three basic lights.
export function PostFX() {
  return (
    <EffectComposer multisampling={0}>
      <DepthOfField focusDistance={0.017} focalLength={0.01} bokehScale={1.4} height={480} />
    </EffectComposer>
  );
}
