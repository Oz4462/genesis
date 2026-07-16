"""Interactive Three.js STL viewer HTML for realization packages.

Embeds a self-contained viewer that loads package STLs via File API or listed
URLs. No external build step. Closes the "no interactive 3D" residual gap for
offline package inspection (exploded slider + rotate).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_stl_viewer_html(
    stl_files: list[str],
    *,
    title: str = "GENESIS assembly viewer",
    run_id: str | None = None,
) -> str:
    """Return a self-contained HTML document with Three.js CDN + STL loader UI."""
    import json

    files_json = json.dumps(list(stl_files))
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>{_esc(title)}</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0}}
header{{padding:10px 16px;background:#1e293b;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
#c{{width:100%;height:calc(100vh - 56px);display:block}}
label{{font-size:12px;opacity:.85}}
input[type=range]{{width:140px}}
</style>
</head><body>
<header>
  <strong>{_esc(title)}</strong>
  <span style="opacity:.7;font-size:12px">run={_esc(run_id or "n/a")}</span>
  <label>explode <input id="ex" type="range" min="0" max="100" value="0"/></label>
  <label><input id="wire" type="checkbox"/> wireframe</label>
  <span id="info" style="font-size:12px;opacity:.7"></span>
</header>
<canvas id="c"></canvas>
<script type="importmap">
{{"imports":{{
  "three":"https://unpkg.com/three@0.160.0/build/three.module.js",
  "three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"
}}}}
</script>
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
import {{ STLLoader }} from 'three/addons/loaders/STLLoader.js';

const files = {files_json};
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({{canvas, antialias:true}});
renderer.setPixelRatio(devicePixelRatio);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0f172a);
const camera = new THREE.PerspectiveCamera(50, 2, 0.1, 5000);
camera.position.set(120, 90, 160);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xffffff, 0x224455, 1.1));
const dir = new THREE.DirectionalLight(0xffffff, 0.8);
dir.position.set(50, 100, 40);
scene.add(dir);
scene.add(new THREE.GridHelper(400, 20, 0x334155, 0x1e293b));

const group = new THREE.Group();
scene.add(group);
const meshes = [];
const loader = new STLLoader();
const info = document.getElementById('info');

function resize() {{
  const w = canvas.clientWidth, h = canvas.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
}}
window.addEventListener('resize', resize);
resize();

async function loadOne(url, i) {{
  try {{
    const geo = await new Promise((res, rej) => loader.load(url, res, undefined, rej));
    geo.computeVertexNormals();
    const mat = new THREE.MeshPhongMaterial({{
      color: new THREE.Color().setHSL(0.55 + i*0.08, 0.55, 0.55),
      flatShading: false,
      transparent: true, opacity: 0.95
    }});
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData.base = mesh.position.clone();
    mesh.userData.idx = i;
    group.add(mesh);
    meshes.push(mesh);
    info.textContent = `loaded ${{meshes.length}}/${{files.length}} STL`;
  }} catch (e) {{
    info.textContent = `STL load failed for ${{url}} (open via local server or drag-drop)`;
  }}
}}

// relative paths work when package is served; else user can drop files
files.forEach((f, i) => loadOne(f, i));

// drag-drop fallback
canvas.addEventListener('dragover', e => e.preventDefault());
canvas.addEventListener('drop', e => {{
  e.preventDefault();
  [...e.dataTransfer.files].forEach((file, i) => {{
    if (!file.name.toLowerCase().endsWith('.stl')) return;
    const url = URL.createObjectURL(file);
    loadOne(url, meshes.length + i);
  }});
}});

const ex = document.getElementById('ex');
const wire = document.getElementById('wire');
ex.oninput = () => {{
  const k = (+ex.value) / 100 * 40;
  meshes.forEach((m, i) => {{
    m.position.x = (i - (meshes.length-1)/2) * k;
  }});
}};
wire.onchange = () => meshes.forEach(m => {{ m.material.wireframe = wire.checked; }});

function frame(t) {{
  resize();
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}}
requestAnimationFrame(frame);
</script>
</body></html>
"""


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_stl_viewer(
    pkg_root: Path,
    stl_files: list[str],
    *,
    title: str = "GENESIS assembly viewer",
    run_id: str | None = None,
) -> Path:
    """Write ``viewer_3d.html`` into the package root."""
    root = Path(pkg_root)
    # use basenames so relative load works from package dir
    rels = [Path(s).name for s in stl_files]
    path = root / "viewer_3d.html"
    path.write_text(
        build_stl_viewer_html(rels, title=title, run_id=run_id),
        encoding="utf-8",
    )
    return path
