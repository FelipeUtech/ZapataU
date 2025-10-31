#!/usr/bin/env python3
"""
Script para investigar comportamiento plástico del modelo Drucker-Prager
Verifica si el suelo está cediendo y monitorea estados de esfuerzo
"""

import openseespy.opensees as ops
import numpy as np
import json
import matplotlib.pyplot as plt
from datetime import datetime
import os

def ejecutar_modelo_detallado(usar_drucker_prager=True, num_pasos=50):
    """Ejecuta modelo con monitoreo detallado de esfuerzos"""

    # Limpiar modelo anterior
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 3)

    # Cargar configuración
    with open('config_zapata.json', 'r') as f:
        config = json.load(f)

    print(f"\n{'='*70}")
    if usar_drucker_prager:
        print("ANÁLISIS DETALLADO - MODELO DRUCKER-PRAGER")
    else:
        print("ANÁLISIS DETALLADO - MODELO ELÁSTICO")
    print('='*70)
    print(f"Número de pasos: {num_pasos}")

    # Importar la clase del modelo
    from opensees_zapata_3d_nolineal import ModeloZapata3DNoLineal

    # Crear modelo
    modelo = ModeloZapata3DNoLineal()
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
    parametros_materiales = []

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

            # Guardar parámetros para análisis
            parametros_materiales.append({
                'mat_id': mat_id,
                'nombre': capa['nombre'],
                'sigma_y': sigma_y,
                'rho_bar': rho_bar,
                'K': K,
                'G': G,
                'E': E
            })
        else:
            # Elástico
            ops.nDMaterial('ElasticIsotropic', mat_id, E, nu, rho)
            print(f"  ✓ Material {mat_id}: {capa['nombre']} - ElasticIsotropic")

            parametros_materiales.append({
                'mat_id': mat_id,
                'nombre': capa['nombre'],
                'E': E,
                'nu': nu
            })

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
        incremento = 1.0 / num_pasos
    else:
        ops.test('NormDispIncr', 1.0e-6, 50, 0)
        incremento = 1.0 / num_pasos

    ops.algorithm('Newton')
    ops.integrator('LoadControl', incremento)
    ops.analysis('Static')

    # Nodo central en la base
    i_central = modelo.nx_zap // 2
    j_central = modelo.ny_zap // 2
    nodo_base_central = modelo.nodos['zapata'][(i_central, j_central, 0)]

    P_total = config['cargas']['carga_vertical']

    # Ejecutar análisis
    historia_carga = []
    historia_despl = []

    print(f"\n  Ejecutando análisis ({num_pasos} pasos)...")
    pasos_exitosos = 0

    for step in range(num_pasos):
        ok = ops.analyze(1)

        if ok == 0:
            factor_carga = (step + 1) * incremento
            carga_actual = P_total * factor_carga / 1000  # kN
            despl = ops.nodeDisp(nodo_base_central)[2] * 1000  # mm

            historia_carga.append(carga_actual)
            historia_despl.append(despl)

            pasos_exitosos += 1

            if (step + 1) % 10 == 0:
                print(f"    Paso {step+1}/{num_pasos}: ✓ (Carga: {carga_actual:.1f} kN, Despl: {despl:.3f} mm)")
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

                pasos_exitosos += 1

                if (step + 1) % 10 == 0:
                    print(f"    Paso {step+1}/{num_pasos}: ✓ (ModifiedNewton)")
                ops.algorithm('Newton')
            else:
                print(f"    Paso {step+1}/{num_pasos}: ✗ No convergió")
                break

    print(f"  ✓ Análisis completado: {pasos_exitosos}/{num_pasos} pasos exitosos")

    return historia_carga, historia_despl, parametros_materiales, pasos_exitosos


