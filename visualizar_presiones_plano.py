#!/usr/bin/env python3
"""
Visualización de contornos de presión en plano vertical
que pasa por el centro de la zapata
"""

import openseespy.opensees as ops
import numpy as np
import json
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from datetime import datetime
import os


def ejecutar_y_extraer_esfuerzos(usar_drucker_prager=True):
    """Ejecuta modelo y extrae esfuerzos de todos los elementos"""

    # Limpiar modelo
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 3)

    # Cargar configuración
    with open('config_zapata.json', 'r') as f:
        config = json.load(f)

    print(f"\n{'='*70}")
    if usar_drucker_prager:
        print("EJECUTANDO MODELO DRUCKER-PRAGER PARA EXTRACCIÓN DE ESFUERZOS")
    else:
        print("EJECUTANDO MODELO ELÁSTICO PARA EXTRACCIÓN DE ESFUERZOS")
    print('='*70)

    # Importar y crear modelo
    from opensees_zapata_3d_nolineal import ModeloZapata3DNoLineal

    modelo = ModeloZapata3DNoLineal()
    modelo.inicializar_modelo()

    # Definir materiales
    geom_zap = config['geometria']['zapata']
    capas = config['suelo_estratificado']['capas']

    # Material concreto
    E_conc = config['materiales']['concreto_zapata']['E']
    nu_conc = config['materiales']['concreto_zapata']['nu']
    rho_conc = config['materiales']['concreto_zapata']['densidad']
    ops.nDMaterial('ElasticIsotropic', 1, E_conc, nu_conc, rho_conc)

    # Material relleno
    E_lleno = config['materiales']['lleno']['E']
    nu_lleno = config['materiales']['lleno']['nu']
    rho_lleno = config['materiales']['lleno']['densidad']
    ops.nDMaterial('ElasticIsotropic', 2, E_lleno, nu_lleno, rho_lleno)

    # Materiales de suelo
    mat_id = 10
    for i, capa in enumerate(capas, 1):
        E = capa['E']
        nu = capa['nu']
        rho = capa['densidad']

        if usar_drucker_prager:
            G = E / (2 * (1 + nu))
            K = E / (3 * (1 - 2*nu))

            cohesion = capa.get('cohesion', 10000)
            phi_grados = capa.get('friccion_grados', 30)
            phi = phi_grados * np.pi / 180

            sin_phi = np.sin(phi)
            rho_bar = (2 * np.sqrt(6) * sin_phi) / (3 - sin_phi)

            sigma_y = max(cohesion, 1000)
            Kinf = sigma_y * 1.2
            Ko = 0.0
            delta1 = 0.0
            delta2 = 0.0
            H = 0.001 * G
            theta = 0.0
            atm = 101325.0

            try:
                ops.nDMaterial('DruckerPrager', mat_id, K, G, sigma_y, rho,
                              rho_bar, Kinf, Ko, delta1, delta2, H, theta, rho, atm)
                print(f"  ✓ Material {mat_id}: {capa['nombre']} - DruckerPrager")
            except:
                ops.nDMaterial('ElasticIsotropic', mat_id, E, nu, rho)
                print(f"  ⚠ Material {mat_id}: {capa['nombre']} - ElasticIsotropic (fallback)")
        else:
            ops.nDMaterial('ElasticIsotropic', mat_id, E, nu, rho)
            print(f"  ✓ Material {mat_id}: {capa['nombre']} - ElasticIsotropic")

        capa['mat_id'] = mat_id
        mat_id += 1

    # Crear malla y elementos
    modelo.config = config
    modelo.crear_malla_unificada()
    modelo.crear_elementos()
    modelo.aplicar_condiciones_frontera()
    modelo.aplicar_cargas()

    # Configurar análisis
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Transformation')

    if usar_drucker_prager:
        ops.test('NormDispIncr', 1.0e-2, 100, 0)
        ops.algorithm('Newton')
        ops.integrator('LoadControl', 0.1)
    else:
        ops.test('NormDispIncr', 1.0e-6, 50, 0)
        ops.algorithm('Newton')
        ops.integrator('LoadControl', 0.1)

    ops.analysis('Static')

    # Ejecutar análisis hasta carga completa
    print(f"\n  Ejecutando análisis...")
    pasos_completados = 0
    for step in range(10):
        ok = ops.analyze(1)
        if ok == 0:
            pasos_completados += 1
        else:
            # Intentar con ModifiedNewton
            ops.algorithm('ModifiedNewton', '-initial')
            ok = ops.analyze(1)
            if ok == 0:
                pasos_completados += 1
            else:
                print(f"  ✗ Fallo en paso {step+1}")
                break
            ops.algorithm('Newton')

    print(f"  ✓ Análisis completado: {pasos_completados}/10 pasos")

    # Extraer información de nodos y elementos
    print(f"\n  Extrayendo esfuerzos de elementos...")

    elementos_info = []

    # Extraer información del modelo
    nx_suelo = modelo.nx_suelo
    ny_suelo = modelo.ny_suelo
    nz_suelo = modelo.nz_suelo
    nx_zap = modelo.nx_zap
    ny_zap = modelo.ny_zap
    nz_zap = modelo.nz_zap

    # Recorrer elementos del suelo
    for key, elem_tag in modelo.elementos['suelo'].items():
        i, j, k, capa_idx = key

        # Obtener nodos del elemento para calcular centroide
        nodos_elem = []
        for di in [0, 1]:
            for dj in [0, 1]:
                for dk in [0, 1]:
                    nodo_tag = modelo.nodos['suelo'][(i+di, j+dj, k+dk)]
                    coord = ops.nodeCoord(nodo_tag)
                    nodos_elem.append(coord)

        # Calcular centroide
        centroide = np.mean(nodos_elem, axis=0)
        x_c, y_c, z_c = centroide

        # Intentar obtener esfuerzos del elemento
        try:
            # Para elementos brick, los esfuerzos suelen estar en los puntos de Gauss
            # Intentamos obtener respuesta del material
            stress = ops.eleResponse(elem_tag, 'material', '1', 'stress')

            if stress and len(stress) >= 6:
                # stress = [σxx, σyy, σzz, τxy, τyz, τzx]
                sigma_xx = stress[0]
                sigma_yy = stress[1]
                sigma_zz = stress[2]
                tau_xy = stress[3]
                tau_yz = stress[4]
                tau_zx = stress[5]

                # Presión media (positiva en compresión)
                p_mean = -(sigma_xx + sigma_yy + sigma_zz) / 3.0

                # Esfuerzo vertical (positivo en compresión)
                sigma_v = -sigma_zz

                # Esfuerzo desviador (Von Mises)
                s_xx = sigma_xx + p_mean
                s_yy = sigma_yy + p_mean
                s_zz = sigma_zz + p_mean
                q = np.sqrt(0.5 * (s_xx**2 + s_yy**2 + s_zz**2 +
                                   2*(tau_xy**2 + tau_yz**2 + tau_zx**2)))

                elementos_info.append({
                    'tag': elem_tag,
                    'tipo': 'suelo',
                    'i': i, 'j': j, 'k': k,
                    'x': x_c, 'y': y_c, 'z': z_c,
                    'sigma_xx': sigma_xx,
                    'sigma_yy': sigma_yy,
                    'sigma_zz': sigma_zz,
                    'sigma_v': sigma_v,
                    'p_mean': p_mean,
                    'q': q
                })
        except:
            # Si no se pueden obtener esfuerzos, guardar con valores nulos
            elementos_info.append({
                'tag': elem_tag,
                'tipo': 'suelo',
                'i': i, 'j': j, 'k': k,
                'x': x_c, 'y': y_c, 'z': z_c,
                'sigma_v': 0.0,
                'p_mean': 0.0,
                'q': 0.0
            })

    # Elementos de zapata
    for key, elem_tag in modelo.elementos['zapata'].items():
        i, j, k = key

        # Obtener nodos del elemento para calcular centroide
        nodos_elem = []
        for di in [0, 1]:
            for dj in [0, 1]:
                for dk in [0, 1]:
                    if (i+di, j+dj, k+dk) in modelo.nodos['zapata']:
                        nodo_tag = modelo.nodos['zapata'][(i+di, j+dj, k+dk)]
                        coord = ops.nodeCoord(nodo_tag)
                        nodos_elem.append(coord)

        if len(nodos_elem) == 8:
            centroide = np.mean(nodos_elem, axis=0)
            x_c, y_c, z_c = centroide

            try:
                stress = ops.eleResponse(elem_tag, 'material', '1', 'stress')
                if stress and len(stress) >= 6:
                    sigma_xx = stress[0]
                    sigma_yy = stress[1]
                    sigma_zz = stress[2]

                    p_mean = -(sigma_xx + sigma_yy + sigma_zz) / 3.0
                    sigma_v = -sigma_zz

                    elementos_info.append({
                        'tag': elem_tag,
                        'tipo': 'zapata',
                        'i': i, 'j': j, 'k': k,
                        'x': x_c, 'y': y_c, 'z': z_c,
                        'sigma_v': sigma_v,
                        'p_mean': p_mean,
                        'q': 0.0
                    })
            except:
                elementos_info.append({
                    'tag': elem_tag,
                    'tipo': 'zapata',
                    'i': i, 'j': j, 'k': k,
                    'x': x_c, 'y': y_c, 'z': z_c,
                    'sigma_v': 0.0,
                    'p_mean': 0.0,
                    'q': 0.0
                })

    print(f"  ✓ Extraídos {len(elementos_info)} elementos")

    # Extraer geometría de la zapata
    B_x = config['geometria']['zapata']['B_x']
    B_y = config['geometria']['zapata']['B_y']
    h_zap = config['geometria']['zapata']['h']
    prof_desp = config['geometria']['profundidad_desplante']

    z_superficie = 0.0
    z_base_zapata = -prof_desp
    z_tope_zapata = z_base_zapata + h_zap

    geom_zapata = {
        'B_x': B_x,
        'B_y': B_y,
        'h': h_zap,
        'z_tope': z_tope_zapata,
        'z_base': z_base_zapata
    }

    return elementos_info, geom_zapata, modelo


