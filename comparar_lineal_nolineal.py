#!/usr/bin/env python3
"""
Script para comparar modelo lineal (elástico) vs no lineal (Drucker-Prager)
Genera gráfica comparativa de carga-desplazamiento
"""

import openseespy.opensees as ops
import numpy as np
import json
import matplotlib.pyplot as plt
from datetime import datetime
import os

def ejecutar_modelo(usar_drucker_prager=False):
    """Ejecuta modelo y retorna historia carga-desplazamiento"""

    # Limpiar modelo anterior
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 3)

    # Cargar configuración
    with open('config_zapata.json', 'r') as f:
        config = json.load(f)

    print(f"\n{'='*60}")
    if usar_drucker_prager:
        print("EJECUTANDO MODELO NO LINEAL (DRUCKER-PRAGER)")
    else:
        print("EJECUTANDO MODELO LINEAL (ELÁSTICO)")
    print('='*60)

    # Importar la clase del modelo
    from opensees_zapata_3d_nolineal import ModeloZapata3DNoLineal

    # Crear modelo
    modelo = ModeloZapata3DNoLineal()

    # Inicializar
    modelo.inicializar_modelo()

    # Definir materiales
    geom_zap = config['geometria']['zapata']
    prof_desp = config['geometria']['profundidad_desplante']
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
            # Parámetros de Drucker-Prager
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
            # Elástico
            ops.nDMaterial('ElasticIsotropic', mat_id, E, nu, rho)
            print(f"  ✓ Material {mat_id}: {capa['nombre']} - ElasticIsotropic")

        capa['mat_id'] = mat_id
        mat_id += 1

    # Crear malla
    modelo.config = config
    modelo.crear_malla_unificada()
    modelo.crear_elementos()
    modelo.aplicar_condiciones_frontera()
    modelo.aplicar_cargas()

    # Análisis
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Transformation')

    if usar_drucker_prager:
        ops.test('NormDispIncr', 1.0e-2, 100, 0)
        incremento = 0.1
    else:
        ops.test('NormDispIncr', 1.0e-6, 50, 0)
        incremento = 0.1

    ops.algorithm('Newton')
    ops.integrator('LoadControl', incremento)
    ops.analysis('Static')

    # Nodo central en la base
    i_central = modelo.nx_zap // 2
    j_central = modelo.ny_zap // 2
    nodo_base_central = modelo.nodos['zapata'][(i_central, j_central, 0)]

    P_total = config['cargas']['carga_vertical']

    # Ejecutar análisis
    num_pasos = 10
    historia_carga = []
    historia_despl = []

    print(f"\n  Ejecutando análisis ({num_pasos} pasos)...")
    for step in range(num_pasos):
        ok = ops.analyze(1)

        if ok == 0:
            factor_carga = (step + 1) * incremento
            carga_actual = P_total * factor_carga / 1000  # kN
            despl = ops.nodeDisp(nodo_base_central)[2] * 1000  # mm

            historia_carga.append(carga_actual)
            historia_despl.append(despl)

            if (step + 1) % 2 == 0:
                print(f"    Paso {step+1}/{num_pasos}: ✓")
        else:
            # Intentar con ModifiedNewton
            ops.algorithm('ModifiedNewton', '-initial')
            ok = ops.analyze(1)
            if ok == 0:
                factor_carga = (step + 1) * incremento
                carga_actual = P_total * factor_carga / 1000
                despl = ops.nodeDisp(nodo_base_central)[2] * 1000

                historia_carga.append(carga_actual)
                historia_despl.append(despl)

                print(f"    Paso {step+1}/{num_pasos}: ✓ (ModifiedNewton)")
                ops.algorithm('Newton')
            else:
                print(f"    Paso {step+1}/{num_pasos}: ✗ No convergió")
                break

    print(f"  ✓ Análisis completado: {len(historia_carga)}/{num_pasos} pasos")

    return historia_carga, historia_despl


def graficar_comparacion(carga_lineal, despl_lineal, carga_nolineal, despl_nolineal):
    """Genera gráfica comparativa"""

    print(f"\n{'='*60}")
    print("GENERANDO GRÁFICA COMPARATIVA")
    print('='*60)

    plt.figure(figsize=(12, 7))

    # Curva lineal
    plt.plot(despl_lineal, carga_lineal, 'b-o', linewidth=2, markersize=6,
             label='Modelo Lineal (Elástico)')

    # Curva no lineal
    plt.plot(despl_nolineal, carga_nolineal, 'r-s', linewidth=2, markersize=6,
             label='Modelo No Lineal (Drucker-Prager)')

    plt.xlabel('Desplazamiento vertical (mm)', fontsize=12)
    plt.ylabel('Carga vertical (kN)', fontsize=12)
    plt.title('Comparación Modelo Lineal vs No Lineal\nCentro de la Base de la Zapata',
              fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper left', fontsize=11)

    # Información
    info_text = 'Zapata: 2.5×2.5×0.6 m\nSuelo estratificado (3 capas)\nProfundidad Df: 1.5 m'
    plt.text(0.02, 0.98, info_text, transform=plt.gca().transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # Rigideces
    if len(carga_lineal) >= 2:
        K_lineal = (carga_lineal[-1] - carga_lineal[0]) / (despl_lineal[-1] - despl_lineal[0])
        K_nolineal = (carga_nolineal[-1] - carga_nolineal[0]) / (despl_nolineal[-1] - despl_nolineal[0])

        rigidez_text = f'Rigidez Lineal: {K_lineal:.2f} kN/mm\nRigidez No Lineal: {K_nolineal:.2f} kN/mm'
        plt.text(0.98, 0.02, rigidez_text, transform=plt.gca().transAxes,
                fontsize=10, horizontalalignment='right', verticalalignment='bottom',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))

    plt.tight_layout()

    # Guardar
    os.makedirs('resultados', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = os.path.join('resultados', f'comparacion_lineal_nolineal_{timestamp}.png')
    plt.savefig(archivo, dpi=300, bbox_inches='tight')
    print(f"\n  ✓ Gráfica guardada en: {archivo}")

    plt.close()

    return archivo


if __name__ == '__main__':
    print("\n" + "#"*60)
    print("# COMPARACIÓN MODELO LINEAL VS NO LINEAL")
    print("#"*60)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Ejecutar modelo lineal
    carga_lineal, despl_lineal = ejecutar_modelo(usar_drucker_prager=False)

    # Ejecutar modelo no lineal
    carga_nolineal, despl_nolineal = ejecutar_modelo(usar_drucker_prager=True)

    # Generar gráfica comparativa
    archivo = graficar_comparacion(carga_lineal, despl_lineal,
                                    carga_nolineal, despl_nolineal)

    print(f"\n{'='*60}")
    print("COMPARACIÓN COMPLETADA")
    print('='*60)
    print(f"\nGráfica disponible en: {archivo}")
