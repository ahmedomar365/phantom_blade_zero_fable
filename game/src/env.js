// Vermilion Gate environment: renderer, arena, lighting, wet floor, weather and post-processing.
// The game owns the camera transform; everything else about how the place looks lives here.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { Reflector } from 'three/addons/objects/Reflector.js';

const V3 = THREE.Vector3;
export const MOON_DIR = new V3(-0.38, 0.40, -0.83).normalize();
const COURT = { x: 17.6, zN: -13.0, zS: 17.6 };           // water sheet / leaf landing area (three.js coords)
const RIPPLES = 10;
const POOL = 5, RING_I = 17, KEY_I = 16, FILL_I = 0.62, RIM_I = 0.75;
const MOON_I = 1.25;

const C_WARM = new THREE.Color(0xffa24e), C_HOT = new THREE.Color(0xff4a1c);
const C_FOG = new THREE.Color(0x0a1322), C_FOG2 = new THREE.Color(0x1c0b0d);
const C_MOON = new THREE.Color(0x9cb8ff), C_MOON2 = new THREE.Color(0xc6a8b8);

const VERT = 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }';

const FinalShader = {
  uniforms: {
    tDiffuse: { value: null }, time: { value: 0 }, res: { value: new THREE.Vector2(1, 1) },
    damage: { value: 0 }, flash: { value: 0 }, desat: { value: 0 }, blur: { value: 0 }, vignette: { value: 1 },
    bars: { value: 0 }, phase: { value: 0 },
  },
  vertexShader: VERT,
  fragmentShader: `
    uniform sampler2D tDiffuse; uniform vec2 res;
    uniform float time, damage, flash, desat, blur, vignette, bars, phase; varying vec2 vUv;
    float hash(vec2 p){ p = fract(p*vec2(123.34, 456.21)); p += dot(p, p+45.32); return fract(p.x*p.y); }
    void main(){
      vec2 c = vUv - 0.5;
      float r2 = dot(c, c);
      vec3 col;
      if (blur > 0.001) {                                   // radial blur toward the centre (dashes, heavy hits)
        col = vec3(0.0);
        float j = hash(vUv * res + time);
        for (int i = 0; i < 10; i++) {
          float t = (float(i) + j) / 10.0;
          col += texture2D(tDiffuse, vUv - c * t * blur * 0.16).rgb;
        }
        col *= 0.1;
      } else {
        vec2 off = c * r2 * 0.008;                          // a touch of lens fringing at the edges
        col = vec3(texture2D(tDiffuse, vUv + off).r, texture2D(tDiffuse, vUv).g, texture2D(tDiffuse, vUv - off).b);
      }
      float l = dot(col, vec3(0.299, 0.587, 0.114));
      // grade: cold shadows, warm highlights; phase two pushes the shadows toward ember red
      vec3 shadowTint = mix(vec3(0.90, 1.0, 1.12), vec3(1.10, 0.90, 0.92), phase);
      col = mix(col * shadowTint, col * vec3(1.06, 1.0, 0.93), smoothstep(0.12, 0.65, l));
      col = (col - 0.5) * (1.08 + 0.06 * phase) + 0.5;
      col = mix(col, vec3(l) * vec3(0.92, 1.0, 1.10), desat * 0.85);          // slow-motion wash
      col *= 1.0 - smoothstep(0.10, 0.60, r2) * 0.50 * vignette;
      col += (hash(vUv * res + fract(time) * 91.7) - 0.5) * 0.035;
      float edge = smoothstep(0.04, 0.42, r2);
      col = mix(col, vec3(0.50, 0.0, 0.0) + col * 0.35, clamp(damage * edge * 1.3, 0.0, 0.85));
      col += flash;
      float bar = step(0.5 - 0.115 * bars, abs(c.y));                          // cinematic letterbox
      gl_FragColor = vec4(col * (1.0 - bar * step(0.001, bars)), 1.0);
    }`,
};

