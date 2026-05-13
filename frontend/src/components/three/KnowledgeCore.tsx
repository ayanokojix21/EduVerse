"use client";

/**
 * KnowledgeCore — cinematic Three.js scene (igloo.inc-style)
 *
 * Scene:
 *   - Deep black void with atmospheric fog
 *   - A glowing wireframe icosahedron ("Knowledge Core") at center
 *   - 3 orbital rings of thin document-shard quads at different radii
 *   - Infinite star-point field for depth
 *   - Blueprint grid on the ground plane
 *   - Monospace annotation overlays (HTML, not WebGL)
 *
 * Scroll:  camera flies from z=22 → z=4 (zooms into the Core)
 * Mouse:   entire scene tilts with smooth parallax
 */

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

// ── Tuning constants ──────────────────────────────────────────────────────────
const SHARD_RINGS   = [
  { count: 7,  radius: 5.5,  speed: 0.004,  tilt: 0.4,  size: [0.30, 0.45] },
  { count: 11, radius: 9.0,  speed: -0.0025, tilt: 1.1, size: [0.20, 0.30] },
  { count: 5,  radius: 13.5, speed: 0.0015, tilt: 0.7,  size: [0.45, 0.65] },
];
const STAR_COUNT    = 1800;
const CORE_COLOR    = 0x00f5a0;   // bright mint — the AI core
const FOG_COLOR     = 0x000000;
const CORE_SCALE    = 1.4;        // scale up the icosahedra
const CAM_Z_START   = 22;
const CAM_Z_END     = 5;