def analizar_linealidad(carga, despl, nombre_modelo):
    """Analiza qué tan lineal es una curva"""

    print(f"\n{'='*70}")
    print(f"ANÁLISIS DE LINEALIDAD - {nombre_modelo}")
    print('='*70)

    if len(carga) < 3:
        print("  ⚠ Datos insuficientes para análisis")
        return None

    # Calcular rigidez instantánea entre puntos consecutivos
    rigideces = []
    for i in range(1, len(carga)):
        dC = carga[i] - carga[i-1]
        dD = despl[i] - despl[i-1]
        if abs(dD) > 1e-10:
            K_inst = dC / dD
            rigideces.append(K_inst)

    # Rigidez promedio (global)
    K_global = (carga[-1] - carga[0]) / (despl[-1] - despl[0])

    # Calcular desviación de la linealidad
    rigideces_array = np.array(rigideces)
    desviacion_std = np.std(rigideces_array)
    desviacion_rel = (desviacion_std / K_global) * 100  # Porcentaje

    print(f"\n  Rigidez global: {K_global:.2f} kN/mm")
    print(f"  Rigidez instantánea:")
    print(f"    - Mínima: {np.min(rigideces):.2f} kN/mm")
    print(f"    - Máxima: {np.max(rigideces):.2f} kN/mm")
    print(f"    - Promedio: {np.mean(rigideces):.2f} kN/mm")
    print(f"    - Desv. std: {desviacion_std:.2f} kN/mm")
    print(f"\n  Variación de rigidez: {desviacion_rel:.2f}%")

    if desviacion_rel < 1.0:
        print(f"  → Comportamiento MUY LINEAL (variación < 1%)")
    elif desviacion_rel < 5.0:
        print(f"  → Comportamiento APROXIMADAMENTE LINEAL (variación < 5%)")
    elif desviacion_rel < 15.0:
        print(f"  → Comportamiento LEVEMENTE NO LINEAL (variación 5-15%)")
    else:
        print(f"  → Comportamiento CLARAMENTE NO LINEAL (variación > 15%)")

    # Calcular R² para ajuste lineal
    # y = mx + b donde y=carga, x=despl
    coef = np.polyfit(despl, carga, 1)
    carga_ajuste = np.polyval(coef, despl)

    ss_res = np.sum((np.array(carga) - carga_ajuste)**2)
    ss_tot = np.sum((np.array(carga) - np.mean(carga))**2)
    r_squared = 1 - (ss_res / ss_tot)

    print(f"\n  Coeficiente R² (ajuste lineal): {r_squared:.6f}")
    if r_squared > 0.9999:
        print(f"  → Ajuste lineal EXCELENTE (R² > 0.9999)")
    elif r_squared > 0.999:
        print(f"  → Ajuste lineal MUY BUENO (R² > 0.999)")
    else:
        print(f"  → Desviación significativa de comportamiento lineal")

    return {
        'K_global': K_global,
        'rigideces': rigideces,
        'desviacion_rel': desviacion_rel,
        'r_squared': r_squared
    }