def crear_contorno_plano_xz(elementos_info, geom_zapata, variable='sigma_v'):
    """Crea contorno de esfuerzos en plano X-Z (Y=0, centro)"""

    print(f"\n{'='*70}")
    print(f"CREANDO CONTORNO DE {variable.upper()} EN PLANO X-Z (Y=0)")
    print('='*70)

    # Filtrar elementos cerca del plano Y=0 (±0.5 m de tolerancia)
    tol_y = 0.5
    elementos_plano = [e for e in elementos_info if abs(e['y']) <= tol_y]

    print(f"  Elementos en plano Y=0 (±{tol_y}m): {len(elementos_plano)}")

    if len(elementos_plano) == 0:
        print("  ⚠ No hay elementos en el plano central")
        return None

    # Extraer coordenadas y valores
    x_vals = np.array([e['x'] for e in elementos_plano])
    z_vals = np.array([e['z'] for e in elementos_plano])
    stress_vals = np.array([e[variable] for e in elementos_plano])

    # Convertir a kPa
    stress_vals = stress_vals / 1000.0

    print(f"  Rango X: [{x_vals.min():.2f}, {x_vals.max():.2f}] m")
    print(f"  Rango Z: [{z_vals.min():.2f}, {z_vals.max():.2f}] m")
    print(f"  Rango {variable}: [{stress_vals.min():.1f}, {stress_vals.max():.1f}] kPa")

    # Crear grid regular para interpolación
    x_min, x_max = x_vals.min(), x_vals.max()
    z_min, z_max = z_vals.min(), z_vals.max()

    nx_grid = 100
    nz_grid = 150

    x_grid = np.linspace(x_min, x_max, nx_grid)
    z_grid = np.linspace(z_min, z_max, nz_grid)
    X_grid, Z_grid = np.meshgrid(x_grid, z_grid)

    # Interpolar valores
    from scipy.interpolate import griddata

    points = np.column_stack([x_vals, z_vals])
    Stress_grid = griddata(points, stress_vals, (X_grid, Z_grid), method='cubic')

    # Reemplazar NaN con interpolación lineal
    mask_nan = np.isnan(Stress_grid)
    if mask_nan.any():
        Stress_grid_lin = griddata(points, stress_vals, (X_grid, Z_grid), method='linear')
        Stress_grid[mask_nan] = Stress_grid_lin[mask_nan]

    # Crear figura
    fig, ax = plt.subplots(figsize=(14, 10))

    # Definir colormap (azul para bajo esfuerzo, rojo para alto)
    colors_list = ['#0000ff', '#4169e1', '#87ceeb', '#90ee90',
                   '#ffff00', '#ffa500', '#ff4500', '#8b0000']
    n_bins = 100
    cmap = LinearSegmentedColormap.from_list('stress', colors_list, N=n_bins)

    # Niveles de contorno
    levels = np.linspace(stress_vals.min(), stress_vals.max(), 30)

    # Contour plot relleno
    contourf = ax.contourf(X_grid, Z_grid, Stress_grid, levels=levels,
                          cmap=cmap, extend='both')

    # Contour lines
    contour = ax.contour(X_grid, Z_grid, Stress_grid, levels=10,
                        colors='black', linewidths=0.5, alpha=0.4)
    ax.clabel(contour, inline=True, fontsize=8, fmt='%0.0f')

    # Colorbar
    cbar = plt.colorbar(contourf, ax=ax, orientation='vertical', pad=0.02)

    if variable == 'sigma_v':
        cbar.set_label('Esfuerzo Vertical σ_v (kPa)\n(+: Compresión)',
                      fontsize=11, fontweight='bold')
    elif variable == 'p_mean':
        cbar.set_label('Presión Media p (kPa)\n(+: Compresión)',
                      fontsize=11, fontweight='bold')
    elif variable == 'q':
        cbar.set_label('Esfuerzo Desviador q (kPa)',
                      fontsize=11, fontweight='bold')

    # Dibujar zapata
    B_x = geom_zapata['B_x']
    z_tope = geom_zapata['z_tope']
    z_base = geom_zapata['z_base']

    # Rectángulo de la zapata
    from matplotlib.patches import Rectangle
    zapata_rect = Rectangle((-B_x/2, z_base), B_x, z_base - z_tope,
                           linewidth=3, edgecolor='black', facecolor='gray',
                           alpha=0.3, label='Zapata')
    ax.add_patch(zapata_rect)

    # Línea de superficie del suelo
    ax.axhline(y=z_tope, color='brown', linestyle='--', linewidth=2,
              alpha=0.7, label='Superficie del suelo')

    # Configuración de ejes
    ax.set_xlabel('Coordenada X (m)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Profundidad Z (m)', fontsize=12, fontweight='bold')
    ax.set_title(f'Contorno de Esfuerzos en Plano Vertical X-Z (Y=0)\n' +
                f'Centro de la Zapata - Variable: {variable}',
                fontsize=13, fontweight='bold', pad=15)

    ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
    ax.set_aspect('equal')
    ax.legend(loc='lower right', fontsize=10)

    # Agregar anotaciones
    info_text = (f"Presión aplicada: 500 kN / 6.25 m² ≈ 80 kPa\n"
                f"Rango de esfuerzos: {stress_vals.min():.0f} - {stress_vals.max():.0f} kPa")
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
           fontsize=9, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    plt.tight_layout()

    return fig