// ── Component ─────────────────────────────────────────────────────────────────
export function KnowledgeCore() {
  const mountRef = useRef<HTMLDivElement>(null);
  // Annotation text, updated via state so it re-renders outside canvas
  const [annot, setAnnot] = useState({ x: "0.000", y: "0.000", pulse: "1.00" });
  const scrollPct = useRef(0);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    // ── Renderer ──────────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.setClearColor(0x000000, 1);
    el.appendChild(renderer.domElement);

    // ── Scene ─────────────────────────────────────────────────────────────────
    const scene  = new THREE.Scene();
    scene.fog    = new THREE.FogExp2(FOG_COLOR, 0.022);

    // ── Camera ────────────────────────────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(60, el.clientWidth / el.clientHeight, 0.1, 200);
    camera.position.set(0, 1.5, CAM_Z_START);
    camera.lookAt(0, 0, 0);

    // ── Lighting ──────────────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0xffffff, 0.1));
    const pointA = new THREE.PointLight(0x00f5a0, 14, 40);
    pointA.position.set(0, 0, 0);
    scene.add(pointA);
    const pointB = new THREE.PointLight(0x7c3aed, 5, 50);
    pointB.position.set(-10, 8, -5);
    scene.add(pointB);

    // ── Root scene group (tilts with mouse) ───────────────────────────────────
    const root = new THREE.Group();
    scene.add(root);

    // ── Knowledge Core: layered icosahedra ────────────────────────────────────
    const coreGroup = new THREE.Group();
    root.add(coreGroup);

    // Outer wireframe
    const outerGeo  = new THREE.IcosahedronGeometry(2.4, 1);
    const outerMat  = new THREE.MeshBasicMaterial({
      color: CORE_COLOR, wireframe: true, transparent: true, opacity: 0.75,
    });
    const outerMesh = new THREE.Mesh(outerGeo, outerMat);
    coreGroup.add(outerMesh);

    // Inner solid (slightly transparent, glowing)
    const innerGeo  = new THREE.IcosahedronGeometry(1.6, 1);
    const innerMat  = new THREE.MeshBasicMaterial({
      color: 0x002d1e, transparent: true, opacity: 0.9,
    });
    coreGroup.add(new THREE.Mesh(innerGeo, innerMat));

    // Extra outer shell — adds depth
    const shellGeo = new THREE.IcosahedronGeometry(3.2, 0);
    const shellMat = new THREE.MeshBasicMaterial({ color: CORE_COLOR, wireframe: true, transparent: true, opacity: 0.12 });
    coreGroup.add(new THREE.Mesh(shellGeo, shellMat));

    // Core glow: additive sprite
    const spriteTex   = buildGlowTexture();
    const spriteMat   = new THREE.SpriteMaterial({ map: spriteTex, color: 0x00f5a0, transparent: true, opacity: 0.65, blending: THREE.AdditiveBlending, depthWrite: false });
    const glow        = new THREE.Sprite(spriteMat);
    glow.scale.set(22, 22, 1);
    coreGroup.add(glow);

    // ── Shard rings ───────────────────────────────────────────────────────────
    const ringGroups: THREE.Group[] = [];
    SHARD_RINGS.forEach((ring, ri) => {
      const group = new THREE.Group();
      group.rotation.x = ring.tilt;
      root.add(group);
      ringGroups.push(group);

      for (let i = 0; i < ring.count; i++) {
        const angle = (i / ring.count) * Math.PI * 2;
        const w     = ring.size[0] + Math.random() * (ring.size[1] - ring.size[0]);
        const h     = w * (0.6 + Math.random() * 0.8);
        const geo   = new THREE.PlaneGeometry(w, h);
        const bright = Math.random() > 0.5;
        const mat   = new THREE.MeshBasicMaterial({
          color:       bright ? 0x00f5a0 : 0x7c3aed,
          transparent: true,
          opacity:     0.08 + Math.random() * 0.18,
          side:        THREE.DoubleSide,
          wireframe:   Math.random() > 0.6,
        });
        const shard = new THREE.Mesh(geo, mat);
        shard.position.set(
          Math.cos(angle) * ring.radius,
          (Math.random() - 0.5) * 2.0,
          Math.sin(angle) * ring.radius,
        );
        shard.rotation.set(
          Math.random() * Math.PI,
          angle,
          Math.random() * Math.PI,
        );
        // Store ring index and angle for per-shard animation
        (shard as any)._angle  = angle;
        (shard as any)._radius = ring.radius;
        (shard as any)._speed  = ring.speed;
        (shard as any)._y      = shard.position.y;
        (shard as any)._phase  = Math.random() * Math.PI * 2;
        group.add(shard);
      }
    });

    // ── Blueprint grid ────────────────────────────────────────────────────────
    const gridHelper = new THREE.GridHelper(60, 30, 0x0a3a24, 0x0a1a14);
    gridHelper.position.y = -5;
    (gridHelper.material as THREE.Material).transparent = true;
    (gridHelper.material as THREE.Material).opacity = 0.4;
    root.add(gridHelper);

    // ── Star field ────────────────────────────────────────────────────────────
    const starVerts: number[] = [];
    for (let i = 0; i < STAR_COUNT; i++) {
      starVerts.push(
        (Math.random() - 0.5) * 160,
        (Math.random() - 0.5) * 160,
        (Math.random() - 0.5) * 160,
      );
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.Float32BufferAttribute(starVerts, 3));
    const starMat = new THREE.PointsMaterial({ color: 0x334155, size: 0.10, transparent: true, opacity: 0.7 });
    scene.add(new THREE.Points(starGeo, starMat));

    // ── Mouse & scroll state ──────────────────────────────────────────────────
    let targetTiltX  = 0;
    let targetTiltY  = 0;
    let currentTiltX = 0;
    let currentTiltY = 0;
    let targetCamZ   = CAM_Z_START;

    const onScroll = () => {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      const pct = maxScroll > 0 ? Math.min(window.scrollY / maxScroll, 1) : 0;
      scrollPct.current = pct;
      targetCamZ = CAM_Z_START - pct * (CAM_Z_START - CAM_Z_END);
    };

    const onMouse = (e: MouseEvent) => {
      const nx = (e.clientX / window.innerWidth  - 0.5) * 2;
      const ny = (e.clientY / window.innerHeight - 0.5) * 2;
      targetTiltY =  nx * 0.18;
      targetTiltX = -ny * 0.12;
    };

    const onResize = () => {
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };

    window.addEventListener("scroll",    onScroll,  { passive: true });
    window.addEventListener("mousemove", onMouse);
    window.addEventListener("resize",    onResize);

    // ── Animation loop ────────────────────────────────────────────────────────
    const clock = new THREE.Clock();
    let raf = 0;

    const animate = () => {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      // Core pulse — icosahedron breathes
      const pulse = 1 + Math.sin(t * 1.4) * 0.07;
      coreGroup.scale.setScalar(pulse);
      outerMesh.rotation.x += 0.003;
      outerMesh.rotation.y += 0.005;

      // Shard rings orbit
      ringGroups.forEach((group, gi) => {
        group.children.forEach((child) => {
          if (!(child instanceof THREE.Mesh)) return;
          const c = child as any;
          c._angle += c._speed;
          child.position.x = Math.cos(c._angle) * c._radius;
          child.position.z = Math.sin(c._angle) * c._radius;
          child.position.y = c._y + Math.sin(t * 0.6 + c._phase) * 0.3;
          child.rotation.y += 0.008;
        });
      });

      // Glow intensity pulse
      pointA.intensity = 6 + Math.sin(t * 1.8) * 2.5;

      // Mouse parallax (smooth)
      currentTiltX = THREE.MathUtils.lerp(currentTiltX, targetTiltX, 0.04);
      currentTiltY = THREE.MathUtils.lerp(currentTiltY, targetTiltY, 0.04);
      root.rotation.x = currentTiltX;
      root.rotation.y = currentTiltY;

      // Camera zoom on scroll
      camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetCamZ, 0.05);

      // Update annotation state every 10 frames
      if (Math.round(t * 60) % 10 === 0) {
        setAnnot({
          x:     (currentTiltX * 100).toFixed(3),
          y:     (currentTiltY * 100).toFixed(3),
          pulse: pulse.toFixed(4),
        });
      }

      renderer.render(scene, camera);
    };
    animate();

    // ── Cleanup ───────────────────────────────────────────────────────────────
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
    <>
      {/* Three.js canvas fills its parent */}
      <div
        ref={mountRef}
        aria-hidden="true"
        style={{ position: "absolute", inset: 0, zIndex: 0 }}
      />

      {/* Blueprint annotation overlays (HTML layer) */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute", inset: 0, zIndex: 2,
          pointerEvents: "none",
          fontFamily: "'Courier New', monospace",
          fontSize: 10,
          color: "rgba(0,245,160,0.22)",
          letterSpacing: "0.08em",
        }}
      >
        {/* Top-left crosshair label */}
        <div style={{ position: "absolute", top: 80, left: 28 }}>
          <div>// EduVerse Knowledge Core v1.0</div>
          <div style={{ marginTop: 4, color: "rgba(0,245,160,0.2)" }}>
            // tilt_x={annot.x}  tilt_y={annot.y}
          </div>
          <div style={{ marginTop: 2, color: "rgba(0,245,160,0.2)" }}>
            // core_pulse={annot.pulse}
          </div>
        </div>

        {/* Bottom-left */}
        <div style={{ position: "absolute", bottom: 28, left: 28 }}>
          <div style={{ color: "rgba(0,245,160,0.5)" }}>SCROLL TO DISCOVER ↓</div>
        </div>

        {/* Top-right corner annotation */}
        <div style={{ position: "absolute", top: 28, right: 28, textAlign: "right" }}>
          <div>////// Knowledge Core</div>
          <div style={{ marginTop: 4, color: "rgba(0,245,160,0.2)" }}>
            nodes=72  edges=∞
          </div>
        </div>

        {/* Center crosshair lines (SVG) */}
        <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
          {/* Thin crosshair */}
          <line x1="50%" y1="44%" x2="50%" y2="56%" stroke="rgba(0,245,160,0.12)" strokeWidth="1" />
          <line x1="44%" y1="50%" x2="56%" y2="50%" stroke="rgba(0,245,160,0.12)" strokeWidth="1" />
          {/* Corner brackets */}
          {[
            ["10%","8%","10%","13%","15%","8%"],
            ["90%","8%","90%","13%","85%","8%"],
            ["10%","92%","10%","87%","15%","92%"],
            ["90%","92%","90%","87%","85%","92%"],
          ].map(([x1,y1,x2,y2,x3,y3],i)=>(
            <g key={i}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(0,245,160,0.18)" strokeWidth="1"/>
              <line x1={x1} y1={y1} x2={x3} y2={y3} stroke="rgba(0,245,160,0.18)" strokeWidth="1"/>
            </g>
          ))}
        </svg>
      </div>
    </>
  );
}

// ── Glow sprite texture builder ───────────────────────────────────────────────
function buildGlowTexture(): THREE.Texture {
  const size   = 256;
  const canvas = document.createElement("canvas");
  canvas.width  = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const grad = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2);
  grad.addColorStop(0,   "rgba(0,245,160,0.9)");
  grad.addColorStop(0.3, "rgba(0,245,160,0.3)");
  grad.addColorStop(1,   "rgba(0,0,0,0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  return tex;
}
