"use client";
import { useEffect, useRef } from "react";
import * as THREE from "three";

const CYAN = 0x00d4ff, PURPLE = 0x8b5cf6, BG = 0x030712;

// ── Custom Catmull-Rom sampler (avoids Three.js 0.184 CatmullRomCurve3 bug) ──
const WPT = [
  new THREE.Vector3(0,   2,  58),  // 0 – hero start
  new THREE.Vector3(0,   2,  38),  // 1 – approaching books
  new THREE.Vector3(0,   4,  16),  // 2 – books tower overhead
  new THREE.Vector3(0,   2,   4),  // 3 – entering spine
  new THREE.Vector3(0,   0,  -7),  // 4 – inside, corridor opens
  new THREE.Vector3(-3,  1.5,-17), // 5 – library left
  new THREE.Vector3( 4, -1, -27),  // 6 – library right
  new THREE.Vector3(-2,  0.5,-37), // 7 – library deeper
  new THREE.Vector3(0,  -1, -46),  // 8 – approaching hub
  new THREE.Vector3(0,  -5, -57),  // 9 – hub terminal
];

function crInterp(p0: THREE.Vector3, p1: THREE.Vector3, p2: THREE.Vector3, p3: THREE.Vector3, t: number): THREE.Vector3 {
  const t2 = t * t, t3 = t2 * t;
  return new THREE.Vector3(
    0.5 * ((2*p1.x) + (-p0.x+p2.x)*t + (2*p0.x-5*p1.x+4*p2.x-p3.x)*t2 + (-p0.x+3*p1.x-3*p2.x+p3.x)*t3),
    0.5 * ((2*p1.y) + (-p0.y+p2.y)*t + (2*p0.y-5*p1.y+4*p2.y-p3.y)*t2 + (-p0.y+3*p1.y-3*p2.y+p3.y)*t3),
    0.5 * ((2*p1.z) + (-p0.z+p2.z)*t + (2*p0.z-5*p1.z+4*p2.z-p3.z)*t2 + (-p0.z+3*p1.z-3*p2.z+p3.z)*t3),
  );
}

function samplePath(t: number): THREE.Vector3 {
  const safe = Math.max(0, Math.min(t, 0.9999));
  const n = WPT.length - 1;
  const ft = safe * n;
  const i = Math.floor(ft);
  const f = ft - i;
  return crInterp(WPT[Math.max(i-1,0)], WPT[i], WPT[Math.min(i+1,n)], WPT[Math.min(i+2,n)], f);
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function makeGlowTex(r: number, g: number, b: number) {
  const cv = document.createElement("canvas"); cv.width = cv.height = 256;
  const ctx = cv.getContext("2d")!;
  const gr = ctx.createRadialGradient(128,128,0,128,128,128);
  gr.addColorStop(0,   `rgba(${r},${g},${b},1)`);
  gr.addColorStop(0.35,`rgba(${r},${g},${b},0.3)`);
  gr.addColorStop(1,   "rgba(0,0,0,0)");
  ctx.fillStyle = gr; ctx.fillRect(0,0,256,256);
  return new THREE.CanvasTexture(cv);
}

function addGlow(parent: THREE.Object3D, r: number, g: number, b: number, op: number, sc: number) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({
    map: makeGlowTex(r,g,b), transparent: true, opacity: op,
    blending: THREE.AdditiveBlending, depthWrite: false,
  }));
  s.scale.set(sc, sc, 1); parent.add(s); return s;
}

function makeBook(w: number, h: number, d: number, col: number, x: number, z: number, ry = 0) {
  const g = new THREE.Group();
  // Main body
  g.add(new THREE.Mesh(new THREE.BoxGeometry(w, h, d),
    new THREE.MeshPhongMaterial({ color: 0x010820, shininess: 100, specular: col, emissive: 0x000510 })));
  // Edge wireframe glow
  g.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, d)),
    new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.95 })));
  // Spine strip (bright)
  const sp = new THREE.Mesh(new THREE.PlaneGeometry(0.15, h * .9),
    new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: .35, side: THREE.DoubleSide }));
  sp.position.set(-w/2+0.01, 0, 0); sp.rotation.y = Math.PI/2; g.add(sp);
  // Page lines on cover face
  for (let j = 0; j < 5; j++) {
    const ly = -h*0.35 + j*(h*0.175);
    const ln = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-w*0.35, ly, d/2+0.01), new THREE.Vector3(w*0.35, ly, d/2+0.01)
    ]);
    g.add(new THREE.Line(ln, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.12 })));
  }
  // Glow halo
  const [r, gv, b] = [(col>>16)&255,(col>>8)&255,col&255];
  addGlow(g, r, gv, b, 0.35, Math.max(w*2.5, h*0.6));
  g.position.set(x, 0, z); g.rotation.y = ry; return g;
}

