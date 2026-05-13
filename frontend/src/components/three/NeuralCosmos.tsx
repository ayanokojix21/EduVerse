"use client";

// ─────────────────────────────────────────────────────────────────────────────
// NeuralCosmos — Three.js knowledge graph background
//
// Scene: ~70 glowing nodes (green/yellow/dim) connected by faint edges.
// Scroll: camera flies forward through the node cloud.
// Mouse:  subtle parallax tilt of the entire scene.
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useRef } from "react";
import * as THREE from "three";

// ── Config ──────────────────────────────────────────────────────────────────

const NODE_COUNT       = 72;
const SPREAD           = 18;       // Volume radius
const CONNECT_DIST     = 5.5;      // Max distance to draw a line
const PARTICLE_COUNT   = 280;
const ROTATION_SPEED   = 0.00018; // rad/frame

const COLORS = {
  strong:      0x4ade80,  // green  — mastered topic
  learning:    0xfbbf24,  // yellow — in progress
  weak:        0x536471,  // dim    — unexplored
  line:        0x2f3336,
  particle:    0x71767b,
};

// ── Component ────────────────────────────────────────────────────────────────

export function NeuralCosmos() {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    // ── Renderer ──────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.setClearColor(0x000000, 0);
    el.appendChild(renderer.domElement);

    // ── Scene & Camera ────────────────────────────────────────────────────
    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(65, el.clientWidth / el.clientHeight, 0.1, 120);
    camera.position.set(0, 0, 18);

    // ── Build nodes ───────────────────────────────────────────────────────
    const positions: THREE.Vector3[] = [];
    const phases:    number[]         = [];
    const speeds:    number[]         = [];
    const nodeGroup = new THREE.Group();
    scene.add(nodeGroup);

    // Color distribution: 25% green, 35% yellow, 40% dim
    function pickColor(i: number) {
      const t = i / NODE_COUNT;
      if (t < 0.25) return COLORS.strong;
      if (t < 0.60) return COLORS.learning;
      return COLORS.weak;
    }

    for (let i = 0; i < NODE_COUNT; i++) {
      // Random position inside a sphere
      const theta = Math.random() * Math.PI * 2;
      const phi   = Math.acos(2 * Math.random() - 1);
      const r     = Math.cbrt(Math.random()) * SPREAD;

      const pos = new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta),
        r * Math.cos(phi)
      );
      positions.push(pos);
      phases.push(Math.random() * Math.PI * 2);
      speeds.push(0.3 + Math.random() * 0.5);

      const geo = new THREE.SphereGeometry(0.06 + Math.random() * 0.10, 8, 8);
      const mat = new THREE.MeshBasicMaterial({
        color:       pickColor(i),
        transparent: true,
        opacity:     0.55 + Math.random() * 0.35,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(pos);
      nodeGroup.add(mesh);
    }

    // ── Build edges ───────────────────────────────────────────────────────
    const lineVerts: number[] = [];
    for (let a = 0; a < NODE_COUNT; a++) {
      for (let b = a + 1; b < NODE_COUNT; b++) {
        if (positions[a].distanceTo(positions[b]) < CONNECT_DIST) {
          lineVerts.push(
            positions[a].x, positions[a].y, positions[a].z,
            positions[b].x, positions[b].y, positions[b].z
          );
        }
      }
    }

    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(lineVerts, 3)
    );
    const lineMat = new THREE.LineBasicMaterial({
      color:       COLORS.line,
      transparent: true,
      opacity:     0.45,
    });
    nodeGroup.add(new THREE.LineSegments(lineGeo, lineMat));

    // ── Build particle field ──────────────────────────────────────────────
    const pVerts: number[] = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      pVerts.push(
        (Math.random() - 0.5) * SPREAD * 2.5,
        (Math.random() - 0.5) * SPREAD * 2.5,
        (Math.random() - 0.5) * SPREAD * 2.5
      );
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.Float32BufferAttribute(pVerts, 3));
    const pMat = new THREE.PointsMaterial({
      color:       COLORS.particle,
      size:        0.07,
      transparent: true,
      opacity:     0.35,
    });
    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);

    // ── State ─────────────────────────────────────────────────────────────
    let scrollY     = 0;
    let mouseX      = 0;
    let mouseY      = 0;
    let targetCamY  = 0;
    let targetTiltX = 0;
    let targetTiltY = 0;
    let currentCamY = 0;

    const onScroll = () => {
      scrollY = window.scrollY;
      const maxScroll   = document.documentElement.scrollHeight - window.innerHeight;
      const progress    = maxScroll > 0 ? scrollY / maxScroll : 0;
      // Fly camera from z=18 → z=4 and y=0 → y=-6 as user scrolls
      targetCamY = -progress * 7;
    };

    const onMouse = (e: MouseEvent) => {
      mouseX     = (e.clientX / window.innerWidth  - 0.5) * 2;
      mouseY     = (e.clientY / window.innerHeight - 0.5) * 2;
      targetTiltY = mouseX * 0.06;
      targetTiltX = -mouseY * 0.04;
    };

    const onResize = () => {
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };

    window.addEventListener("scroll",  onScroll,  { passive: true });
    window.addEventListener("mousemove", onMouse);
    window.addEventListener("resize",  onResize);

    // ── Animation loop ────────────────────────────────────────────────────
    const clock = new THREE.Clock();
    let raf = 0;

    const animate = () => {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      // Slow global rotation
      nodeGroup.rotation.y += ROTATION_SPEED;
      nodeGroup.rotation.x  = Math.sin(t * 0.07) * 0.03;

      // Bob each node
      nodeGroup.children.forEach((child, i) => {
        if (child instanceof THREE.Mesh) {
          child.position.y = positions[i].y
            + Math.sin(t * speeds[i] + phases[i]) * 0.25;
        }
      });

      // Particles drift
      particles.rotation.y += 0.00008;
      particles.rotation.x += 0.00004;

      // Camera: smooth lerp to scroll-driven position
      currentCamY = THREE.MathUtils.lerp(currentCamY, targetCamY, 0.04);
      camera.position.y = currentCamY;

      // Mouse parallax tilt
      scene.rotation.y = THREE.MathUtils.lerp(scene.rotation.y, targetTiltY, 0.05);
      scene.rotation.x = THREE.MathUtils.lerp(scene.rotation.x, targetTiltX, 0.05);

      renderer.render(scene, camera);
    };
    animate();

    // ── Cleanup ───────────────────────────────────────────────────────────
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll",    onScroll);
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("resize",    onResize);
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div
      ref={mountRef}
      aria-hidden="true"
      style={{
        position:      "fixed",
        inset:         0,
        zIndex:        1,
        pointerEvents: "none",
        overflow:      "hidden",
      }}
    />
  );
}
