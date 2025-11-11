#!/usr/bin/env python3
"""
Generador de malla 1/4 de zapata usando Gmsh.
Lee parámetros desde config.py para crear mallas consistentes.
"""

import gmsh
import numpy as np
import pyvista as pv
import meshio
import config

# ---------------------------------
# Leer parámetros desde config.py
# ---------------------------------
print("Leyendo configuración desde config.py...")

# Geometría de la zapata
B = config.ZAPATA['B']
L = config.ZAPATA['L']
tz = config.ZAPATA['h']  # Espesor/altura de zapata
Df = config.ZAPATA['Df']

# Dimensiones del dominio
dimensiones = config.obtener_dimensiones_dominio()
Lx_completo = dimensiones['Lx']
Ly_completo = dimensiones['Ly']
Lz = dimensiones['Lz']

# Estratos de suelo
estratos = config.ESTRATOS_SUELO

# Validar que los espesores suman Lz
total_espesor = sum(e['espesor'] for e in estratos)
if abs(total_espesor - Lz) > 0.01:
    print(f"⚠️  Advertencia: Suma de espesores ({total_espesor}m) != Lz ({Lz}m)")

# Calcular espesores individuales
if len(estratos) >= 3:
    H1 = estratos[0]['espesor']
    H2 = estratos[1]['espesor']
    H3 = estratos[2]['espesor']
elif len(estratos) == 2:
    H1 = estratos[0]['espesor']
    H2 = estratos[1]['espesor']
    H3 = 0.0
elif len(estratos) == 1:
    H1 = estratos[0]['espesor']
    H2 = 0.0
    H3 = 0.0
else:
    raise ValueError("Debe haber al menos 1 estrato de suelo")

print(f"✓ Zapata: {B}m × {L}m × {tz}m, Df={Df}m")
print(f"✓ Dominio completo: {Lx_completo}m × {Ly_completo}m × {Lz}m")
print(f"✓ Estratos: {len(estratos)} capas (espesores: {[e['espesor'] for e in estratos]}m)")

# --- Modelo 1/4 con simetría ---
Lx = Lx_completo / 2
Ly = Ly_completo / 2

# Posición de la zapata en el origen (para modelo 1/4)
x0 = 0.0
y0 = 0.0
z_base = -Df          # Base de la zapata (más profunda)
z_top = -Df + tz      # Tope de la zapata (sube h metros)

# ---------------------------------
# Inicializar Gmsh
# ---------------------------------
gmsh.initialize()
gmsh.model.add("zapata_3D_cuarto")

print("\nCreando geometría...")

# Crear volúmenes de estratos de suelo de forma dinámica
soil_volumes = []
z_current = 0.0

for i, estrato in enumerate(estratos):
    z_top_estrato = z_current
    z_bottom_estrato = z_current - estrato['espesor']

    # Crear caja para este estrato
    soil_vol = gmsh.model.occ.addBox(0, 0, z_bottom_estrato, Lx, Ly, estrato['espesor'])
    soil_volumes.append({
        'tag': soil_vol,
        'nombre': estrato['nombre'],
        'z_top': z_top_estrato,
        'z_bottom': z_bottom_estrato
    })

    z_current = z_bottom_estrato
    print(f"  Estrato {i+1}: {estrato['nombre']}, z={z_top_estrato:.1f} a {z_bottom_estrato:.1f}m")

# Crear excavación y zapata
# Para modelo 1/4 con zapata en el origen: usar B/2 y L/2
excav_width = B / 2
excav_length = L / 2
foot_width = B / 2
foot_length = L / 2

excav = gmsh.model.occ.addBox(x0, y0, z_base, excav_width, excav_length, Df)
foot = gmsh.model.occ.addBox(x0, y0, z_base, foot_width, foot_length, tz)

print(f"  Excavación: ancho={excav_width:.2f}m, largo={excav_length:.2f}m, profundidad={Df}m")
print(f"  Zapata: ancho={foot_width:.2f}m, largo={foot_length:.2f}m, espesor={tz}m")

gmsh.model.occ.synchronize()

# Cortar la excavación de todos los estratos
print("\nCortando excavación de estratos...")
soil_tags_cut = []

for i, soil_vol in enumerate(soil_volumes):
    is_last = (i == len(soil_volumes) - 1)

    # En el último estrato, eliminamos también la herramienta (excav)
    soil_cut, _ = gmsh.model.occ.cut(
        [(3, soil_vol['tag'])],
        [(3, excav)],
        removeObject=True,
        removeTool=is_last
    )

    if soil_cut:
        soil_tags_cut.append({
            'tag': soil_cut[0][1],
            'nombre': soil_vol['nombre']
        })
        print(f"  ✓ {soil_vol['nombre']} cortado")

gmsh.model.occ.synchronize()

# ---------------------------------
# Grupos físicos
# ---------------------------------
print("\nCreando grupos físicos...")

# Grupos para estratos de suelo
phys_groups = {}
for i, soil_data in enumerate(soil_tags_cut, 1):
    phys_group = gmsh.model.addPhysicalGroup(3, [soil_data['tag']])
    phys_name = f"SOIL_{i}"
    gmsh.model.setPhysicalName(3, phys_group, phys_name)
    phys_groups[phys_name] = phys_group
    print(f"  ✓ Grupo físico '{phys_name}': {soil_data['nombre']}")