const WaterShader = {
  name: 'WetCourt',
  uniforms: {
    color: { value: null }, tDiffuse: { value: null }, textureMatrix: { value: null },
    tNormal: { value: null }, tNoise: { value: null }, time: { value: 0 }, rain: { value: 1 },
    ripples: { value: [] }, moonDir: { value: MOON_DIR.clone() }, moonColor: { value: new THREE.Color(0x9cb8ff) },
    strength: { value: 1.0 }, fogColor: { value: new THREE.Color() }, fogDensity: { value: 0.012 },
  },
  vertexShader: `
    uniform mat4 textureMatrix; varying vec4 vUv; varying vec3 vWorld;
    void main(){
      vUv = textureMatrix * vec4(position, 1.0);
      vWorld = (modelMatrix * vec4(position, 1.0)).xyz;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
  fragmentShader: `
    uniform sampler2D tDiffuse, tNormal, tNoise; uniform float time, rain, strength, fogDensity;
    uniform vec4 ripples[${RIPPLES}]; uniform vec3 moonDir, moonColor, fogColor;
    varying vec4 vUv; varying vec3 vWorld;
    float hash(vec2 p){ p = fract(p*vec2(123.34, 456.21)); p += dot(p, p+45.32); return fract(p.x*p.y); }
    vec2 rainRings(vec2 p){
      vec2 acc = vec2(0.0);
      for (int k = 0; k < 3; k++) {
        vec2 q = p * (1.3 + float(k) * 0.85) + float(k) * 17.3;
        vec2 cell = floor(q); vec2 f = fract(q) - 0.5;
        float h = hash(cell + float(k) * 3.7);
        float tt = fract(time * (0.50 + 0.35 * h) + h * 7.0);
        vec2 ctr = (vec2(hash(cell + 3.1), hash(cell + 7.7)) - 0.5) * 0.45;
        vec2 d = f - ctr; float dist = length(d);
        float rad = tt * 0.42;
        float ring = exp(-pow((dist - rad) * 24.0, 2.0)) * (1.0 - tt) * (1.0 - tt);
        acc += normalize(d + 1e-5) * ring * sin((dist - rad) * 70.0);
      }
      return acc;
    }
    void main(){
      vec2 p = vWorld.xz;
      vec3 toCam = cameraPosition - vWorld;
      float dist = length(toCam);
      vec3 V = toCam / dist;
      vec2 n1 = texture2D(tNormal, p * 0.105 + time * vec2(0.011, 0.019)).xy * 2.0 - 1.0;
      vec2 n2 = texture2D(tNormal, p * 0.29 - time * vec2(0.021, 0.012)).xy * 2.0 - 1.0;
      vec2 nxy = (n1 * 0.55 + n2 * 0.45) * 0.10;
      vec2 nc = nxy * 0.6;
      float near = smoothstep(26.0, 3.0, dist);
      vec2 rings = rainRings(p) * 0.55 * rain * near;
      for (int i = 0; i < ${RIPPLES}; i++) {
        vec4 r = ripples[i];
        float age = time - r.z;
        if (r.w > 0.0 && age > 0.0 && age < 2.6) {
          vec2 d = p - r.xy; float dl = length(d);
          float rad = 0.15 + age * 2.4;
          float k = 1.0 - age / 2.6;
          float w = exp(-pow((dl - rad) * 2.6, 2.0)) * k * k * r.w;
          nxy += normalize(d + 1e-4) * w * sin((dl - rad) * 11.0) * 0.40;
        }
      }
      // standing water gathers in the low flags: mask from low-frequency noise (kept wet almost everywhere)
      float depth = smoothstep(0.26, 0.52, texture2D(tNoise, p * 0.043).r);
      float wet = mix(0.42, 1.0, depth);
      vec3 N = normalize(vec3(nxy.x + rings.x, 1.0, nxy.y + rings.y));
      nxy += rings * 0.22;                                  // rings tilt the surface a lot but only nudge the mirror image
      float cosT = max(dot(N, V), 0.0);
      float F = 0.035 + 0.965 * pow(1.0 - cosT, 4.2);
      vec4 uv = vUv;
      uv.xy += nxy * min(uv.w, 14.0) * (0.30 * mix(0.35, 1.0, depth));
      vec3 refl = texture2DProj(tDiffuse, uv).rgb;
      refl = min(refl, vec3(1.3));                        // the mirrored moon and lantern cores stay under the bloom threshold
      vec3 R = reflect(-V, N);
      // moon glint: computed on the calm surface only (no rain rings), so it stays a thin broken streak
      vec3 Rc = reflect(-V, normalize(vec3(nc.x, 1.0, nc.y)));
      float spec = pow(max(dot(Rc, moonDir), 0.0), 2600.0) * 1.1;
      refl *= 1.0 - 0.8 * smoothstep(0.975, 0.998, dot(Rc, moonDir));   // the mirrored moon disc and its halo are dimmed: a glint, not a lamp
      vec3 col = min(refl * F * wet * strength + moonColor * spec * depth, vec3(0.52));
      float a = clamp(depth * 0.42 * (1.0 - F) + F * wet * 0.85, 0.0, 0.96);   // water darkens the stone and hides it at grazing angles
      float fog = 1.0 - exp(-fogDensity * fogDensity * dist * dist);
      col = mix(col, fogColor * a, fog);
      // fade the sheet out at its rim so it never shows a hard edge against steps and walls
      vec2 e = vec2(${COURT.x.toFixed(1)} - abs(p.x), min(p.y - (${COURT.zN.toFixed(1)}), ${COURT.zS.toFixed(1)} - p.y));
      float rim = smoothstep(0.0, 0.5, min(e.x, e.y));
      gl_FragColor = vec4(col * rim, a * rim);
    }`,
};

function glowTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)');
  gr.addColorStop(0.14, 'rgba(255,255,255,0.5)');
  gr.addColorStop(0.42, 'rgba(255,255,255,0.11)');
  gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr;
  g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function mistTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  for (let i = 0; i < 26; i++) {
    const x = 128 + (Math.random() - 0.5) * 120, y = 128 + (Math.random() - 0.5) * 70, r = 34 + Math.random() * 60;
    const gr = g.createRadialGradient(x, y, 0, x, y, r);
    gr.addColorStop(0, 'rgba(255,255,255,0.10)');
    gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr;
    g.fillRect(0, 0, 256, 256);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export class Env {
  constructor(canvas, { quality = 2, adaptive = !navigator.webdriver } = {}) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' });
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(C_FOG.getHex(), 0.012);
    this.camera = new THREE.PerspectiveCamera(45, 16 / 9, 0.1, 900);
    this.camera.layers.enable(1);                            // layer 1: things the floor reflection skips (rain, mist, splashes)
    this.scene.add(this.camera);
    this.radius = 11;
    this.quality = quality;
    this.post = { damage: 0, flash: 0, desat: 0, blur: 0, vignette: 1, bars: 0 };
    this.time = 0;
    this.phase = 0;
    this.phaseTarget = 0;
    this.wind = 0;                                           // gust energy, decays
    this.noAO = [];
    this.aoScale = 0.5;
    // adaptive resolution: if frames run long, the internal resolution steps down (never during automated tests)
    this.adaptive = adaptive;
    this.scale = 1;
    this._ft = 12; this._last = 0; this._adaptT = 0;
    this.glow = [];
    this.lamps = [];
    this.meta = null;
    this._v = new V3();
    this._rip = 0;
    this._zero = new V3();
  }

  async load(onProgress = () => {}) {
    const total = 15.4e6;
    const arena = new Promise((res, rej) => new GLTFLoader().load('assets/arena.glb', res,
      (e) => onProgress(Math.min(0.92, e.loaded / (e.total || total))), rej));
    const tl = new THREE.TextureLoader();
    const tex = (f) => new Promise((res, rej) => tl.load('assets/' + f, res, undefined, rej));
    const sky = new Promise((res, rej) => new HDRLoader().load('assets/sky_night.hdr', res, undefined, rej));
    const [g, skyTex, wn, nz, leaf, meta] = await Promise.all([arena, sky, tex('waternormals.jpg'), tex('noise.png'), tex('leaf.png'),
      fetch('assets/arena_meta.json').then((r) => r.json())]);
    this.meta = meta;
    this.tex = { sky: skyTex, wn, nz, leaf, glow: glowTexture(), mist: mistTexture() };
    for (const t of [wn, nz]) { t.wrapS = t.wrapT = THREE.RepeatWrapping; }
    leaf.colorSpace = THREE.SRGBColorSpace;
    this.build(g.scene);
    this.setQuality(this.quality);
    // compile every material up front so the first frames of the fight do not hitch
    await this.renderer.compileAsync(this.scene, this.camera);
    // one real frame through the whole post stack, so its one-off compile cost lands on the loading screen
    this.camera.position.set(1.1, 2.15, 9.3);
    this.camera.lookAt(0, 1.45, -2);
    this.update(0.016, this._zero);
    this.render();
    onProgress(1);
  }

  // ------------------------------------------------------------------ construction
  build(arena) {
    const { scene, renderer, meta } = this;
    const sky = this.tex.sky;
    sky.mapping = THREE.EquirectangularReflectionMapping;
    scene.background = sky;
    scene.backgroundIntensity = 0.55;
    const pm = new THREE.PMREMGenerator(renderer);
    scene.environment = pm.fromEquirectangular(sky).texture;
    scene.environmentIntensity = 0.55;
    pm.dispose();

    // ---- moon: cold rim light from behind the hall; one fixed shadow frustum covers the whole court
    const moon = new THREE.DirectionalLight(C_MOON.getHex(), MOON_I);
    moon.castShadow = true;
    moon.shadow.mapSize.set(4096, 4096);
    const sc = moon.shadow.camera;
    sc.left = -30; sc.right = 30; sc.top = 34; sc.bottom = -30; sc.near = 20; sc.far = 220;
    moon.shadow.bias = -0.0005;
    moon.shadow.normalBias = 0.05;
    moon.target.position.set(0, 0, -4);
    moon.position.copy(moon.target.position).addScaledVector(MOON_DIR, 110);
    scene.add(moon, moon.target);
    this.moon = moon;
    this.hemi = new THREE.HemisphereLight(0x33486e, 0x0b0907, 0.42);
    scene.add(this.hemi);
    // soft sky fill from the camera's usual side so faces and chests never go black
    // two shadowless lights ride with the camera: a soft cool fill from over its shoulder so backs and faces never
    // go black, and a cold rim from beyond the fighters so their outlines separate from the dark floor at any angle
    this.fill = new THREE.DirectionalLight(0x86a0d8, FILL_I);
    this.rim = new THREE.DirectionalLight(0xa8c4ff, RIM_I);
    scene.add(this.fill, this.fill.target, this.rim, this.rim.target);
    this._f = new V3(); this._r = new V3();

    // ---- arena
    const tint = (m) => { if (m.userData.tint) m.color.setRGB(...m.userData.tint); };
    const seen = new Set();
    arena.traverse((o) => {
      if (!o.isMesh) return;
      const top = (o.parent && o.parent !== arena ? o.parent : o).name || o.name;
      o.castShadow = !/^(Glow|Backdrop|Ground|Floor)/.test(top);
      o.receiveShadow = !/^(Glow|Backdrop)/.test(top);
      if (/^(Foliage|BackdropNeedles)/.test(top)) this.noAO.push(o);
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      mats.forEach((m, i) => {
        if (seen.has(m)) return;
        seen.add(m);
        tint(m);
        for (const k of ['map', 'normalMap', 'roughnessMap', 'metalnessMap']) if (m[k]) m[k].anisotropy = 8;
        if (m.name.startsWith('glow_')) {
          if (m.map) m.emissiveMap = m.map;
          m.emissiveIntensity *= ({ glow_lattice: 0.45, glow_interior: 0.8, glow_paper: 0.8, glow_paperred: 0.75, glow_flame: 0.6 })[m.name] ?? 1;
          m.userData.e0 = m.emissiveIntensity;
          m.userData.c0 = m.emissive.clone();
          this.glow.push(m);
        } else if (m.name.startsWith('bg_')) {
          m.fog = false; m.roughness = 1; m.metalness = 0; m.envMapIntensity = 0;
          m.emissive.copy(m.color).multiplyScalar(m.name === 'bg_ground' ? 0.0 : 1.0);
          m.color.multiplyScalar(m.name === 'bg_ground' ? 1.0 : 0.0);
          m.userData.e0 = 1; m.userData.c0 = m.emissive.clone();
          if (m.name !== 'bg_ground') this.bgMats = (this.bgMats || []).concat(m);
        } else if (m.name === 'ar_plaster') {
          m.color.multiplyScalar(0.72);
        } else if (m.name === 'ar_foliage' || m.name === 'ar_needle') {
          m.alphaTest = 0.45; m.transparent = false; m.depthWrite = true; m.side = THREE.DoubleSide;
          m.envMapIntensity = 0.0;
          if (m.name === 'ar_needle') { m.color.multiplyScalar(0.13); m.roughnessMap = null; m.metalnessMap = null; m.roughness = 1; m.metalness = 0; }
          if (m.name === 'ar_foliage') { m.roughnessMap = null; m.metalnessMap = null; m.roughness = 0.95; m.metalness = 0; this.swayMaterial(m); }
        } else if (m.name === 'ar_flag' || m.name === 'ar_medallion' || m.name === 'ar_band') {
          // the water sheet supplies the mirror; the stone under it stays matte so lights do not double up as glare
          m.envMapIntensity = 0.5; m.roughnessMap = null; m.metalnessMap = null; m.roughness = 0.9; m.metalness = 0;
          const pm = new THREE.MeshPhysicalMaterial();
          THREE.MeshStandardMaterial.prototype.copy.call(pm, m);
          pm.specularIntensity = 0.3;
          mats[i] = pm;
          if (Array.isArray(o.material)) o.material[i] = pm; else o.material = pm;
          seen.add(pm);
        }
      });
    });
    scene.add(arena);
    this.arena = arena;

    // ---- lantern lights
    const P = (a) => new V3(a[0], a[1], a[2]);
    const lamp = (pos, intensity, dist, opts = {}) => {
      const l = new THREE.PointLight(C_WARM.getHex(), intensity, dist, 2);
      l.position.copy(pos);
      scene.add(l);
      this.lamps.push({ l, i0: intensity, ph: Math.random() * 20, flick: opts.flick ?? 0.08, hot: opts.hot ?? 1 });
      return l;
    };
    const sprite = (pos, size, opacity, color = 0xffa860) => {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.tex.glow, color, blending: THREE.AdditiveBlending,
        depthWrite: false, transparent: true, opacity, fog: false }));
      s.scale.setScalar(size);
      s.position.copy(pos);
      s.userData.o0 = opacity;
      scene.add(s);
      this.noAO.push(s);
      (this.sprites = this.sprites || []).push(s);
      return s;
    };
    // the ring of stone lanterns shares a small pool of real lights: the ones nearest the fight are lit, with fades
    this.ringPos = [];
    for (const a of meta.stone_lanterns) {
      const p = P(a);
      if (Math.hypot(p.x, p.z) < 14) this.ringPos.push(p.clone().add(new V3(0, 0.25, 0)));
      sprite(p, 1.5, 0.42);
    }
    this.pool = Array.from({ length: POOL }, (_, i) => {
      const l = new THREE.PointLight(C_WARM.getHex(), 0, 14, 2);
      scene.add(l);
      return { l, idx: -1, fade: 0, ph: i * 3.1 };
    });
    for (const a of meta.path_lanterns) sprite(P(a), 1.4, 0.35);
    for (const a of meta.hall_lanterns) sprite(P(a), P(a).z < 0 ? 2.6 : 1.8, 0.30, 0xff7a48);
    for (const a of meta.string_lanterns) sprite(P(a), 0.95, 0.30, 0xff9a5a);
    for (const a of meta.candles) sprite(P(a), 0.5, 0.5, 0xffc880);
    // porch lanterns wash the facade and the steps; the south gate gets one too
    lamp(new V3(-7, 5.0, -19.4), 60, 30, { flick: 0.04 });
    lamp(new V3(7, 5.0, -19.4), 60, 30, { flick: 0.04 });
    lamp(new V3(0, 3.4, 16.4), 30, 18);
    const tc = meta.tree.canopy;
    lamp(new V3(tc[0] - 1.5, 3.6, tc[2] + 1.5), 34, 13, { flick: 0.05 });      // lantern glow caught under the maple
    // candle light inside the nave pours out of the open door: a long warm backlight with shadows
    const door = new THREE.SpotLight(0xff9a48, 420, 70, 0.40, 0.55, 2);
    door.position.set(0, 3.7, -25.7);
    door.target.position.set(0, 0.4, -7);
    door.castShadow = true;
    door.shadow.mapSize.set(1024, 1024);
    door.shadow.camera.near = 1.0; door.shadow.camera.far = 60;
    door.shadow.bias = -0.0006; door.shadow.normalBias = 0.04;
    scene.add(door, door.target);
    this.door = door;
    this.lamps.push({ l: door, i0: door.intensity, ph: 3.3, flick: 0.06, hot: 1 });
    // gentle warm key that travels with the fighters (reads as the sum of the lantern ring)
    this.key = new THREE.PointLight(0xffc49a, KEY_I, 17, 2);
    scene.add(this.key);

    this.buildWater();
    this.buildRain();
    this.buildLeaves();
    this.buildSplashes();
    this.buildMist();
    this.buildPost();
    this.resize();
  }

  /** Foliage cards rock in the wind (vertex shader only, so shadows stay put). */
  swayMaterial(m) {
    this.swayUni = { swayT: { value: 0 }, swayAmp: { value: 1 } };
    m.onBeforeCompile = (sh) => {
      sh.uniforms.swayT = this.swayUni.swayT;
      sh.uniforms.swayAmp = this.swayUni.swayAmp;
      sh.vertexShader = 'uniform float swayT; uniform float swayAmp;\n' + sh.vertexShader.replace('#include <begin_vertex>',
        `#include <begin_vertex>
         { float ph = position.x * 0.9 + position.z * 1.3 + position.y * 0.7;
           transformed += vec3(sin(swayT * 1.3 + ph), 0.5 * sin(swayT * 1.9 + ph * 1.7), cos(swayT * 1.1 + ph * 0.8)) * 0.05 * swayAmp; }`);
    };
  }

  updatePool(dt, focus, k) {
    const want = this.ringPos.map((p, i) => [p.distanceToSquared(focus), i]).sort((a, b) => a[0] - b[0]).slice(0, POOL).map((a) => a[1]);
    const held = this.pool.map((s) => s.idx);
    for (const s of this.pool) {
      const keep = want.includes(s.idx);
      s.fade = Math.max(0, Math.min(1, s.fade + (keep ? 1 : -1) * dt * 2.5));
      if (!keep && s.fade <= 0) {
        const next = want.find((i) => !held.includes(i));
        if (next !== undefined) { s.idx = next; held.push(next); s.l.position.copy(this.ringPos[next]); if (this.time < 0.5) s.fade = 1; }
      }
      const f = 1 + 0.08 * (Math.sin(this.time * 9.1 + s.ph) * 0.5 + Math.sin(this.time * 23.7 + s.ph * 2.3) * 0.3 + Math.sin(this.time * 3.3 + s.ph) * 0.4);
      s.l.intensity = RING_I * s.fade * f * (1 + 0.55 * k);
      s.l.color.copy(C_WARM).lerp(C_HOT, k * 0.75);
    }
  }

  buildWater() {
    const w = COURT.x * 2, d = COURT.zS - COURT.zN;
    const water = new Reflector(new THREE.PlaneGeometry(w, d), { textureWidth: 1280, textureHeight: 720, shader: WaterShader, multisample: 0, clipBias: 0.003 });
    const u = water.material.uniforms;
    u.tNormal.value = this.tex.wn;
    u.tNoise.value = this.tex.nz;
    u.ripples.value = Array.from({ length: RIPPLES }, () => new THREE.Vector4(0, 0, -99, 0));
    u.fogColor.value = this.scene.fog.color;
    water.material.transparent = true;
    water.material.depthWrite = false;
    water.material.blending = THREE.CustomBlending;
    water.material.blendSrc = THREE.OneFactor;
    water.material.blendDst = THREE.OneMinusSrcAlphaFactor;
    water.rotation.x = -Math.PI / 2;
    water.position.set(0, 0.018, (COURT.zN + COURT.zS) / 2);
    water.renderOrder = 1;
    this.scene.add(water);
    this.water = water;
    this.noAO.push(water);
    water.getReflectionCamera(this.camera).layers.set(0);
    // quality 0 refreshes the mirror every other frame
    const render = water.onBeforeRender;
    let skip = 0;
    water.onBeforeRender = (...a) => {
      if (this.quality === 0 && (skip++ & 1)) return;
      render.apply(water, a);
    };
  }

  buildRain() {
    const N = 3600;
    const pos = new Float32Array(N * 6), end = new Float32Array(N * 2), rnd = new Float32Array(N * 2);
    for (let i = 0; i < N; i++) {
      const x = Math.random() * 40, y = Math.random() * 22, z = Math.random() * 40, r = Math.random();
      pos.set([x, y, z, x, y, z], i * 6);
      end.set([0, 1], i * 2);
      rnd.set([r, r], i * 2);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('end', new THREE.BufferAttribute(end, 1));
    g.setAttribute('rnd', new THREE.BufferAttribute(rnd, 1));
    this.rainMat = new THREE.ShaderMaterial({
      uniforms: { time: { value: 0 }, cam: { value: new V3() }, slant: { value: new V3(1.2, 0, 0.7) }, amount: { value: 1 } },
      vertexShader: `uniform float time, amount; uniform vec3 cam, slant; attribute float end; attribute float rnd; varying float vA;
        void main(){
          vec3 box = vec3(40.0, 22.0, 40.0);
          vec3 vel = vec3(slant.x, -15.0 - rnd * 6.0, slant.z);
          vec3 p = position + vel * time;
          p = mod(p - cam, box) - box * 0.5 + cam;
          p += normalize(vel) * end * (0.26 + rnd * 0.34);
          vec4 mv = viewMatrix * vec4(p, 1.0);
          vA = amount * (0.030 + 0.085 * rnd) * smoothstep(20.0, 5.0, -mv.z) * smoothstep(0.4, 1.6, -mv.z);
          // the hall porch and nave are roofed
          if (p.y < 0.0 || (p.z < -18.6 && p.y < 7.0 && abs(p.x) < 15.0)) vA = 0.0;
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: 'varying float vA; void main(){ gl_FragColor = vec4(vec3(0.60, 0.70, 0.86) * vA, 1.0); }',
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false,
    });
    this.rain = new THREE.LineSegments(g, this.rainMat);
    this.rain.frustumCulled = false;
    this.rain.layers.set(1);
    this.scene.add(this.rain);
    this.noAO.push(this.rain);
  }

  buildLeaves() {
    const MAX = 240;
    const geo = new THREE.PlaneGeometry(1, 1);
    const cell = new Float32Array(MAX * 2);
    for (let i = 0; i < MAX; i++) { cell[i * 2] = (i & 1) * 0.5; cell[i * 2 + 1] = ((i >> 1) & 1) * 0.5; }
    geo.setAttribute('aCell', new THREE.InstancedBufferAttribute(cell, 2));
    const mat = new THREE.MeshStandardMaterial({ map: this.tex.leaf, alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.55, envMapIntensity: 0.4 });
    mat.onBeforeCompile = (sh) => {
      sh.vertexShader = 'attribute vec2 aCell;\n' + sh.vertexShader.replace('#include <uv_vertex>', '#include <uv_vertex>\n vMapUv = uv * 0.5 + aCell;');
    };
    const mesh = new THREE.InstancedMesh(geo, mat, MAX);
    mesh.frustumCulled = false;
    mesh.castShadow = false;
    mesh.receiveShadow = true;
    this.scene.add(mesh);
    this.noAO.push(mesh);
    this.leafMesh = mesh;
    this.leaves = [];
    for (let i = 0; i < MAX; i++) {
      const L = { p: new V3(), v: new V3(), q: new THREE.Quaternion(), ax: new V3(), spin: 0, size: 0.15, state: 0, t: 0, life: 0, ph: Math.random() * 10 };
      this.spawnLeaf(L, true);
      this.leaves.push(L);
    }
    this._m = new THREE.Matrix4(); this._q = new THREE.Quaternion(); this._s = new V3();
  }

  spawnLeaf(L, warm = false) {
    const t = this.meta.tree, c = t.canopy;
    const fromTree = Math.random() < 0.72;
    if (fromTree) {
      const a = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random()) * t.radius;
      L.p.set(c[0] + Math.cos(a) * r, t.bottom + Math.random() * (t.top - t.bottom) * 0.6, c[2] + Math.sin(a) * r);
    } else {
      L.p.set((Math.random() - 0.5) * 30, 9 + Math.random() * 5, COURT.zN + Math.random() * (COURT.zS - COURT.zN));
    }
    L.v.set(-0.5 - Math.random() * 0.5, -0.5 - Math.random() * 0.45, 0.25 + Math.random() * 0.4);
    L.ax.set(Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5).normalize();
    L.q.setFromAxisAngle(L.ax, Math.random() * 6.28);
    L.spin = (Math.random() < 0.5 ? -1 : 1) * (1.5 + Math.random() * 3.5);
    L.size = 0.13 + Math.random() * 0.11;
    L.state = 0; L.t = 0;
    if (warm) {
      // pre-roll: some already in the air lower down, some already floating on the water
      const k = Math.random();
      if (k < 0.45) {
        L.state = 1; L.life = 4 + Math.random() * 22; L.t = Math.random() * 4;
        const a = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random());
        if (Math.random() < 0.6) L.p.set(c[0] - 3 + Math.cos(a) * r * 8, 0.03, c[2] + 3 + Math.sin(a) * r * 8);
        else L.p.set((Math.random() - 0.5) * 32, 0.03, COURT.zN + Math.random() * (COURT.zS - COURT.zN));
        L.p.x = Math.max(-COURT.x + 0.5, Math.min(COURT.x - 0.5, L.p.x));
        L.p.z = Math.max(COURT.zN + 0.5, Math.min(COURT.zS - 0.5, L.p.z));
        L.q.setFromAxisAngle(new V3(1, 0, 0), -Math.PI / 2).premultiply(new THREE.Quaternion().setFromAxisAngle(new V3(0, 1, 0), Math.random() * 6.28));
      } else {
        const f = Math.random();
        L.p.addScaledVector(L.v, f * 9);
        if (L.p.y < 0.4) L.p.y = 0.4 + Math.random() * 6;
      }
    }
  }

  updateLeaves(dt) {
    const mesh = this.leafMesh, n = mesh.count, m = this._m, q = this._q, s = this._s;
    const gust = this.wind, t = this.time;
    for (let i = 0; i < n; i++) {
      const L = this.leaves[i];
      let scale = L.size;
      if (L.state === 0) {
        const flutter = Math.sin(t * 2.3 + L.ph) * 0.9;
        L.p.x += (L.v.x * (1 + gust * 3.5) + flutter * 0.35) * dt;
        L.p.z += (L.v.z * (1 + gust * 2.0) + Math.cos(t * 1.7 + L.ph * 1.3) * 0.3) * dt;
        L.p.y += (L.v.y * (1 + 0.5 * this.phase) + Math.abs(flutter) * 0.25 + gust * 0.9) * dt;
        q.setFromAxisAngle(L.ax, L.spin * (1 + gust * 2) * dt);
        L.q.premultiply(q);
        const inCourt = Math.abs(L.p.x) < COURT.x && L.p.z > COURT.zN && L.p.z < COURT.zS;
        if (L.p.y < 0.03) {
          if (inCourt) {
            L.state = 1; L.t = 0; L.life = 7 + Math.random() * 16; L.p.y = 0.03;
            L.q.setFromAxisAngle(s.set(1, 0, 0), -Math.PI / 2).premultiply(q.setFromAxisAngle(s.set(0, 1, 0), Math.random() * 6.28));
            if (this._v.set(L.p.x, 0, L.p.z).distanceToSquared(this.camera.position) < 400 && Math.random() < 0.35) this.pushRipple(L.p.x, L.p.z, 0.22);
          } else this.spawnLeaf(L);
        } else if (L.p.y < -1 || Math.abs(L.p.x) > 30 || Math.abs(L.p.z) > 34) this.spawnLeaf(L);
      } else {
        L.t += dt;
        L.p.x += (-0.035 + Math.sin(t * 0.4 + L.ph) * 0.02 - gust * 0.5) * dt;
        L.p.z += (0.02 + Math.cos(t * 0.33 + L.ph) * 0.02 + gust * 0.25) * dt;
        L.p.y = 0.03 + Math.sin(t * 1.6 + L.ph) * 0.004;
        if (L.t > L.life) this.spawnLeaf(L);
        else if (L.t > L.life - 1.2) scale *= (L.life - L.t) / 1.2;
      }
      m.compose(L.p, L.q, s.set(scale, scale, scale));
      mesh.setMatrixAt(i, m);
    }
    mesh.instanceMatrix.needsUpdate = true;
  }

  buildSplashes() {
    const N = 220;
    this.spl = { n: N, i: 0, p: new Float32Array(N * 3), v: new Float32Array(N * 3), life: new Float32Array(N) };
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(this.spl.p, 3));
    g.setAttribute('life', new THREE.BufferAttribute(this.spl.life, 1));
    const mat = new THREE.ShaderMaterial({
      uniforms: { scale: { value: 600 } },
      vertexShader: `attribute float life; varying float vL; uniform float scale;
        void main(){ vL = life; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = (0.035 + 0.03 * life) * scale / -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `varying float vL; void main(){ vec2 c = gl_PointCoord - 0.5; float a = smoothstep(0.5, 0.1, length(c)) * clamp(vL * 2.0, 0.0, 1.0);
        gl_FragColor = vec4(vec3(0.55, 0.66, 0.85) * a * 0.55, 1.0); }`,
      transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false,
    });
    for (let i = 0; i < N; i++) this.spl.p[i * 3 + 1] = -10;
    this.splashes = new THREE.Points(g, mat);
    this.splashes.frustumCulled = false;
    this.splashes.layers.set(1);
    this.scene.add(this.splashes);
    this.noAO.push(this.splashes);
  }

  updateSplashes(dt) {
    const S = this.spl;
    for (let i = 0; i < S.n; i++) {
      if (S.life[i] <= 0) continue;
      S.life[i] -= dt * 1.7;
      S.v[i * 3 + 1] -= 9.8 * dt;
      S.p[i * 3] += S.v[i * 3] * dt; S.p[i * 3 + 1] += S.v[i * 3 + 1] * dt; S.p[i * 3 + 2] += S.v[i * 3 + 2] * dt;
      if (S.p[i * 3 + 1] < 0 || S.life[i] <= 0) { S.life[i] = 0; S.p[i * 3 + 1] = -10; }
    }
    this.splashes.geometry.attributes.position.needsUpdate = true;
    this.splashes.geometry.attributes.life.needsUpdate = true;
  }

  buildMist() {
    this.mist = [];
    const spots = [[-13, -9], [12, -10], [-14, 6], [13, 9], [0, -14], [-5, 15], [7, 14], [0, -22], [-16, -1], [16, 1]];
    for (const [x, z] of spots) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.tex.mist, color: 0x8fa6cc, transparent: true, opacity: 0.16, depthWrite: false, fog: false }));
      s.position.set(x, 1.1 + Math.random() * 0.8, z);
      s.scale.set(15 + Math.random() * 7, 4.5 + Math.random() * 2, 1);
      s.userData = { x, z, ph: Math.random() * 10, o0: 0.13 + Math.random() * 0.07 };
      s.layers.set(1);
      this.scene.add(s);
      this.noAO.push(s);
      this.mist.push(s);
    }
  }

  buildPost() {
    const { renderer, scene, camera } = this;
    const rt = new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, samples: 4 });
    this.composer = new EffectComposer(renderer, rt);
    this.composer.addPass(new RenderPass(scene, camera));
    this.gtao = new GTAOPass(scene, camera, 4, 4);
    this.gtao.updateGtaoMaterial({ radius: 0.5, distanceExponent: 1.4, thickness: 1.2, scale: 1.2, samples: 12, screenSpaceRadius: false });
    this.gtao.blendIntensity = 1.0;
    const aoRender = this.gtao.render.bind(this.gtao);
    // The AO pass redraws the scene with a normal material. Anything that is not solid geometry (sprites, lines,
    // points, the water, alpha cards, and any transparent / additive / non-depth-writing effect mesh the game adds)
    // must stay out of it: such meshes often have no normals, which turns into NaN -> black blocks on screen.
    const hidden = [];
    const solid = (m) => !(m.transparent || m.depthWrite === false || m.blending !== THREE.NormalBlending || m.visible === false);
    this.gtao.render = (...a) => {
      hidden.length = 0;
      for (const o of this.noAO) if (o.visible) { o.visible = false; hidden.push(o); }
      scene.traverseVisible((o) => {
        if (o.userData.noAO || o.isSprite || o.isPoints || o.isLine
          || (o.isMesh && !(Array.isArray(o.material) ? o.material.every(solid) : solid(o.material)))) hidden.push(o);
      });
      for (const o of hidden) o.visible = false;
      aoRender(...a);
      for (const o of hidden) o.visible = true;
    };
    const gs = this.gtao.setSize.bind(this.gtao);
    this.gtao.setSize = (w, h) => gs(Math.max(2, Math.round(w * this.aoScale)), Math.max(2, Math.round(h * this.aoScale)));
    this.composer.addPass(this.gtao);
    this.composer.addPass(new ShaderPass({                  // scrub NaN/inf so bloom cannot smear them
      uniforms: { tDiffuse: { value: null } }, vertexShader: VERT,
      fragmentShader: `uniform sampler2D tDiffuse; varying vec2 vUv;
        void main(){ vec3 c = texture2D(tDiffuse, vUv).rgb;
          uvec3 b = floatBitsToUint(c) & uvec3(0x7F800000u);
          if (b.r == 0x7F800000u || b.g == 0x7F800000u || b.b == 0x7F800000u) c = vec3(0.0);
          gl_FragColor = vec4(clamp(c, 0.0, 16.0), 1.0); }`,
    }));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(4, 4), 0.36, 0.7, 1.0);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());
    this.final = new ShaderPass(FinalShader);
    this.composer.addPass(this.final);
  }

  // ------------------------------------------------------------------ public controls
  setQuality(q) {
    this.quality = q = Math.max(0, Math.min(2, q | 0));
    this.scale = 1;
    if (!this.composer) return;
    this.gtao.enabled = q >= 2;
    this.moon.shadow.mapSize.setScalar(q >= 2 ? 4096 : (q === 1 ? 2048 : 1024));
    if (this.moon.shadow.map) { this.moon.shadow.map.dispose(); this.moon.shadow.map = null; }
    this.door.castShadow = q >= 1;
    this.leafMesh.count = q >= 2 ? 240 : (q === 1 ? 140 : 70);
    this.rain.geometry.setDrawRange(0, (q >= 1 ? 3600 : 1600) * 2);
    this.mist.forEach((s, i) => { s.visible = q >= 1 || i < 4; });
    this.pixelRatio = Math.min(window.devicePixelRatio || 1, q >= 2 ? 1.25 : (q === 1 ? 1.0 : 0.75));
    this.resize();
  }

  resize() {
    if (!this.composer) return;
    const w = window.innerWidth, h = window.innerHeight, pr = (this.pixelRatio || 1) * this.scale;
    this.renderer.setPixelRatio(pr);
    this.renderer.setSize(w, h, false);
    this.composer.setPixelRatio(pr);
    this.composer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.final.uniforms.res.value.set(w * pr, h * pr);
    this.splashes.material.uniforms.scale.value = h * pr;
    const k = this.quality >= 2 ? 0.5 : (this.quality === 1 ? 0.4 : 0.3);      // mirror resolution relative to the frame
    this.water.getRenderTarget().setSize(Math.max(256, Math.round(w * pr * k)), Math.max(144, Math.round(h * pr * k)));
  }

  pushRipple(x, z, strength) {
    const r = this.water.material.uniforms.ripples.value[this._rip];
    r.set(x, z, this.time, strength);
    this._rip = (this._rip + 1) % RIPPLES;
  }

  /** Ring ripple on the water sheet plus a small crown of droplets (footsteps ~0.4, slams 2-3). */
  ripple(x, z, strength = 1) {
    if (Math.abs(x) > COURT.x || z < COURT.zN || z > COURT.zS) return;
    this.pushRipple(x, z, Math.min(3, strength));
    const S = this.spl, n = Math.min(40, Math.round(4 + strength * 9));
    for (let k = 0; k < n; k++) {
      const i = S.i; S.i = (S.i + 1) % S.n;
      const a = Math.random() * Math.PI * 2, sp = (0.5 + Math.random() * 1.3) * (0.6 + 0.4 * strength);
      S.p[i * 3] = x + Math.cos(a) * 0.12; S.p[i * 3 + 1] = 0.03; S.p[i * 3 + 2] = z + Math.sin(a) * 0.12;
      S.v[i * 3] = Math.cos(a) * sp; S.v[i * 3 + 1] = (1.2 + Math.random() * 1.8) * (0.6 + 0.4 * strength); S.v[i * 3 + 2] = Math.sin(a) * sp;
      S.life[i] = 0.6 + Math.random() * 0.5;
    }
  }

  /** Burst of wind: leaves and rain are kicked sideways and the canopy thrashes for a moment. */
  gust(strength = 1) { this.wind = Math.min(2.5, this.wind + strength); }

  /** 0..1 blend to the phase-two mood. */
  setPhase(k) { this.phaseTarget = Math.max(0, Math.min(1, k)); }

  // ------------------------------------------------------------------ per frame
  update(dt, focus) {
    this.time += dt;
    const t = this.time;
    this.wind *= Math.exp(-dt * 1.4);
    this.phase += (this.phaseTarget - this.phase) * Math.min(1, dt * 1.5);
    const k = this.phase, cam = this.camera.getWorldPosition(this._v);

    // mood
    this.scene.fog.color.copy(C_FOG).lerp(C_FOG2, k);
    this.moon.color.copy(C_MOON).lerp(C_MOON2, k * 0.6);
    this.moon.intensity = MOON_I * (1 - 0.30 * k);
    this.hemi.intensity = 0.42 * (1 - 0.25 * k);
    this.scene.backgroundIntensity = 0.55 * (1 - 0.25 * k);
    for (const L of this.lamps) {
      const f = 1 + L.flick * (Math.sin(t * 9.1 + L.ph) * 0.5 + Math.sin(t * 23.7 + L.ph * 2.3) * 0.3 + Math.sin(t * 3.3 + L.ph * 0.7) * 0.4);
      L.l.intensity = L.i0 * f * (1 + 0.55 * k);
      L.l.color.copy(C_WARM).lerp(C_HOT, k * 0.75);
    }
    for (const m of this.glow) {
      m.emissiveIntensity = m.userData.e0 * (1 + 0.45 * k) * (1 + 0.04 * Math.sin(t * 7.0 + m.id));
      m.emissive.copy(m.userData.c0).lerp(C_HOT, k * 0.45);
    }
    if (this.sprites) for (const s of this.sprites) { s.material.opacity = s.userData.o0 * (1 + 0.5 * k); }
    this.key.color.setHex(0xffc49a).lerp(C_HOT, k * 0.5);
    this.key.intensity = KEY_I * (1 + 0.3 * k);
    if (focus) this.key.position.set(focus.x * 0.85, 3.2, focus.z * 0.85 + 4.5);
    this.updatePool(dt, focus || this._zero, k);
    {
      const fo = focus || this._zero, f = this._f, r = this._r;
      this.camera.getWorldDirection(f); f.y = 0;
      if (f.lengthSq() < 1e-4) f.set(0, 0, -1);
      f.normalize(); r.set(-f.z, 0, f.x);
      this.fill.target.position.set(fo.x, 1.2, fo.z);
      this.fill.position.copy(this.fill.target.position).addScaledVector(f, -10).addScaledVector(r, -6).setY(10);
      this.rim.target.position.set(fo.x, 1.2, fo.z);
      this.rim.position.copy(this.rim.target.position).addScaledVector(f, 10).addScaledVector(r, 5.5).setY(6.5);
      this.fill.intensity = FILL_I * (1 - 0.15 * k);
      this.rim.intensity = RIM_I;
      this.rim.color.setHex(0xa8c4ff).lerp(C_HOT, k * 0.35);
    }

    // weather
    const rm = this.rainMat.uniforms;
    rm.time.value = t;
    rm.cam.value.copy(cam);
    rm.slant.value.set(1.2 - this.wind * 7, 0, 0.7 + this.wind * 3);
    rm.amount.value = 1 + 0.5 * k + this.wind * 0.4;
    const wu = this.water.material.uniforms;
    wu.time.value = t;
    wu.rain.value = 1 + 0.4 * k;
    wu.moonColor.value.copy(this.moon.color).multiplyScalar(this.moon.intensity / MOON_I);
    wu.fogDensity.value = this.scene.fog.density;
    if (this.swayUni) { this.swayUni.swayT.value += dt * (1 + this.wind * 4); this.swayUni.swayAmp.value = 1 + this.wind * 2.5; }
    this.updateLeaves(dt);
    this.updateSplashes(dt);
    for (const s of this.mist) {
      const u = s.userData;
      s.position.x = u.x + Math.sin(t * 0.05 + u.ph) * 3 - this.wind * 1.5;
      s.position.z = u.z + Math.cos(t * 0.04 + u.ph) * 2;
      s.material.opacity = u.o0 * (0.8 + 0.2 * Math.sin(t * 0.21 + u.ph)) * (1 + 0.3 * k);
      s.material.color.setHex(0x8fa6cc).lerp(C_HOT, k * 0.25);
    }
    const fu = this.final.uniforms;
    fu.time.value = t;
    fu.phase.value = k;
  }

  render() {
    const fu = this.final.uniforms, p = this.post;
    fu.damage.value = p.damage; fu.flash.value = p.flash; fu.desat.value = p.desat;
    fu.blur.value = p.blur; fu.vignette.value = p.vignette; fu.bars.value = p.bars;
    this.composer.render();
    const now = performance.now(), ft = now - this._last;
    this._last = now;
    if (ft < 100) this._ft += (ft - this._ft) * 0.05;
    if (this.adaptive && now - this._adaptT > 2000) {
      this._adaptT = now;
      if (this._ft > 19.5 && this.scale > 0.6) { this.scale = Math.max(0.6, this.scale - 0.1); this.resize(); }
      else if (this._ft < 11.0 && this.scale < 1) { this.scale = Math.min(1, this.scale + 0.1); this.resize(); }
    }
  }
}