function makePanel(w: number, h: number, col: number) {
  const g = new THREE.Group();
  // Glass fill
  g.add(new THREE.Mesh(new THREE.PlaneGeometry(w, h),
    new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: .04, side: THREE.DoubleSide })));
  // Border
  g.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(w, h)),
    new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: .85 })));
  // Corner brackets
  const bracketPts = (bw: number, bh: number, sx: number, sy: number) => [
    new THREE.Vector3(sx*bw, sy*(bh-0.3), 0), new THREE.Vector3(sx*bw, sy*bh, 0), new THREE.Vector3(sx*(bw-0.3), sy*bh, 0)
  ];
  [[w/2,h/2,1,1],[w/2,h/2,-1,1],[w/2,h/2,1,-1],[w/2,h/2,-1,-1]].forEach(([bw,bh,sx,sy]) => {
    const bg = new THREE.BufferGeometry().setFromPoints(bracketPts(bw as number, bh as number, sx as number, sy as number));
    g.add(new THREE.Line(bg, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: .9 })));
  });
  // Data lines
  for (let i = 1; i < 5; i++) {
    const ln = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-w/2+0.4, -h/2+(h/5)*i, 0),
      new THREE.Vector3(w/2-0.4,  -h/2+(h/5)*i, 0),
    ]);
    g.add(new THREE.Line(ln, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.15 })));
  }
  return g;
}

