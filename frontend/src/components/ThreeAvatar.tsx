"use client";

import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Sphere, Torus, MeshDistortMaterial } from '@react-three/drei';
import * as THREE from 'three';

function Ring({ radius, tubeRadius, color, speed, tiltX = 0, tiltZ = 0, active }: {
  radius: number; tubeRadius: number; color: string; speed: number;
  tiltX?: number; tiltZ?: number; active: boolean;
}) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.y = state.clock.getElapsedTime() * speed;
    ref.current.rotation.x = tiltX + Math.sin(state.clock.getElapsedTime() * 0.4) * 0.08;
    ref.current.rotation.z = tiltZ;
  });
  return (
    <Torus ref={ref} args={[radius, tubeRadius, 16, 100]}>
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={active ? 1.2 : 0.5}
        transparent
        opacity={active ? 0.9 : 0.5}
        roughness={0.1}
        metalness={0.9}
      />
    </Torus>
  );
}

export default function ThreeAvatar({ active = false }: { active?: boolean }) {
  const coreRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (coreRef.current) {
      coreRef.current.rotation.x = state.clock.getElapsedTime() * 0.3;
      coreRef.current.rotation.y = state.clock.getElapsedTime() * 0.5;
      const pulse = active
        ? 1 + Math.sin(state.clock.getElapsedTime() * 4) * 0.08
        : 1 + Math.sin(state.clock.getElapsedTime() * 1.5) * 0.03;
      coreRef.current.scale.setScalar(pulse);
    }
  });

  return (
    <group>
      {/* Core sphere */}
      <Sphere ref={coreRef} args={[0.55, 64, 64]}>
        <MeshDistortMaterial
          color={active ? '#7c3aed' : '#2563eb'}
          emissive={active ? '#6d28d9' : '#1d4ed8'}
          emissiveIntensity={active ? 0.8 : 0.3}
          distort={active ? 0.55 : 0.25}
          speed={active ? 4 : 1.5}
          roughness={0.05}
          metalness={0.95}
        />
      </Sphere>

      {/* Orbit rings */}
      <Ring radius={0.95} tubeRadius={0.015} color="#60a5fa" speed={0.8}  tiltX={1.1} tiltZ={0.3}  active={active} />
      <Ring radius={1.15} tubeRadius={0.010} color="#a78bfa" speed={-0.5} tiltX={0.5} tiltZ={-0.8} active={active} />
      <Ring radius={1.35} tubeRadius={0.008} color="#34d399" speed={0.3}  tiltX={-0.3} tiltZ={0.6} active={active} />

      {/* Ambient glow (point light inside) */}
      <pointLight
        color={active ? '#8b5cf6' : '#3b82f6'}
        intensity={active ? 3 : 1.2}
        distance={4}
      />
    </group>
  );
}

