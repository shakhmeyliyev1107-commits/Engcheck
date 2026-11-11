import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { L3Item } from "../api";

const COLOR = { document: 0x5d6877, manual: 0x0f5c8c };

/** Uskuna rangi va shaffofligi manbasini bildiradi: qo'lda — ko'k; taxminiy joylashuv — shaffof. */
function material(item: L3Item, selected: boolean) {
  const manual = item.source === "manual" || item.position_source === "manual" || item.renamed;
  return new THREE.MeshStandardMaterial({
    color: manual ? COLOR.manual : COLOR.document,
    transparent: item.position_source === "assumed",
    opacity: item.position_source === "assumed" ? 0.45 : 1,
    emissive: selected ? 0xffa200 : 0x000000,
    emissiveIntensity: selected ? 0.55 : 0,
  });
}

function geometry(item: L3Item): THREE.BufferGeometry {
  if (item.shape === "cylinder_v") return new THREE.CylinderGeometry(item.w / 2, item.w / 2, item.h, 28);
  if (item.shape === "cylinder_h") {
    const g = new THREE.CylinderGeometry(item.h / 2, item.h / 2, item.w, 24);
    g.rotateZ(Math.PI / 2);   // o'qi X bo'ylab yotadi
    return g;
  }
  return new THREE.BoxGeometry(item.w, item.h, item.d);
}

function label(text: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.fillRect(0, 0, 256, 64);
  ctx.fillStyle = "#1c2430";
  ctx.font = "bold 30px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text.slice(0, 14), 128, 32);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false }));
  sprite.scale.set(5, 1.25, 1);
  return sprite;
}

interface Props {
  items: L3Item[];
  selected: string | null;
  editable: boolean;
  onSelect: (id: string | null) => void;
  onMove: (id: string, x: number, y: number) => void;
  onError: () => void;
}

/** three.js sahnasi. Model X → sahna X, model Y → sahna −Z, balandlik → sahna Y. */
export function ThreeView({ items, selected, editable, onSelect, onMove, onError }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const ctx = useRef<{ scene: THREE.Scene; camera: THREE.PerspectiveCamera; renderer: THREE.WebGLRenderer; controls: OrbitControls; group: THREE.Group; framed: boolean } | null>(null);
  const callbacks = useRef({ onSelect, onMove, editable });
  callbacks.current = { onSelect, onMove, editable };
  const [count, setCount] = useState(0);

  useEffect(() => {
    const el = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      onError();
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf4f5f7);
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 5000);
    camera.position.set(30, 35, 45);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.maxPolarAngle = Math.PI / 2 - 0.02;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(40, 80, 30);
    scene.add(sun);
    const grid = new THREE.GridHelper(400, 80, 0x9aa5b3, 0xdde1e7);
    scene.add(grid);
    const group = new THREE.Group();
    scene.add(group);
    ctx.current = { scene, camera, renderer, controls, group, framed: false };

    const resize = () => {
      const { clientWidth: w, clientHeight: h } = el;
      renderer.setSize(w, h, false);
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(el);

    // Tanlash va zamin bo'ylab sudrash
    const ray = new THREE.Raycaster();
    const ground = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    let drag: { mesh: THREE.Object3D; offset: THREE.Vector3; moved: boolean; start: THREE.Vector3 } | null = null;
    const pointer = (e: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    };
    const down = (e: PointerEvent) => {
      ray.setFromCamera(pointer(e), camera);
      const hit = ray.intersectObjects(group.children.filter((o) => (o as THREE.Mesh).isMesh), false)[0];
      if (!hit) { callbacks.current.onSelect(null); return; }
      callbacks.current.onSelect(hit.object.userData.id);
      if (!callbacks.current.editable) return;
      const point = new THREE.Vector3();
      if (!ray.ray.intersectPlane(ground, point)) return;
      controls.enabled = false;
      drag = { mesh: hit.object, offset: hit.object.position.clone().sub(point).setY(0), moved: false, start: hit.object.position.clone() };
      renderer.domElement.setPointerCapture(e.pointerId);
    };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      ray.setFromCamera(pointer(e), camera);
      const point = new THREE.Vector3();
      if (!ray.ray.intersectPlane(ground, point)) return;
      const next = point.add(drag.offset);
      if (!drag.moved && next.distanceTo(new THREE.Vector3(drag.start.x, 0, drag.start.z)) < 0.3) return;   // titrash ko'chirish emas
      drag.moved = true;
      drag.mesh.position.x = next.x;
      drag.mesh.position.z = next.z;
      const tag = group.children.find((o) => o.userData.labelFor === drag!.mesh.userData.id);
      if (tag) { tag.position.x = next.x; tag.position.z = next.z; }
    };
    const up = () => {
      controls.enabled = true;
      if (drag?.moved) callbacks.current.onMove(drag.mesh.userData.id, Math.round(drag.mesh.position.x * 10) / 10, Math.round(-drag.mesh.position.z * 10) / 10);
      drag = null;
    };
    const dom = renderer.domElement;
    dom.addEventListener("pointerdown", down);
    dom.addEventListener("pointermove", move);
    dom.addEventListener("pointerup", up);
    dom.addEventListener("pointercancel", up);

    let frame = 0;
    const loop = () => {
      controls.update();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(loop);
    };
    loop();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      renderer.dispose();
      dom.remove();
      ctx.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const c = ctx.current;
    if (!c) return;
    for (const child of [...c.group.children]) {
      c.group.remove(child);
      const mesh = child as THREE.Mesh;
      mesh.geometry?.dispose();
      (mesh.material as THREE.Material | undefined)?.dispose?.();
    }
    for (const item of items) {
      const mesh = new THREE.Mesh(geometry(item), material(item, item.id === selected));
      mesh.position.set(item.x, item.z + item.h / 2, -item.y);
      mesh.rotation.y = THREE.MathUtils.degToRad(item.rot);
      mesh.userData.id = item.id;
      c.group.add(mesh);
      const tag = label(item.label);
      tag.position.set(item.x, item.z + item.h + 1.4, -item.y);
      tag.userData.labelFor = item.id;
      c.group.add(tag);
    }
    if (!c.framed && items.length) {   // birinchi marta kamerani modelga qaratamiz
      const box = new THREE.Box3().setFromObject(c.group);
      const center = box.getCenter(new THREE.Vector3());
      const size = Math.max(box.getSize(new THREE.Vector3()).length(), 20);
      c.controls.target.copy(center);
      c.camera.position.set(center.x + size * 0.3, size * 0.45, center.z + size * 0.6);
      c.framed = true;
    }
    setCount(items.length);
  }, [items, selected]);

  return <div className="l3-view" ref={host} data-testid="l3-view" data-rendered={count} />;
}
