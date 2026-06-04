"use client";

import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function Particles({ count = 200, active = false }: { count?: number; active?: boolean }) {
  const mesh = useRef<THREE.Points>(null);

  const [positions, speeds] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const spd = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      pos[i * 3]     = (Math.random() - 0.5) * 20;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 20;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 8;
      spd[i] = 0.002 + Math.random() * 0.006;
    }
    return [pos, spd];
  }, [count]);

  useFrame(() => {
    if (!mesh.current) return;
    const pos = mesh.current.geometry.attributes.position.array as Float32Array;
    for (let i = 0; i < count; i++) {
      pos[i * 3 + 1] += speeds[i] * (active ? 2.5 : 1);
      if (pos[i * 3 + 1] > 10) pos[i * 3 + 1] = -10;
    }
    mesh.current.geometry.attributes.position.needsUpdate = true;
    mesh.current.rotation.y += 0.0005;
  });

  return (
    <points ref={mesh}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.04}
        color={active ? '#a78bfa' : '#3b82f6'}
        transparent
        opacity={active ? 0.8 : 0.4}
        sizeAttenuation
      />
    </points>
  );
}

export default function ParticleField({ active = false }: { active?: boolean }) {
  return (
    <Canvas
      camera={{ position: [0, 0, 10], fov: 60 }}
      style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }}
      gl={{ alpha: true, antialias: false }}
    >
      <Particles count={300} active={active} />
    </Canvas>
  );
}