def crear_contorno_plano_yz(elementos_info, geom_zapata, variable='sigma_v'):
    """Crea contorno de esfuerzos en plano Y-Z (X=0, centro)"""

    print(f"\n{'='*70}")
    print(f"CREANDO CONTORNO DE {variable.upper()} EN PLANO Y-Z (X=0)")
    print('='*70)

    # Filtrar elementos cerca del plano X=0
    tol_x = 0.5
    elementos_plano = [e for e in elementos_info if abs(e['x']) <= tol_x]

    print(f"  Elementos en plano X=0 (±{tol_x}m): {len(elementos_plano)}")

    if len(elementos_plano) == 0:
        print("  ⚠ No hay elementos en el plano central")
        return None

    # Extraer coordenadas y valores
    y_vals = np.array([e['y'] for e in elementos_plano])
    z_vals = np.array([e['z'] for e in elementos_plano])
    stress_vals = np.array([e[variable] for e in elementos_plano])

    # Convertir a kPa
    stress_vals = stress_vals / 1000.0

    print(f"  Rango Y: [{y_vals.min():.2f}, {y_vals.max():.2f}] m")
    print(f"  Rango Z: [{z_vals.min():.2f}, {z_vals.max():.2f}] m")
    print(f"  Rango {variable}: [{stress_vals.min():.1f}, {stress_vals.max():.1f}] kPa")

    # Crear grid regular
    y_min, y_max = y_vals.min(), y_vals.max()
    z_min, z_max = z_vals.min(), z_vals.max()

    ny_grid = 100
    nz_grid = 150

    y_grid = np.linspace(y_min, y_max, ny_grid)
    z_grid = np.linspace(z_min, z_max, nz_grid)
    Y_grid, Z_grid = np.meshgrid(y_grid, z_grid)

    # Interpolar
    from scipy.interpolate import griddata

    points = np.column_stack([y_vals, z_vals])
    Stress_grid = griddata(points, stress_vals, (Y_grid, Z_grid), method='cubic')

    # Reemplazar NaN
    mask_nan = np.isnan(Stress_grid)
    if mask_nan.any():
        Stress_grid_lin = griddata(points, stress_vals, (Y_grid, Z_grid), method='linear')
        Stress_grid[mask_nan] = Stress_grid_lin[mask_nan]

    # Crear figura
    fig, ax = plt.subplots(figsize=(14, 10))

    # Colormap
    colors_list = ['#0000ff', '#4169e1', '#87ceeb', '#90ee90',
                   '#ffff00', '#ffa500', '#ff4500', '#8b0000']
    n_bins = 100
    cmap = LinearSegmentedColormap.from_list('stress', colors_list, N=n_bins)

    # Niveles
    levels = np.linspace(stress_vals.min(), stress_vals.max(), 30)

    # Contour plot
    contourf = ax.contourf(Y_grid, Z_grid, Stress_grid, levels=levels,
                          cmap=cmap, extend='both')

    contour = ax.contour(Y_grid, Z_grid, Stress_grid, levels=10,
                        colors='black', linewidths=0.5, alpha=0.4)
    ax.clabel(contour, inline=True, fontsize=8, fmt='%0.0f')

    # Colorbar
    cbar = plt.colorbar(contourf, ax=ax, orientation='vertical', pad=0.02)

    if variable == 'sigma_v':
        cbar.set_label('Esfuerzo Vertical σ_v (kPa)\n(+: Compresión)',
                      fontsize=11, fontweight='bold')
    elif variable == 'p_mean':
        cbar.set_label('Presión Media p (kPa)\n(+: Compresión)',
                      fontsize=11, fontweight='bold')
    elif variable == 'q':
        cbar.set_label('Esfuerzo Desviador q (kPa)',
                      fontsize=11, fontweight='bold')

    # Dibujar zapata
    B_y = geom_zapata['B_y']
    z_tope = geom_zapata['z_tope']
    z_base = geom_zapata['z_base']

    from matplotlib.patches import Rectangle
    zapata_rect = Rectangle((-B_y/2, z_base), B_y, z_base - z_tope,
                           linewidth=3, edgecolor='black', facecolor='gray',
                           alpha=0.3, label='Zapata')
    ax.add_patch(zapata_rect)

    # Superficie
    ax.axhline(y=z_tope, color='brown', linestyle='--', linewidth=2,
              alpha=0.7, label='Superficie del suelo')

    # Configuración
    ax.set_xlabel('Coordenada Y (m)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Profundidad Z (m)', fontsize=12, fontweight='bold')
    ax.set_title(f'Contorno de Esfuerzos en Plano Vertical Y-Z (X=0)\n' +
                f'Centro de la Zapata - Variable: {variable}',
                fontsize=13, fontweight='bold', pad=15)

    ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
    ax.set_aspect('equal')
    ax.legend(loc='lower right', fontsize=10)

    info_text = (f"Presión aplicada: 500 kN / 6.25 m² ≈ 80 kPa\n"
                f"Rango de esfuerzos: {stress_vals.min():.0f} - {stress_vals.max():.0f} kPa")
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
           fontsize=9, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    plt.tight_layout()

    return fig