# Grupo para zapata
phys_foot = gmsh.model.addPhysicalGroup(3, [foot])
gmsh.model.setPhysicalName(3, phys_foot, "FOOTING")
phys_groups['FOOTING'] = phys_foot
print(f"  ✓ Grupo físico 'FOOTING': Zapata de concreto")

gmsh.model.occ.synchronize()

# ---------------------------------
# Tamaño de malla - leer desde config.py
# ---------------------------------
print("\nConfigurando tamaño de malla...")

# Usar parámetros de malla gradual de config.py si está disponible
malla_params = config.MALLA.get('graded', {})
lc_min = malla_params.get('dx_min', min(B, L) / 6)
lc_max = malla_params.get('dx_max', 2.0)

# Centro de la zapata para refinamiento
x_center = x0 + foot_width / 2
y_center = y0 + foot_length / 2
z_center = (z_base + z_top) / 2

print(f"  Tamaño elemento mínimo (zapata): {lc_min:.3f}m")
print(f"  Tamaño elemento máximo (fronteras): {lc_max:.3f}m")

def size_callback(dim, tag, x, y, z, lc):
    """Calcula tamaño de elemento según distancia a zapata."""
    dx = x - x_center
    dy = y - y_center
    dz = z - z_center
    dist = np.sqrt(dx**2 + dy**2 + dz**2)

    # Refinamiento gradual desde la zapata
    if dist < 0.5:
        return lc_min
    elif dist < 2.0:
        # Transición suave
        t = (dist - 0.5) / 1.5
        return lc_min + (lc_max - lc_min) * t
    else:
        return lc_max

gmsh.model.mesh.setSizeCallback(size_callback)

print("\nGenerando malla 3D...")
gmsh.model.mesh.generate(3)

# Guardar archivo .msh
msh_file = "mallas/zapata_3D_cuarto.msh"
gmsh.write(msh_file)
print(f"✓ Malla Gmsh guardada: {msh_file}")

# ---------------------------------
# Conversión a PyVista y exportes
# ---------------------------------
print("\nExtrayendo datos de malla...")
node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
points = node_coords.reshape(-1, 3)

etags, ntags = gmsh.model.mesh.getElementsByType(4)
connectivity = ntags - 1
tet_tags = etags

# Asignar material_id a cada elemento según grupo físico
domain_id = np.zeros(len(tet_tags), dtype=int)

# Crear mapeo dinámico: grupo físico -> material_id
# Estratos de suelo: material_id = 1, 2, 3, ...
# Zapata: material_id = len(estratos) + 1
color_map = {}
for i in range(1, len(estratos) + 1):
    soil_name = f"SOIL_{i}"
    if soil_name in phys_groups:
        color_map[phys_groups[soil_name]] = i

# Zapata tiene el último material_id
color_map[phys_groups['FOOTING']] = len(estratos) + 1

print("\nAsignando material_id a elementos:")
for pg, mat_id in color_map.items():
    ents = gmsh.model.getEntitiesForPhysicalGroup(3, pg)
    count = 0
    for ent in ents:
        etags_local, _ = gmsh.model.mesh.getElementsByType(4, ent)
        for eid in etags_local:
            idx = np.where(tet_tags == eid)[0]
            domain_id[idx] = mat_id
            count += 1

    # Obtener nombre del grupo
    group_name = gmsh.model.getPhysicalName(3, pg)
    print(f"  {group_name}: material_id={mat_id}, {count} elementos")

# Crear grilla PyVista
cells = np.insert(connectivity.reshape(-1, 4), 0, 4, axis=1).ravel()
celltypes = np.full(len(connectivity) // 4, pv.CellType.TETRA, dtype=np.uint8)
grid = pv.UnstructuredGrid(cells, celltypes, points)
grid.cell_data["dominio"] = domain_id

vtu_path = "mallas/zapata_3D_cuarto.vtu"
grid.save(vtu_path)
print(f"\n✅ Guardado VTK: {vtu_path}")

xdmf_path = "mallas/zapata_3D_cuarto.xdmf"
cells_xdmf = connectivity.reshape(-1, 4) + 1
mesh = meshio.Mesh(points, [("tetra", cells_xdmf)], cell_data={"dominio": [domain_id.astype(np.int32)]})
meshio.write(xdmf_path, mesh)
print(f"✅ Guardado XDMF: {xdmf_path}")

gmsh.finalize()

# ---------------------------------
# Resumen
# ---------------------------------
print("\n" + "="*70)
print("MALLA GENERADA EXITOSAMENTE")
print("="*70)
print(f"Número de nodos: {len(points):,}")
print(f"Número de elementos: {len(tet_tags):,}")
print(f"Estratos de suelo: {len(estratos)}")
print(f"Dominios: {', '.join([f'SOIL_{i}' for i in range(1, len(estratos)+1)])} + FOOTING")
print(f"\nArchivos generados:")
print(f"  • {msh_file}")
print(f"  • {vtu_path}")
print(f"  • {xdmf_path}")
print("="*70 + "\n")
