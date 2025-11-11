#!/usr/bin/env python3
"""
===================================================================================
ANÁLISIS DE ZAPATAS EN 2 FASES CON OPENSEESPY
===================================================================================
Este script ejecuta análisis en 2 fases:
  FASE 1 - GRAVEDAD: Campo de tensiones inicial por peso propio
  FASE 2 - CARGA:    Asentamiento incremental por carga de columna

Flujo de trabajo:
  1. Lee configuración desde config.py
  2. Genera/lee malla con fusión de nodos duplicados
  3. Crea modelo en OpenSeesPy
  4. FASE 1: Aplica gravedad, analiza, guarda resultados
  5. FASE 2: Fija gravedad, aplica carga, analiza, guarda resultados
  6. Genera resultados combinados y reportes

USO:
    python run_analysis_2phases.py

CONFIGURACIÓN:
    Modifica los parámetros en config.py antes de ejecutar
===================================================================================
"""

import openseespy.opensees as ops
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import sys

# Importar configuración y utilidades
import config
import utils

# ===================================================================================
# FUNCIÓN PRINCIPAL
# ===================================================================================

def main():
    """Función principal que ejecuta el análisis completo."""

    print("\n" + "="*80)
    print("ANÁLISIS DE ZAPATA CON OPENSEESPY - VERSIÓN INTEGRADA")
    print("="*80)
    print(f"\nFecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # -------------------------
    # 1. VALIDAR CONFIGURACIÓN
    # -------------------------
    print("\n" + "="*80)
    print("PASO 1: VALIDANDO CONFIGURACIÓN")
    print("="*80)

    config.imprimir_resumen()

    if not config.validar_configuracion():
        print("\n❌ Errores en la configuración. Por favor corrige config.py")
        sys.exit(1)

    # -------------------------
    # 2. PREPARAR PARÁMETROS
    # -------------------------
    print("\n" + "="*80)
    print("PASO 2: PREPARANDO MODELO")
    print("="*80)

    # Extraer parámetros
    zapata = config.ZAPATA
    dominio_cfg = config.DOMINIO
    malla_cfg = config.MALLA
    mat_suelo = config.MATERIAL_SUELO
    estratos_suelo = config.ESTRATOS_SUELO
    mat_zapata = config.MATERIAL_ZAPATA
    cargas = config.CARGAS
    salida = config.SALIDA

    # Calcular dimensiones del dominio
    usar_cuarto = dominio_cfg['usar_cuarto_modelo']
    factor = dominio_cfg['factor_horizontal']

    if usar_cuarto:
        # Modelo 1/4
        Lx = factor * zapata['B'] / 2.0
        Ly = factor * zapata['L'] / 2.0
        B_modelo = zapata['B'] / 2.0
        L_modelo = zapata['L'] / 2.0
        print(f"✓ Usando modelo 1/4 con simetría")
        print(f"  Dominio 1/4: {Lx}m × {Ly}m × {dominio_cfg['profundidad']}m")
    else:
        # Modelo completo
        Lx = factor * zapata['B']
        Ly = factor * zapata['L']
        B_modelo = zapata['B']
        L_modelo = zapata['L']
        print(f"✓ Usando modelo completo")
        print(f"  Dominio completo: {Lx}m × {Ly}m × {dominio_cfg['profundidad']}m")

    Lz = dominio_cfg['profundidad']

    dominio = {'Lx': Lx, 'Ly': Ly, 'Lz': Lz}
    zapata_modelo = {'B': B_modelo, 'L': L_modelo, 'h': zapata['h'],
                     'Df': zapata['Df'],  # Agregar profundidad de desplante
                     'x_min': 0.0, 'y_min': 0.0}

    # -------------------------
    # 3. GENERAR MALLA CON GMSH
    # -------------------------
    print("\n" + "="*80)
    print("PASO 3: GENERANDO MALLA CON GMSH")
    print("="*80)

    print("Ejecutando generate_mesh_quarter.py...")
    print("(Esto generará una malla tetraédrica con Gmsh)")

    import subprocess
    result = subprocess.run(
        ['python3', 'generate_mesh_quarter.py'],
        capture_output=True,
        text=True,
        timeout=300  # 5 minutos máximo
    )

    if result.returncode != 0:
        print(f"❌ Error al generar malla:")
        print(result.stderr)
        sys.exit(1)

    # Mostrar salida del generador de malla
    print(result.stdout)

    # Leer malla generada desde archivo .vtu
    import pyvista as pv
    mesh_file = "mallas/zapata_3D_cuarto.vtu"

    print(f"\nLeyendo malla desde {mesh_file}...")
    grid = pv.read(mesh_file)

    # Extraer información de la malla
    points = grid.points
    cells = grid.cells
    material_ids = grid.cell_data.get('dominio', None)

    # Contar elementos por tipo
    num_elements = grid.n_cells
    num_nodes = grid.n_points

    print(f"✓ Malla cargada:")
    print(f"  Nodos: {num_nodes:,}")
    print(f"  Elementos tetraédricos: {num_elements:,}")

    # Verificar que hay material_ids
    if material_ids is None:
        print("❌ Error: No se encontraron material_ids en la malla")
        sys.exit(1)

    # Mostrar distribución de materiales
    unique_mats = np.unique(material_ids)
    print(f"  Materiales encontrados: {unique_mats}")
    for mat_id in unique_mats:
        count = np.sum(material_ids == mat_id)
        if mat_id == len(estratos_suelo) + 1:
            print(f"    Material {mat_id} (ZAPATA): {count:,} elementos")
        else:
            print(f"    Material {mat_id} (ESTRATO {mat_id}): {count:,} elementos")

    # -------------------------
    # 4. CREAR MODELO EN OPENSEESPY
    # -------------------------
    print("\n" + "="*80)
    print("PASO 4: CREANDO MODELO EN OPENSEESPY")
    print("="*80)

    # Inicializar
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 3)
    print("✓ Modelo inicializado (3D, 3 DOF)")

    # -------------------------
    # FUSIONAR NODOS DUPLICADOS
    # -------------------------
    print("\nDetectando y fusionando nodos duplicados...")

    # Crear diccionario para detectar duplicados
    coord_to_nodes = {}
    tolerance = 1e-6

    for i, point in enumerate(points):
        # Redondear coordenadas para detectar duplicados
        key = (round(point[0] / tolerance) * tolerance,
               round(point[1] / tolerance) * tolerance,
               round(point[2] / tolerance) * tolerance)

        if key not in coord_to_nodes:
            coord_to_nodes[key] = []
        coord_to_nodes[key].append(i)

    # Crear mapeo: índice_original -> índice_maestro
    node_mapping = {}  # índice en points (0-based) -> node_id en OpenSees (1-based)
    master_nodes = {}  # node_id -> coords
    next_node_id = 1
    duplicates_found = 0

    for key, node_indices in coord_to_nodes.items():
        # El primer nodo es el maestro
        master_idx = node_indices[0]

        # Todos los nodos en esta posición mapean al maestro
        for idx in node_indices:
            node_mapping[idx] = next_node_id

        # Guardar coordenadas del nodo maestro
        master_nodes[next_node_id] = points[master_idx]

        # Contar duplicados
        if len(node_indices) > 1:
            duplicates_found += len(node_indices) - 1

        next_node_id += 1

    print(f"  ✓ Nodos duplicados detectados: {duplicates_found}")
    print(f"  ✓ Nodos únicos (después de fusión): {len(master_nodes)}")

    # Crear nodos en OpenSees (solo los maestros)
    print("\nCreando nodos en OpenSees...")
    node_coords = {}
    for node_id, coords in master_nodes.items():
        ops.node(node_id, float(coords[0]), float(coords[1]), float(coords[2]))
        node_coords[node_id] = np.array(coords)

    print(f"✓ {len(node_coords)} nodos creados (interfaces fusionadas)")

    # Identificar nodos en superficie (z máxima)
    z_max = points[:, 2].max()
    surface_nodes = [nid for nid, coords in node_coords.items() if abs(coords[2] - z_max) < 0.01]
    print(f"✓ {len(surface_nodes)} nodos en superficie (z={z_max:.2f}m)")

    # Identificar nodos en el tope de la zapata
    Df = zapata['Df']
    h_zapata = zapata['h']
    z_tope_zapata = -Df  # Tope de zapata (fondo de excavación)
    z_base_zapata = -Df - h_zapata  # Base de zapata

    # Límites de la zapata en planta (modelo 1/4)
    # Para modelo 1/4, la zapata empieza en el origen (0, 0)
    x_min_zapata = 0.0
    x_max_zapata = B_modelo / 2
    y_min_zapata = 0.0
    y_max_zapata = L_modelo / 2

    zapata_nodes = []
    for nid, coords in node_coords.items():
        x, y, z = coords
        # Nodo está en el tope de la zapata
        if (abs(z - z_tope_zapata) < 0.1 and
            x_min_zapata <= x <= x_max_zapata and
            y_min_zapata <= y <= y_max_zapata):
            zapata_nodes.append(nid)

    print(f"✓ {len(zapata_nodes)} nodos en tope de zapata (z≈{z_tope_zapata:.2f}m)")

    # Aplicar condiciones de borde
    print("\nAplicando condiciones de borde...")

    # Fondo: empotrado (z mínima)
    z_min = points[:, 2].min()
    fixed_nodes = [nid for nid, coords in node_coords.items() if abs(coords[2] - z_min) < 0.01]
    for nid in fixed_nodes:
        ops.fix(nid, 1, 1, 1)
    print(f"  ✓ {len(fixed_nodes)} nodos fijados en fondo (z={z_min:.2f}m)")

    # Planos de simetría (modelo 1/4)
    if usar_cuarto:
        # Plano x=0: desplazamiento en X = 0
        x_min_tol = points[:, 0].min()
        x_symmetry_nodes = [nid for nid, coords in node_coords.items() if abs(coords[0] - x_min_tol) < 0.01]
        for nid in x_symmetry_nodes:
            if nid not in fixed_nodes:  # No re-aplicar si ya está fijado
                ops.fix(nid, 1, 0, 0)
        print(f"  ✓ {len(x_symmetry_nodes)} nodos en plano X=0 (simetría)")

        # Plano y=0: desplazamiento en Y = 0
        y_min_tol = points[:, 1].min()
        y_symmetry_nodes = [nid for nid, coords in node_coords.items() if abs(coords[1] - y_min_tol) < 0.01]
        for nid in y_symmetry_nodes:
            if nid not in fixed_nodes:
                ops.fix(nid, 0, 1, 0)
        print(f"  ✓ {len(y_symmetry_nodes)} nodos en plano Y=0 (simetría)")

    # Definir materiales
    print("\nDefiniendo materiales...")

    # NOTA: Usando 'ElasticIsotropic' sin rho para evitar bug con FourNodeTetrahedron
    # El parámetro rho causa valores incorrectos en desplazamientos

    # Materiales de estratos de suelo
    for i, estrato in enumerate(estratos_suelo, 1):
        mat_tag = i
        ops.nDMaterial('ElasticIsotropic', mat_tag,
                       estrato['E'], estrato['nu'])
        print(f"✓ {estrato['nombre']} (tag={mat_tag}): E={estrato['E']/1000:.0f} MPa")

    # Material concreto (zapata)
    mat_tag_zapata = len(estratos_suelo) + 1
    ops.nDMaterial('ElasticIsotropic', mat_tag_zapata,
                   mat_zapata['E'], mat_zapata['nu'])
    print(f"✓ Material concreto (tag={mat_tag_zapata}): E={mat_zapata['E']/1000:.0f} MPa")

    # Crear elementos tetraédricos
    print("\nCreando elementos tetraédricos...")

    # Extraer conectividad de tetraedros
    # En PyVista, cells tiene formato: [n_points, p0, p1, ..., n_points, p0, p1, ...]
    element_id = 1
    cell_idx = 0
    element_counts = {mat_id: 0 for mat_id in unique_mats}

    while cell_idx < len(cells):
        n_points = cells[cell_idx]
        if n_points != 4:
            print(f"⚠️  Advertencia: Elemento con {n_points} nodos (esperado 4)")
            cell_idx += n_points + 1
            continue

        # Nodos del tetraedro (PyVista usa indexación 0-based)
        # Mapear a node_ids de OpenSees usando node_mapping
        idx1 = int(cells[cell_idx + 1])
        idx2 = int(cells[cell_idx + 2])
        idx3 = int(cells[cell_idx + 3])
        idx4 = int(cells[cell_idx + 4])

        n1 = node_mapping[idx1]
        n2 = node_mapping[idx2]
        n3 = node_mapping[idx3]
        n4 = node_mapping[idx4]

        # Material del elemento
        mat_id = int(material_ids[element_id - 1])

        # Crear elemento en OpenSees
        ops.element('FourNodeTetrahedron', element_id, n1, n2, n3, n4, mat_id)

        element_counts[mat_id] += 1
        element_id += 1
        cell_idx += n_points + 1

    total_elements = element_id - 1
    print(f"✓ {total_elements:,} elementos tetraédricos creados")

    # Reportar por material
    for mat_id in sorted(element_counts.keys()):
        count = element_counts[mat_id]
        if mat_id == mat_tag_zapata:
            print(f"  Material {mat_id} (ZAPATA): {count:,} elementos")
        else:
            estrato_idx = mat_id - 1
            if 0 <= estrato_idx < len(estratos_suelo):
                print(f"  Material {mat_id} ({estratos_suelo[estrato_idx]['nombre']}): {count:,} elementos")

    # -------------------------
    # 5a. FASE 1 - GRAVEDAD
    # -------------------------
    print("\n" + "="*80)
    print("FASE 1: APLICANDO GRAVEDAD")
    print("="*80)

    # Patrón de carga para gravedad
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)

    # Aplicar fuerzas gravitacionales a cada elemento tetraédrico
    print("\nCalculando fuerzas gravitacionales por elemento...")

    g = 9.81  # m/s²

    # Crear diccionario para acumular fuerzas por nodo
    node_forces = {nid: np.array([0.0, 0.0, 0.0]) for nid in node_coords.keys()}

    # Recorrer todos los elementos para aplicar gravedad
    element_id = 1
    cell_idx = 0
    total_weight = 0.0

    while cell_idx < len(cells):
        n_points = cells[cell_idx]
        if n_points != 4:
            cell_idx += n_points + 1
            continue

        # Índices de nodos en PyVista (0-based)
        idx1 = int(cells[cell_idx + 1])
        idx2 = int(cells[cell_idx + 2])
        idx3 = int(cells[cell_idx + 3])
        idx4 = int(cells[cell_idx + 4])

        # IDs de nodos en OpenSees (1-based, con fusión)
        n1 = node_mapping[idx1]
        n2 = node_mapping[idx2]
        n3 = node_mapping[idx3]
        n4 = node_mapping[idx4]

        # Coordenadas de los 4 nodos
        p1 = points[idx1]
        p2 = points[idx2]
        p3 = points[idx3]
        p4 = points[idx4]

        # Calcular volumen del tetraedro
        v1 = p2 - p1
        v2 = p3 - p1
        v3 = p4 - p1
        vol = abs(np.dot(v1, np.cross(v2, v3)) / 6.0)

        # Obtener densidad según material
        mat_id = int(material_ids[element_id - 1])
        if mat_id == mat_tag_zapata:
            rho = mat_zapata['rho']
        else:
            estrato_idx = mat_id - 1
            rho = estratos_suelo[estrato_idx]['rho']

        # Fuerza gravitacional total del elemento (en kN)
        weight = vol * rho * g / 1000.0  # kN
        total_weight += weight

        # Distribuir fuerza en 4 nodos (1/4 cada uno)
        force_per_node = -weight / 4.0  # Negativo = hacia abajo en Z

        node_forces[n1][2] += force_per_node
        node_forces[n2][2] += force_per_node
        node_forces[n3][2] += force_per_node
        node_forces[n4][2] += force_per_node

        element_id += 1
        cell_idx += n_points + 1

    # Aplicar fuerzas acumuladas a los nodos
    for nid, force in node_forces.items():
        if abs(force[2]) > 1e-10:  # Solo si hay fuerza significativa
            ops.load(nid, float(force[0]), float(force[1]), float(force[2]))

    print(f"✓ Fuerzas gravitacionales aplicadas")
    print(f"  Peso total del modelo: {total_weight:.2f} kN")
    print(f"  Nodos con carga gravitacional: {len([f for f in node_forces.values() if abs(f[2]) > 1e-10])}")

    # -------------------------
    # 6a. ANÁLISIS FASE 1
    # -------------------------
    print("\n" + "="*80)
    print("EJECUTANDO ANÁLISIS FASE 1 - GRAVEDAD")
    print("="*80)

    analisis_cfg = config.ANALISIS

    ops.system(analisis_cfg['solver'])
    ops.numberer(analisis_cfg['numberer'])
    ops.constraints(analisis_cfg['constraints'])
    ops.integrator('LoadControl', 1.0)
    ops.algorithm(analisis_cfg['algorithm'])
    ops.analysis(analisis_cfg['tipo'])

    print(f"Configuración:")
    print(f"  Solver: {analisis_cfg['solver']}")
    print(f"  Algorithm: {analisis_cfg['algorithm']}")

    print("\nEjecutando análisis de gravedad...")
    ok = ops.analyze(1)

    if ok == 0:
        print("✓ Análisis de gravedad completado exitosamente")
    else:
        print("❌ Error en análisis de gravedad")
        sys.exit(1)

    # -------------------------
    # 7a. EXTRAER RESULTADOS FASE 1
    # -------------------------
    print("\n" + "="*80)
    print("EXTRAYENDO RESULTADOS FASE 1")
    print("="*80)

    # Extraer asentamientos por gravedad
    df_fase1 = utils.extraer_asentamientos(node_coords)
    print(f"✓ {len(df_fase1)} puntos con asentamientos por gravedad extraídos")

    # Renombrar columna para claridad
    df_fase1.rename(columns={'Settlement_mm': 'Settlement_gravedad_mm'}, inplace=True)

    # Estadísticas Fase 1
    s1_max = df_fase1['Settlement_gravedad_mm'].max()
    s1_min = df_fase1['Settlement_gravedad_mm'].min()
    s1_mean = df_fase1['Settlement_gravedad_mm'].mean()

    print(f"\nEstadísticas FASE 1 - Gravedad:")
    print(f"  Asentamiento máximo: {s1_max:.4f} mm")
    print(f"  Asentamiento mínimo: {s1_min:.4f} mm")
    print(f"  Asentamiento promedio: {s1_mean:.4f} mm")

    # Guardar resultados Fase 1
    csv_fase1 = "settlements_fase1_gravedad.csv"
    df_fase1.to_csv(csv_fase1, index=False)
    print(f"✓ Resultados Fase 1 guardados: {csv_fase1}")

    # -------------------------
    # 5b. FASE 2 - CARGA INCREMENTAL
    # -------------------------
    print("\n" + "="*80)
    print("FASE 2: APLICANDO CARGA INCREMENTAL")
    print("="*80)

    # Fijar el estado de gravedad
    print("\nFijando estado de gravedad con loadConst...")
    ops.loadConst('-time', 0.0)
    print("✓ Estado de gravedad fijado")

    # Crear nuevo patrón para carga incremental
    ops.timeSeries('Linear', 2)
    ops.pattern('Plain', 2, 2)

    # Ajustar carga si es modelo 1/4
    P_column = cargas['P_column']
    if usar_cuarto:
        P_column = P_column / 4.0
        print(f"Modelo 1/4: Carga ajustada a {P_column:.2f} kN")

    # La carga de columna es adicional (no incluir peso propio que ya está en gravedad)
    carga_total = P_column

    # Distribuir carga entre nodos del tope de zapata
    if len(zapata_nodes) == 0:
        print("⚠️  Advertencia: No se encontraron nodos en el tope de la zapata")
        print("    Aplicando carga en nodos de superficie dentro de área de zapata")

        # Buscar nodos de superficie en área de zapata
        for nid in surface_nodes:
            coords = node_coords[nid]
            x, y = coords[0], coords[1]
            if (x_min_zapata <= x <= x_max_zapata and
                y_min_zapata <= y <= y_max_zapata):
                zapata_nodes.append(nid)

    if len(zapata_nodes) > 0:
        carga_por_nodo = -carga_total / len(zapata_nodes)  # Negativa (hacia abajo)

        for nid in zapata_nodes:
            ops.load(nid, 0.0, 0.0, carga_por_nodo)

        print(f"✓ Carga incremental aplicada: {carga_total:.2f} kN")
        print(f"  Nodos cargados: {len(zapata_nodes)}")
        print(f"  Carga por nodo: {carga_por_nodo:.4f} kN")
    else:
        print("❌ Error: No se pudieron identificar nodos para aplicar cargas")
        sys.exit(1)

    # Calcular presión total (incluyendo peso propio)
    area_zapata = zapata['B'] * zapata['L']
    if usar_cuarto:
        area_zapata = area_zapata / 4.0

    # Peso propio de zapata
    vol_zapata = (B_modelo / 2) * (L_modelo / 2) * h_zapata
    peso_zapata = vol_zapata * mat_zapata['rho'] * 9.81 / 1000.0  # kN

    presion = (P_column + peso_zapata) / area_zapata
    print(f"  Presión contacto total: {presion:.2f} kPa (columna + peso zapata)")

    # -------------------------
    # 6b. ANÁLISIS FASE 2
    # -------------------------
    print("\n" + "="*80)
    print("EJECUTANDO ANÁLISIS FASE 2 - CARGA INCREMENTAL")
    print("="*80)

    print("Ejecutando análisis de carga incremental...")
    ok = ops.analyze(1)

    if ok == 0:
        print("✓ Análisis de carga incremental completado exitosamente")
    else:
        print("❌ Error en análisis de carga incremental")
        sys.exit(1)

    # -------------------------
    # 7b. EXTRAER RESULTADOS FASE 2
    # -------------------------
    print("\n" + "="*80)
    print("EXTRAYENDO RESULTADOS FASE 2")
    print("="*80)

    # Extraer asentamientos TOTALES (gravedad + carga)
    df_total_temp = utils.extraer_asentamientos(node_coords)

    # Los desplazamientos actuales son la suma de ambas fases
    # Para obtener solo la contribución de la carga, restar fase 1
    df_fase2 = df_total_temp.copy()
    df_fase2['Settlement_carga_mm'] = df_total_temp['Settlement_mm'] - df_fase1['Settlement_gravedad_mm']
    df_fase2 = df_fase2[['X', 'Y', 'Z', 'Settlement_carga_mm']]

    print(f"✓ {len(df_fase2)} puntos con asentamientos por carga extraídos")

    # Estadísticas Fase 2
    s2_max = df_fase2['Settlement_carga_mm'].max()
    s2_min = df_fase2['Settlement_carga_mm'].min()
    s2_mean = df_fase2['Settlement_carga_mm'].mean()

    print(f"\nEstadísticas FASE 2 - Carga incremental:")
    print(f"  Asentamiento máximo: {s2_max:.4f} mm")
    print(f"  Asentamiento mínimo: {s2_min:.4f} mm")
    print(f"  Asentamiento promedio: {s2_mean:.4f} mm")

    # Guardar resultados Fase 2
    csv_fase2 = "settlements_fase2_incremental.csv"
    df_fase2.to_csv(csv_fase2, index=False)
    print(f"✓ Resultados Fase 2 guardados: {csv_fase2}")

    # -------------------------
    # 7c. COMBINAR RESULTADOS
    # -------------------------
    print("\n" + "="*80)
    print("COMBINANDO RESULTADOS DE AMBAS FASES")
    print("="*80)

    # Crear DataFrame combinado
    df_settlements = pd.DataFrame({
        'X': df_fase1['X'],
        'Y': df_fase1['Y'],
        'Z': df_fase1['Z'],
        'Settlement_gravedad_mm': df_fase1['Settlement_gravedad_mm'],
        'Settlement_carga_mm': df_fase2['Settlement_carga_mm'],
        'Settlement_total_mm': df_fase1['Settlement_gravedad_mm'] + df_fase2['Settlement_carga_mm']
    })

    # Estadísticas totales
    df_surface = df_settlements[df_settlements['Z'] == df_settlements['Z'].max()]

    s_max = df_surface['Settlement_total_mm'].max()
    s_min = df_surface['Settlement_total_mm'].min()
    s_mean = df_surface['Settlement_total_mm'].mean()
    s_std = df_surface['Settlement_total_mm'].std()
    s_diff = s_max - s_min

    print(f"\nEstadísticas TOTALES (gravedad + carga) en superficie:")
    print(f"  Máximo: {s_max:.4f} mm")
    print(f"  Mínimo: {s_min:.4f} mm")
    print(f"  Promedio: {s_mean:.4f} mm")
    print(f"  Desv. estándar: {s_std:.4f} mm")
    print(f"  Diferencial: {s_diff:.4f} mm")

    # Verificar criterios
    print("\nVerificación de criterios:")
    criterios = config.CRITERIOS

    if s_max > criterios['asentamiento_maximo_admisible']:
        print(f"  ⚠️  Asentamiento máximo {s_max:.2f} mm > {criterios['asentamiento_maximo_admisible']} mm (REVISAR)")
    else:
        print(f"  ✓ Asentamiento máximo OK ({s_max:.2f} mm < {criterios['asentamiento_maximo_admisible']} mm)")

    rel_diff = s_diff / s_max if s_max > 0 else 0
    if rel_diff > criterios['asentamiento_diferencial_admisible']:
        print(f"  ⚠️  Diferencial {rel_diff:.4f} > {criterios['asentamiento_diferencial_admisible']} (REVISAR)")
    else:
        print(f"  ✓ Asentamiento diferencial OK ({rel_diff:.4f} < {criterios['asentamiento_diferencial_admisible']})")

    # -------------------------
    # 8. GUARDAR RESULTADOS
    # -------------------------
    print("\n" + "="*80)
    print("PASO 8: GUARDANDO RESULTADOS")
    print("="*80)

    # Guardar CSV combinado
    if salida['guardar_csv']:
        csv_file_combined = "settlements_total.csv"
        df_settlements.to_csv(csv_file_combined, index=False)
        print(f"✓ Asentamientos totales (ambas fases) guardados: {csv_file_combined}")

        csv_surface_file = salida['csv_surface']
        df_surface.to_csv(csv_surface_file, index=False)
        print(f"✓ Asentamientos superficie guardados: {csv_surface_file}")

    # Exportar a VTU para ParaView (con resultados de ambas fases)
    print("\nGenerando archivo VTU para ParaView...")
    try:
        # Crear nuevo grid con solo los nodos únicos (después de fusión)
        # Extraer coordenadas de nodos únicos
        unique_points = np.zeros((len(node_coords), 3))
        node_id_to_idx = {}  # Mapeo de node_id (OpenSees) a índice en unique_points

        for idx, nid in enumerate(sorted(node_coords.keys())):
            unique_points[idx] = node_coords[nid]
            node_id_to_idx[nid] = idx

        # Reconstruir conectividad de elementos con nodos únicos
        new_cells = []
        new_material_ids = []

        element_id = 1
        cell_idx = 0

        while cell_idx < len(cells):
            n_points = cells[cell_idx]
            if n_points != 4:
                cell_idx += n_points + 1
                continue

            # Obtener índices originales
            idx1 = int(cells[cell_idx + 1])
            idx2 = int(cells[cell_idx + 2])
            idx3 = int(cells[cell_idx + 3])
            idx4 = int(cells[cell_idx + 4])

            # Mapear a IDs de OpenSees (con fusión)
            n1 = node_mapping[idx1]
            n2 = node_mapping[idx2]
            n3 = node_mapping[idx3]
            n4 = node_mapping[idx4]

            # Convertir a índices en unique_points
            new_idx1 = node_id_to_idx[n1]
            new_idx2 = node_id_to_idx[n2]
            new_idx3 = node_id_to_idx[n3]
            new_idx4 = node_id_to_idx[n4]

            # Agregar celda
            new_cells.extend([4, new_idx1, new_idx2, new_idx3, new_idx4])

            # Material
            mat_id = int(material_ids[element_id - 1])
            new_material_ids.append(mat_id)

            element_id += 1
            cell_idx += n_points + 1

        # Crear UnstructuredGrid con nodos únicos
        celltypes = [pv.CellType.TETRA] * len(new_material_ids)
        result_grid = pv.UnstructuredGrid(new_cells, celltypes, unique_points)
        result_grid.cell_data['dominio'] = np.array(new_material_ids)

        # Extraer desplazamientos TOTALES de todos los nodos desde OpenSees
        displacements = np.zeros((len(node_coords), 3))
        settlement_grav_array = np.zeros(len(node_coords))
        settlement_carga_array = np.zeros(len(node_coords))
        settlement_total_mm = np.zeros(len(node_coords))

        for idx, nid in enumerate(sorted(node_coords.keys())):
            disp = ops.nodeDisp(nid)
            displacements[idx] = disp
            settlement_total_mm[idx] = -disp[2] * 1000.0  # Convertir a mm (negativo = asentamiento)

            # Buscar en el dataframe
            coords = node_coords[nid]
            match = df_settlements[(abs(df_settlements['X'] - coords[0]) < 1e-6) &
                                   (abs(df_settlements['Y'] - coords[1]) < 1e-6) &
                                   (abs(df_settlements['Z'] - coords[2]) < 1e-6)]
            if len(match) > 0:
                settlement_grav_array[idx] = match.iloc[0]['Settlement_gravedad_mm']
                settlement_carga_array[idx] = match.iloc[0]['Settlement_carga_mm']

        # Agregar datos de punto
        result_grid.point_data['Displacement_X_m'] = displacements[:, 0]
        result_grid.point_data['Displacement_Y_m'] = displacements[:, 1]
        result_grid.point_data['Displacement_Z_m'] = displacements[:, 2]
        result_grid.point_data['Settlement_gravedad_mm'] = settlement_grav_array
        result_grid.point_data['Settlement_carga_mm'] = settlement_carga_array
        result_grid.point_data['Settlement_total_mm'] = settlement_total_mm
        result_grid.point_data['Displacement_Magnitude_m'] = np.linalg.norm(displacements, axis=1)

        # Guardar archivo VTU
        vtu_file = 'resultados_2phases.vtu'
        result_grid.save(vtu_file)
        print(f"✓ Archivo VTU generado: {vtu_file}")
        print(f"  Nodos: {len(unique_points)}, Elementos: {len(new_material_ids)}")
        print(f"  Para visualizar: paraview {vtu_file}")
    except Exception as e:
        print(f"⚠️  Error al generar VTU: {e}")
        import traceback
        traceback.print_exc()

    # Generar reporte especial para análisis en 2 fases
    if salida['generar_reporte']:
        # Descripción de estratos para reporte
        estratos_desc = ', '.join([f"{e['nombre']} (E={e['E']/1000:.0f} MPa, h={e['espesor']}m)"
                                   for e in estratos_suelo])

        # Reporte personalizado para análisis en 2 fases
        reporte_file = "analysis_summary_2phases.txt"
        with open(reporte_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("REPORTE DE ANÁLISIS DE ZAPATA - 2 FASES\n")
            f.write("="*80 + "\n\n")

            f.write("MODELO:\n")
            f.write(f"  Zapata: {zapata['B']}m × {zapata['L']}m × {zapata['h']}m\n")
            f.write(f"  Dominio: {Lx}m × {Ly}m × {Lz}m\n")
            f.write(f"  Modelo: {'Cuarto con simetría' if usar_cuarto else 'Completo'}\n")
            f.write(f"  Malla: GMSH Tetraédrica\n")
            f.write(f"  Elementos: {total_elements} elementos tetraédricos\n")
            f.write(f"  Nodos: {len(node_coords)}\n")
            f.write(f"  Estratos suelo: {estratos_desc}\n")
            f.write(f"  Material zapata: E={mat_zapata['E']/1000:.0f} MPa (concreto rígido)\n")
            f.write(f"  Peso total modelo: {total_weight:.2f} kN\n\n")

            f.write("="*80 + "\n")
            f.write("FASE 1 - GRAVEDAD\n")
            f.write("="*80 + "\n")
            f.write(f"  Tipo: Campo de tensiones por peso propio\n")
            f.write(f"  Asentamiento máximo: {s1_max:.4f} mm\n")
            f.write(f"  Asentamiento mínimo: {s1_min:.4f} mm\n")
            f.write(f"  Asentamiento promedio: {s1_mean:.4f} mm\n\n")

            f.write("="*80 + "\n")
            f.write("FASE 2 - CARGA INCREMENTAL\n")
            f.write("="*80 + "\n")
            f.write(f"  Tipo: Carga de columna\n")
            f.write(f"  Carga aplicada: {P_column:.2f} kN\n")
            f.write(f"  Presión contacto: {presion:.2f} kPa\n")
            f.write(f"  Asentamiento máximo: {s2_max:.4f} mm\n")
            f.write(f"  Asentamiento mínimo: {s2_min:.4f} mm\n")
            f.write(f"  Asentamiento promedio: {s2_mean:.4f} mm\n\n")

            f.write("="*80 + "\n")
            f.write("RESULTADOS TOTALES (FASE 1 + FASE 2)\n")
            f.write("="*80 + "\n")
            f.write(f"  Asentamiento máximo: {s_max:.4f} mm\n")
            f.write(f"  Asentamiento mínimo: {s_min:.4f} mm\n")
            f.write(f"  Asentamiento promedio: {s_mean:.4f} mm\n")
            f.write(f"  Desviación estándar: {s_std:.4f} mm\n")
            f.write(f"  Diferencial: {s_diff:.4f} mm\n")
            f.write(f"  Relación diferencial: {rel_diff:.4f}\n\n")

            f.write("="*80 + "\n\n")

        print(f"✓ Reporte de 2 fases generado: {reporte_file}")

    # -------------------------
    # 9. GENERAR VISUALIZACIONES
    # -------------------------
    if salida['generar_graficas']:
        print("\n" + "="*80)
        print("PASO 9: GENERANDO VISUALIZACIONES")
        print("="*80)

        # Ejecutar visualizador definitivo
        print("\nEjecutando visualizador completo...")
        try:
            import subprocess
            result = subprocess.run(['python', 'visualize_zapata.py'],
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print("✓ Visualización completa generada: modelo_quarter_isometrico_graded.png")
            else:
                print("⚠️  Error al generar visualización completa")
                if result.stderr:
                    print(f"   {result.stderr[:200]}")
        except Exception as e:
            print(f"⚠️  No se pudo ejecutar visualize_zapata.py: {e}")

    # -------------------------
    # 10. RESUMEN FINAL
    # -------------------------
    print("\n" + "="*80)
    print("ANÁLISIS EN 2 FASES COMPLETADO EXITOSAMENTE")
    print("="*80)
    print(f"\nTiempo: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nArchivos generados:")
    print(f"\n  Resultados por fase:")
    print(f"  • settlements_fase1_gravedad.csv (asentamientos por gravedad)")
    print(f"  • settlements_fase2_incremental.csv (asentamientos por carga)")
    print(f"  • settlements_total.csv (combinado con ambas fases)")
    if salida['guardar_csv']:
        print(f"  • {salida['csv_surface']} (superficie)")
    print(f"\n  Visualización:")
    print(f"  • resultados_2phases.vtu (ParaView - con campos por fase)")
    if salida['generar_reporte']:
        print(f"\n  Reportes:")
        print(f"  • analysis_summary_2phases.txt")
    if salida['generar_graficas']:
        print(f"\n  Gráficas:")
        print(f"  • modelo_quarter_isometrico_graded.png (visualización completa)")

    print("\n" + "="*80 + "\n")


# ===================================================================================
# EJECUTAR
# ===================================================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Análisis interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error durante el análisis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