if __name__ == '__main__':
    print("\n" + "#"*70)
    print("# VISUALIZACIÓN DE CONTORNOS DE PRESIÓN EN PLANO VERTICAL")
    print("#"*70)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Ejecutar modelo y extraer esfuerzos
    print("[1/3] Ejecutando modelo y extrayendo esfuerzos...")
    elementos_info, geom_zapata, modelo = ejecutar_y_extraer_esfuerzos(
        usar_drucker_prager=True)

    # Crear directorio para resultados
    os.makedirs('imagenes', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Crear contornos para diferentes variables
    variables = [
        ('sigma_v', 'Esfuerzo Vertical'),
        ('p_mean', 'Presión Media'),
        ('q', 'Esfuerzo Desviador')
    ]

    archivos_generados = []

    print(f"\n[2/3] Generando contornos en plano X-Z (Y=0)...")
    for var, descripcion in variables:
        print(f"\n  Procesando: {descripcion}")
        fig = crear_contorno_plano_xz(elementos_info, geom_zapata, variable=var)

        if fig:
            archivo = os.path.join('imagenes',
                                  f'contorno_xz_{var}_{timestamp}.png')
            fig.savefig(archivo, dpi=300, bbox_inches='tight')
            print(f"  ✓ Guardado: {archivo}")
            archivos_generados.append(archivo)
            plt.close(fig)

    print(f"\n[3/3] Generando contornos en plano Y-Z (X=0)...")
    for var, descripcion in variables:
        print(f"\n  Procesando: {descripcion}")
        fig = crear_contorno_plano_yz(elementos_info, geom_zapata, variable=var)

        if fig:
            archivo = os.path.join('imagenes',
                                  f'contorno_yz_{var}_{timestamp}.png')
            fig.savefig(archivo, dpi=300, bbox_inches='tight')
            print(f"  ✓ Guardado: {archivo}")
            archivos_generados.append(archivo)
            plt.close(fig)

    print(f"\n{'='*70}")
    print("VISUALIZACIÓN COMPLETADA")
    print('='*70)
    print(f"\nArchivos generados ({len(archivos_generados)}):")
    for archivo in archivos_generados:
        print(f"  - {archivo}")

    print(f"\nLos contornos muestran la distribución de esfuerzos en el suelo")
    print(f"bajo la zapata en los planos verticales centrales X-Z y Y-Z.")