def graficar_comparacion_detallada(carga_lineal, despl_lineal,
                                   carga_nolineal, despl_nolineal,
                                   analisis_lineal, analisis_nolineal):
    """Genera gráficas comparativas detalladas"""

    print(f"\n{'='*70}")
    print("GENERANDO GRÁFICAS DETALLADAS")
    print('='*70)

    # Crear figura con 2 subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # ===== SUBPLOT 1: Curvas carga-desplazamiento =====
    ax1.plot(despl_lineal, carga_lineal, 'b-o', linewidth=2, markersize=4,
             label='Modelo Lineal (Elástico)', alpha=0.7)
    ax1.plot(despl_nolineal, carga_nolineal, 'r-s', linewidth=2, markersize=4,
             label='Modelo No Lineal (Drucker-Prager)', alpha=0.7)

    ax1.set_xlabel('Desplazamiento vertical (mm)', fontsize=12)
    ax1.set_ylabel('Carga vertical (kN)', fontsize=12)
    ax1.set_title('Curvas Carga-Desplazamiento\n(50 pasos de análisis)',
                  fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=10)

    # Información de rigidez
    if analisis_lineal and analisis_nolineal:
        info_text = (f"Rigidez Lineal: {analisis_lineal['K_global']:.2f} kN/mm (R²={analisis_lineal['r_squared']:.5f})\n"
                    f"Rigidez No Lineal: {analisis_nolineal['K_global']:.2f} kN/mm (R²={analisis_nolineal['r_squared']:.5f})\n"
                    f"Variación NL: {analisis_nolineal['desviacion_rel']:.2f}%")
        ax1.text(0.98, 0.02, info_text, transform=ax1.transAxes,
                fontsize=9, horizontalalignment='right', verticalalignment='bottom',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))

    # ===== SUBPLOT 2: Rigidez instantánea =====
    if analisis_lineal and analisis_nolineal:
        # Puntos medios para rigidez instantánea
        despl_medio_lin = [(despl_lineal[i] + despl_lineal[i+1])/2
                          for i in range(len(despl_lineal)-1)]
        despl_medio_nl = [(despl_nolineal[i] + despl_nolineal[i+1])/2
                         for i in range(len(despl_nolineal)-1)]

        ax2.plot(despl_medio_lin, analisis_lineal['rigideces'],
                'b-o', linewidth=2, markersize=4, label='Modelo Lineal', alpha=0.7)
        ax2.plot(despl_medio_nl, analisis_nolineal['rigideces'],
                'r-s', linewidth=2, markersize=4, label='Modelo No Lineal', alpha=0.7)

        # Líneas de rigidez global (referencia)
        ax2.axhline(y=analisis_lineal['K_global'], color='b',
                   linestyle='--', alpha=0.3, label=f'K global lineal')
        ax2.axhline(y=analisis_nolineal['K_global'], color='r',
                   linestyle='--', alpha=0.3, label=f'K global no lineal')

        ax2.set_xlabel('Desplazamiento vertical (mm)', fontsize=12)
        ax2.set_ylabel('Rigidez instantánea (kN/mm)', fontsize=12)
        ax2.set_title('Evolución de Rigidez Instantánea\n(Detección de No-Linealidad)',
                     fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='best', fontsize=9)

        # Resaltar si hay cambio significativo
        if analisis_nolineal['desviacion_rel'] > 5.0:
            ax2.text(0.02, 0.98, '⚠ Variación significativa\nen rigidez no lineal',
                    transform=ax2.transAxes,
                    fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))

    plt.tight_layout()

    # Guardar
    os.makedirs('imagenes', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = os.path.join('imagenes', f'analisis_detallado_plasticidad_{timestamp}.png')
    plt.savefig(archivo, dpi=300, bbox_inches='tight')
    print(f"\n  ✓ Gráfica guardada en: {archivo}")

    plt.close()

    return archivo


if __name__ == '__main__':
    print("\n" + "#"*70)
    print("# INVESTIGACIÓN DETALLADA: ¿POR QUÉ LA CURVA NO LINEAL ES LINEAL?")
    print("#"*70)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Ejecutar modelo lineal con más resolución
    print("\n[1/4] Ejecutando modelo LINEAL con 50 pasos...")
    carga_lin, despl_lin, params_lin, pasos_lin = ejecutar_modelo_detallado(
        usar_drucker_prager=False, num_pasos=50)

    # Ejecutar modelo no lineal con más resolución
    print("\n[2/4] Ejecutando modelo NO LINEAL con 50 pasos...")
    carga_nl, despl_nl, params_nl, pasos_nl = ejecutar_modelo_detallado(
        usar_drucker_prager=True, num_pasos=50)

    # Analizar linealidad de ambas curvas
    print("\n[3/4] Analizando linealidad de las curvas...")
    analisis_lin = analizar_linealidad(carga_lin, despl_lin, "MODELO LINEAL")
    analisis_nl = analizar_linealidad(carga_nl, despl_nl, "MODELO NO LINEAL")

    # Generar gráficas
    print("\n[4/4] Generando gráficas comparativas...")
    archivo = graficar_comparacion_detallada(carga_lin, despl_lin,
                                             carga_nl, despl_nl,
                                             analisis_lin, analisis_nl)

    # Resumen y diagnóstico
    print(f"\n{'='*70}")
    print("DIAGNÓSTICO: ¿POR QUÉ LA CURVA NO LINEAL PARECE LINEAL?")
    print('='*70)

    if analisis_nl:
        var_nl = analisis_nl['desviacion_rel']
        r2_nl = analisis_nl['r_squared']

        print(f"\nVariación de rigidez en modelo no lineal: {var_nl:.2f}%")
        print(f"Coeficiente R² (ajuste lineal): {r2_nl:.6f}")

        print(f"\nPOSIBLES RAZONES:")

        if var_nl < 2.0 and r2_nl > 0.9999:
            print("\n1. ✓ CONFIRMADO: La curva es efectivamente muy lineal")
            print("   Esto sugiere que:")
            print("   - Los esfuerzos podrían estar bajo la superficie de fluencia")
            print("   - El material no está cediendo significativamente")
            print("   - El comportamiento es predominantemente elástico")

            # Mostrar parámetros de fluencia
            print(f"\n2. Parámetros de fluencia Drucker-Prager:")
            for param in params_nl:
                if 'sigma_y' in param:
                    print(f"   - {param['nombre']}: σ_y = {param['sigma_y']/1000:.1f} kPa")

            print(f"\n3. Carga aplicada: 500 kN sobre 2.5×2.5 m")
            print(f"   Presión promedio ≈ 80 kPa")
            print(f"   (Comparar con σ_y de cada capa)")

            print(f"\n4. RECOMENDACIONES:")
            print(f"   a) Reducir σ_y (cohesión) para observar plasticidad clara")
            print(f"   b) Aumentar la carga aplicada")
            print(f"   c) Verificar que rho_bar (fricción) sea adecuado")

        elif var_nl < 5.0:
            print("\n1. ✓ La curva muestra leve no-linealidad")
            print("   El material SÍ está cediendo, pero de manera gradual")
            print("   El endurecimiento plástico H es relativamente alto")

        else:
            print("\n1. ✓ La curva SÍ muestra no-linealidad significativa")
            print("   Con 50 pasos, la curvatura debería ser más evidente")

    print(f"\n{'='*70}")
    print(f"ANÁLISIS COMPLETADO")
    print('='*70)
    print(f"\nGráfica detallada disponible en: {archivo}")
    print(f"\nLa gráfica de rigidez instantánea muestra si hay degradación")
    print(f"de rigidez (evidencia de plasticidad) a lo largo del análisis.")
