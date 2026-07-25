// Exactly three lights, all native Three.js primitives (never drei's
// <SpotLight volumetric> or any cone/beam mesh) - lights only ever
// influence shading here, nothing about them is itself rendered.
export function Lighting() {
  return (
    <>
      {/* warm spotlight from above */}
      <spotLight
        position={[0, 4.2, 1]}
        target-position={[0, 0, 0]}
        angle={0.5}
        penumbra={0.6}
        distance={9}
        decay={2}
        intensity={18}
        color="#ffd9a0"
      />

      {/* cool rim light from behind, backlighting the focused cover's edges */}
      <pointLight position={[0, 0.4, -2.2]} intensity={4} color="#8ecbff" distance={7} decay={2} />

      {/* very soft ambient fill */}
      <ambientLight intensity={0.12} />
    </>
  );
}
