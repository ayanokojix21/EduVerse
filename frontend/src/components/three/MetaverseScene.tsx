"use client";
import { useEffect, useRef } from "react";
import * as THREE from "three";

const CYAN   = 0x00d4ff;
const PURPLE = 0x8b5cf6;
const BG     = 0x050914;

function glow(r: number, g: number, b: number): THREE.Texture {
  const cv = document.createElement("canvas");
  cv.width = cv.height = 256;
  const ctx = cv.getContext("2d")!;
  const gr = ctx.createRadialGradient(128,128,0,128,128,128);
  gr.addColorStop(0,   `rgba(${r},${g},${b},1)`);
  gr.addColorStop(0.3, `rgba(${r},${g},${b},0.4)`);
  gr.addColorStop(1,   `rgba(0,0,0,0)`);
  ctx.fillStyle = gr;
  ctx.fillRect(0,0,256,256);
  return new THREE.CanvasTexture(cv);
}

export function MetaverseScene() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current; if (!el) return;

    // ── renderer ─────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.setClearColor(BG, 1);
    el.appendChild(renderer.domElement);

    // ── scene / camera ────────────────────────────────────────────────
    const scene  = new THREE.Scene();
    scene.background = new THREE.Color(BG);
    scene.fog        = new THREE.FogExp2(BG, 0.016);
    const camera = new THREE.PerspectiveCamera(65, el.clientWidth/el.clientHeight, 0.1, 200);
    camera.position.set(0, 1.5, 18);

    // ── lights ────────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0x0a1628, 3));
    const lCyan = new THREE.PointLight(CYAN,   30, 28); lCyan.position.set(0,0,0);  scene.add(lCyan);
    const lPurp = new THREE.PointLight(PURPLE, 12, 38); lPurp.position.set(-9,6,-6); scene.add(lPurp);
    const lWhite= new THREE.PointLight(0xffffff, 4, 22); lWhite.position.set(6,9,4);  scene.add(lWhite);

    // ── root (mouse tilt target) ─────────────────────────────────────
    const root = new THREE.Group();
    scene.add(root);

    // ── central torus knot ────────────────────────────────────────────
    const tkG = new THREE.Group(); root.add(tkG);

    tkG.add(new THREE.Mesh(
      new THREE.TorusKnotGeometry(2.2, 0.65, 200, 24, 3, 5),
      new THREE.MeshPhongMaterial({ color:0x010a1e, emissive:0x000510, shininess:200, specular:CYAN })
    ));
    tkG.add(new THREE.Mesh(
      new THREE.TorusKnotGeometry(2.2, 0.66, 60, 12, 3, 5),
      new THREE.MeshBasicMaterial({ color:CYAN, wireframe:true, transparent:true, opacity:0.45 })
    ));
    tkG.add(new THREE.Mesh(
      new THREE.TorusKnotGeometry(2.22, 0.68, 30, 6, 3, 5),
      new THREE.MeshBasicMaterial({ color:PURPLE, wireframe:true, transparent:true, opacity:0.22 })
    ));

    const mkSprite = (tex:THREE.Texture, op:number, sc:number) => {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map:tex, transparent:true, opacity:op, blending:THREE.AdditiveBlending, depthWrite:false }));
      s.scale.set(sc,sc,1); return s;
    };
    tkG.add(mkSprite(glow(0,212,255),  0.65, 30));
    tkG.add(mkSprite(glow(255,255,255),0.35, 10));

    // ── orbital rings ─────────────────────────────────────────────────
    const addRing = (r:number, color:number, rx:number, ry:number, op:number) => {
      const m = new THREE.Mesh(new THREE.TorusGeometry(r,0.02,8,150),
        new THREE.MeshBasicMaterial({color, transparent:true, opacity:op}));
      m.rotation.x = rx; m.rotation.y = ry; root.add(m); return m;
    };
    addRing(5.8, CYAN,  1.97, 0,   0.30);
    addRing(9.0, PURPLE,1.37, 0.3, 0.20);
    addRing(12,  CYAN,  0.8,  0.9, 0.10);

    // ── orbiting icosahedra ───────────────────────────────────────────
    const ORBS = [
      {r:5.8, sp: 0.004, col:CYAN,   sz:0.35, ph:0    },
      {r:5.8, sp: 0.004, col:CYAN,   sz:0.22, ph:2.09 },
      {r:5.8, sp: 0.004, col:PURPLE, sz:0.28, ph:4.19 },
      {r:9.0, sp:-0.0025,col:PURPLE, sz:0.45, ph:0.5  },
      {r:9.0, sp:-0.0025,col:CYAN,   sz:0.32, ph:2.6  },
      {r:9.0, sp:-0.0025,col:PURPLE, sz:0.40, ph:4.7  },
    ] as const;

    const orbiters = ORBS.map(o => {
      const g2 = new THREE.Group(); root.add(g2);
      g2.add(new THREE.Mesh(
        new THREE.IcosahedronGeometry(o.sz, 1),
        new THREE.MeshBasicMaterial({color:o.col, wireframe:true, transparent:true, opacity:0.9})
      ));
      g2.add(new THREE.Mesh(
        new THREE.IcosahedronGeometry(o.sz*0.82, 0),
        new THREE.MeshBasicMaterial({color: o.col===CYAN ? 0x001a26 : 0x0e0a2a, transparent:true, opacity:0.95})
      ));
      const gc = o.col===CYAN ? glow(0,212,255) : glow(139,92,246);
      g2.add(mkSprite(gc, 0.5, o.sz*5.5));
      return { g:g2, ...o, angle: o.ph };
    });

    // ── particles ─────────────────────────────────────────────────────
    const pv: number[] = [];
    for (let i=0;i<2200;i++) {
      const r=12+Math.random()*22, th=Math.random()*Math.PI*2, ph=Math.acos(2*Math.random()-1);
      pv.push(r*Math.sin(ph)*Math.cos(th), r*Math.sin(ph)*Math.sin(th), r*Math.cos(ph));
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.Float32BufferAttribute(pv,3));
    scene.add(new THREE.Points(pGeo, new THREE.PointsMaterial({color:0x5590c0, size:0.07, transparent:true, opacity:0.65})));

    // ── grid ─────────────────────────────────────────────────────────
    const grid = new THREE.GridHelper(80, 50, 0x0a2040, 0x050e1e);
    grid.position.y = -8;
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.4;
    root.add(grid);

    // ── state ─────────────────────────────────────────────────────────
    let trX=0, trY=0, crX=0, crY=0, tCamZ=18;

    const onMouse = (e:MouseEvent) => {
      trY =  (e.clientX/innerWidth -0.5)*2 * 0.28;
      trX = -(e.clientY/innerHeight-0.5)*2 * 0.18;
    };
    const onScroll = () => {
      const pct = Math.min(scrollY/(document.documentElement.scrollHeight-innerHeight||1),1);
      tCamZ = 18 - pct*10;
      camera.position.y = 1.5 - pct*4;
    };
    const onResize = () => {
      camera.aspect = el.clientWidth/el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener("mousemove", onMouse);
    window.addEventListener("scroll",    onScroll, {passive:true});
    window.addEventListener("resize",    onResize);

    // ── animation loop ────────────────────────────────────────────────
    const clock = new THREE.Clock(); let raf=0;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      const t = clock.getElapsedTime();

      // Torus knot slow rotation + breathe
      tkG.rotation.y += 0.003; tkG.rotation.x = Math.sin(t*0.4)*0.15;
      const breathe = 1 + Math.sin(t*1.2)*0.05; tkG.scale.setScalar(breathe);

      // Orbiter animation
      orbiters.forEach(o => {
        o.angle += o.sp;
        o.g.position.set(Math.cos(o.angle)*o.r, Math.sin(o.angle*0.5)*1.8, Math.sin(o.angle)*o.r);
        o.g.rotation.y += 0.012; o.g.rotation.x += 0.007;
      });

      // Lights pulse
      lCyan.intensity  = 25 + Math.sin(t*1.5)*8;
      lPurp.intensity  = 10 + Math.sin(t*0.9+1)*4;

      // Mouse parallax
      crX = THREE.MathUtils.lerp(crX, trX, 0.04);
      crY = THREE.MathUtils.lerp(crY, trY, 0.04);
      root.rotation.x = crX; root.rotation.y = crY;

      // Camera zoom
      camera.position.z = THREE.MathUtils.lerp(camera.position.z, tCamZ, 0.05);

      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("scroll",    onScroll);
      window.removeEventListener("resize",    onResize);
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={ref} style={{position:"absolute",inset:0,zIndex:0}} aria-hidden="true"/>;
}