export function CampusJourney() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current; if (!el) return;

    // ── Renderer ─────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.setClearColor(BG, 1);
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(BG);
    scene.fog = new THREE.FogExp2(BG, 0.010);

    const camera = new THREE.PerspectiveCamera(72, el.clientWidth/el.clientHeight, 0.1, 300);
    const camPos = WPT[0].clone();
    camera.position.copy(camPos);

    // ── Lighting ──────────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0x0a1628, 3));
    const lA = new THREE.PointLight(CYAN,   30, 55); lA.position.set(0,   5,  5);   scene.add(lA);
    const lB = new THREE.PointLight(PURPLE, 20, 60); lB.position.set(-10, 4, -22);  scene.add(lB);
    const lC = new THREE.PointLight(CYAN,   25, 50); lC.position.set( 5,  2, -52);  scene.add(lC);
    const lD = new THREE.PointLight(PURPLE, 15, 40); lD.position.set( 0, -5, -57);  scene.add(lD);

    // ── HERO: Giant book skyscrapers ──────────────────────────────────────
    const BOOKS = [
      makeBook(4,   30, .9, CYAN,    0,   0,    0   ),
      makeBook(3,   22, .8, PURPLE, -7,  -1,    .08 ),
      makeBook(5,   36, 1,  CYAN,    9,  -3,   -.10 ),
      makeBook(2.5, 18, .7, PURPLE,-14,  -2,    .18 ),
      makeBook(3.5, 26, .9, CYAN,   16,  -4,   -.18 ),
      makeBook(4.5, 32, 1,  PURPLE,-21,  -2,    .22 ),
      makeBook(3,   20, .7, CYAN,   23,  -5,   -.25 ),
      makeBook(2,   16, .6, PURPLE, 28,  -6,   -.30 ),
    ];
    BOOKS.forEach(b => scene.add(b));

    // Floating book debris around hero (small books)
    for (let i = 0; i < 12; i++) {
      const mini = makeBook(
        0.4+Math.random()*0.5, 1.2+Math.random()*1.5, 0.1,
        Math.random() > 0.5 ? CYAN : PURPLE,
        (Math.random()-0.5)*30, 10+Math.random()*20, Math.random()*Math.PI
      );
      scene.add(mini);
    }

    // ── LIBRARY INTERIOR ─────────────────────────────────────────────────
    // Floor grid
    const grid = new THREE.GridHelper(60, 48, 0x0a2040, 0x050e1e);
    grid.position.set(0, -9, -25);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.55;
    scene.add(grid);

    // Ceiling
    const ceil = new THREE.GridHelper(60, 48, 0x0a1830, 0x040d18);
    ceil.position.set(0, 9, -25);
    (ceil.material as THREE.Material).transparent = true;
    (ceil.material as THREE.Material).opacity = 0.22;
    scene.add(ceil);

    // Pillars with glow rings
    [-9, 9].forEach(x => {
      for (let zi = 0; zi < 6; zi++) {
        const z = -10 - zi * 7;
        const p = new THREE.Group(); p.position.set(x, 0, z);
        p.add(new THREE.Mesh(new THREE.CylinderGeometry(.07,.07,18,10),
          new THREE.MeshPhongMaterial({color:0x010820,specular:CYAN,shininess:120})));
        p.add(new THREE.Mesh(new THREE.CylinderGeometry(.075,.075,18,10),
          new THREE.MeshBasicMaterial({color:CYAN,wireframe:true,transparent:true,opacity:.35})));
        // Glowing ring around pillar mid-point
        p.add(new THREE.Mesh(new THREE.TorusGeometry(.25,.02,6,32),
          new THREE.MeshBasicMaterial({color: zi%2===0 ? CYAN : PURPLE, transparent:true, opacity:.8})));
        scene.add(p);
      }
    });

    // Holographic panels (architectural blueprints)
    const PANELS = [
      { w:5.5, h:3.2, col:CYAN,   x:-5.5, y:1.8,  z:-15, ry: .35 },
      { w:4.5, h:2.8, col:PURPLE, x: 6,   y:0.5,  z:-22, ry:-.30 },
      { w:5,   h:3,   col:CYAN,   x:-5,   y:-0.8, z:-30, ry: .28 },
      { w:5.5, h:3.2, col:PURPLE, x: 6.5, y:1.2,  z:-38, ry:-.35 },
      { w:4,   h:2.5, col:CYAN,   x:-5,   y:0.5,  z:-45, ry: .20 },
    ];
    PANELS.forEach(p => {
      const pg = makePanel(p.w, p.h, p.col);
      pg.position.set(p.x, p.y, p.z); pg.rotation.y = p.ry;
      // Glow behind panel
      const [r,g,b] = p.col===CYAN ? [0,212,255] : [139,92,246];
      addGlow(pg, r, g, b, 0.15, p.w*2.5);
      scene.add(pg);
    });

    // Light beams along corridor
    for (let i = 0; i < 6; i++) {
      const beam = new THREE.Mesh(new THREE.CylinderGeometry(.015,.015,18,6),
        new THREE.MeshBasicMaterial({color: i%2===0 ? CYAN : PURPLE, transparent:true, opacity:.14}));
      beam.position.set((i%2===0 ? -1:1)*3.5, 0, -11 - i*6);
      scene.add(beam);
    }

    // Flying data particles (library cloud)
    const pv: number[] = [];
    for (let i=0;i<900;i++)
      pv.push((Math.random()-.5)*24, (Math.random()-.5)*16, -8 - Math.random()*48);
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.Float32BufferAttribute(pv,3));
    const particles = scene.add(new THREE.Points(pGeo, new THREE.PointsMaterial({
      color:0x00d4ff, size:.045, transparent:true, opacity:.55,
    }))) as unknown as THREE.Points;

    // Speed-rush particles (for fly-through feel)
    const rv: number[] = [];
    for (let i=0;i<200;i++)
      rv.push((Math.random()-.5)*6, (Math.random()-.5)*4, -5 - Math.random()*55);
    const rushGeo = new THREE.BufferGeometry();
    rushGeo.setAttribute("position", new THREE.Float32BufferAttribute(rv,3));
    const rush = new THREE.Points(rushGeo, new THREE.PointsMaterial({
      color:0xffffff, size:.04, transparent:true, opacity:.3,
    }));
    scene.add(rush);

    // ── HUB ─────────────────────────────────────────────────────────────
    const hub = new THREE.Group(); hub.position.set(0,-9,-55);
    // Platform
    hub.add(new THREE.Mesh(new THREE.CylinderGeometry(14,14,.2,64),
      new THREE.MeshPhongMaterial({color:0x010820,specular:CYAN,shininess:140,emissive:0x001018})));
    // Outer ring
    hub.add(new THREE.Mesh(new THREE.TorusGeometry(14,.06,8,128),
      new THREE.MeshBasicMaterial({color:CYAN,transparent:true,opacity:.9})));
    // Mid ring
    hub.add(new THREE.Mesh(new THREE.TorusGeometry(9,.04,8,100),
      new THREE.MeshBasicMaterial({color:PURPLE,transparent:true,opacity:.7})));
    // Inner ring
    hub.add(new THREE.Mesh(new THREE.TorusGeometry(5,.03,8,80),
      new THREE.MeshBasicMaterial({color:CYAN,transparent:true,opacity:.5})));
    // Radial spokes
    for (let i=0;i<8;i++) {
      const spoke = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0,0.15,0), new THREE.Vector3(Math.cos(i*Math.PI/4)*14, 0.15, Math.sin(i*Math.PI/4)*14)
      ]);
      hub.add(new THREE.Line(spoke, new THREE.LineBasicMaterial({color:CYAN,transparent:true,opacity:.2})));
    }
    // Central core
    const core = new THREE.Mesh(new THREE.IcosahedronGeometry(1.4,2),
      new THREE.MeshPhongMaterial({color:0x010820,specular:CYAN,shininess:200,emissive:0x001a2a}));
    core.position.y = 3; hub.add(core);
    addGlow(hub, 0,212,255, 0.6, 28);
    scene.add(hub);

    // CTA terminal frame
    const term = makePanel(8, 4.5, CYAN);
    term.position.set(0,-4.5,-60);
    addGlow(term, 0,212,255, 0.18, 12);
    scene.add(term);

    // ── State ─────────────────────────────────────────────────────────────
    let tTarget = 0, tCurrent = 0;
    let mXTarget = 0, mYTarget = 0, mX = 0, mY = 0;

    const onScroll = () => {
      const max = document.documentElement.scrollHeight - innerHeight;
      tTarget = max > 0 ? Math.min(scrollY / max, 0.999) : 0;
    };
    const onMouse = (e: MouseEvent) => {
      mXTarget = (e.clientX/innerWidth  - .5) * .08;
      mYTarget = (e.clientY/innerHeight - .5) * .05;
    };
    const onResize = () => {
      camera.aspect = el.clientWidth/el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener("scroll",    onScroll,  {passive:true});
    window.addEventListener("mousemove", onMouse);
    window.addEventListener("resize",    onResize);

    // ── Animation loop ────────────────────────────────────────────────────
    const startMs = performance.now(); let raf = 0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const t = (performance.now() - startMs) / 1000; // seconds, no THREE.Clock

      // ── Camera path (smooth Catmull-Rom, no Three.js curve API)
      tCurrent = THREE.MathUtils.lerp(tCurrent, tTarget, 0.042);
      mX = THREE.MathUtils.lerp(mX, mXTarget, 0.06);
      mY = THREE.MathUtils.lerp(mY, mYTarget, 0.06);

      const pos  = samplePath(tCurrent);
      const look = samplePath(Math.min(tCurrent + 0.03, 0.9999));

      camPos.lerp(pos, 0.1);
      camera.position.copy(camPos);
      camera.lookAt(look.x + mX*12, look.y - mY*8, look.z);

      // ── Animate books (subtle breathing sway)
      BOOKS.forEach((b,i) => {
        b.rotation.y = Math.sin(t*.25+i*.7)*.022;
        b.position.y = Math.sin(t*.18+i*.5)*.15;
      });

      // ── Hub animations
      core.rotation.y += .010; core.rotation.x += .005;
      hub.rotation.y += 0.001; // slowly rotate entire hub

      // ── Fog density shifts with journey depth
      const fogDensity = THREE.MathUtils.lerp(0.008, 0.016, tCurrent);
      (scene.fog as THREE.FogExp2).density = fogDensity;

      // ── Rush particles drift toward camera
      const rposArr = rushGeo.attributes.position.array as Float32Array;
      for (let i = 0; i < rposArr.length; i += 3) {
        rposArr[i+2] += 0.12;
        if (rposArr[i+2] > camPos.z + 5) rposArr[i+2] = camPos.z - 60;
      }
      rushGeo.attributes.position.needsUpdate = true;

      // ── Lights pulse
      lA.intensity = 27 + Math.sin(t*1.5)*8;
      lB.intensity = 17 + Math.sin(t*.9+1)*5;
      lD.intensity = 12 + Math.sin(t*1.1+2)*4;

      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll",    onScroll);
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("resize",    onResize);
      renderer.dispose();
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={ref} style={{position:"fixed", inset:0, zIndex:0}} aria-hidden />;
}
