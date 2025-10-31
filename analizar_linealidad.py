#!/usr/bin/env python3
"""
Script para analizar por qué la curva Drucker-Prager aparece lineal
Usa los datos del análisis existente (10 pasos) y los analiza estadísticamente
"""

import openseespy.opensees as ops
import numpy as np
import json
import matplotlib.pyplot as plt
from datetime import datetime
import os

# Importar la función de ejecución del modelo
from comparar_lineal_nolineal import ejecutar_modelo


def analizar_linealidad(carga, despl, nombre_modelo):
    """Analiza qué tan lineal es una curva"""

    print(f"\n{'='*70}")
    print(f"ANÁLISIS DE LINEALIDAD - {nombre_modelo}")
    print('='*70)

    if len(carga) < 3:
        print("  ⚠ Datos insuficientes para análisis")
        return None

    print(f"\n  Datos de la curva:")
    print(f"  {'Paso':<8} {'Carga (kN)':<15} {'Despl (mm)':<15} {'K inst (kN/mm)':<15}")
    print(f"  {'-'*60}")

    # Calcular rigidez instantánea entre puntos consecutivos
    rigideces = []
    for i in range(len(carga)):
        if i == 0:
            print(f"  {i+1:<8} {carga[i]:<15.2f} {despl[i]:<15.4f} {'--':<15}")
        else:
            dC = carga[i] - carga[i-1]
            dD = despl[i] - despl[i-1]
            if abs(dD) > 1e-10:
                K_inst = dC / dD
                rigideces.append(K_inst)
                print(f"  {i+1:<8} {carga[i]:<15.2f} {despl[i]:<15.4f} {K_inst:<15.2f}")
            else:
                print(f"  {i+1:<8} {carga[i]:<15.2f} {despl[i]:<15.4f} {'--':<15}")

    # Rigidez promedio (global)
    K_global = (carga[-1] - carga[0]) / (despl[-1] - despl[0])

    # Estadísticas de rigidez instantánea
    rigideces_array = np.array(rigideces)
    desviacion_std = np.std(rigideces_array)
    desviacion_rel = (desviacion_std / K_global) * 100  # Porcentaje
    rango = np.max(rigideces_array) - np.min(rigideces_array)
    rango_rel = (rango / K_global) * 100

    print(f"\n  ESTADÍSTICAS DE RIGIDEZ:")
    print(f"  {'-'*60}")
    print(f"  Rigidez global (K):          {K_global:>12.2f} kN/mm")
    print(f"  Rigidez instantánea:")
    print(f"    - Mínima:                  {np.min(rigideces):>12.2f} kN/mm ({(np.min(rigideces)/K_global-1)*100:+.2f}%)")
    print(f"    - Máxima:                  {np.max(rigideces):>12.2f} kN/mm ({(np.max(rigideces)/K_global-1)*100:+.2f}%)")
    print(f"    - Promedio:                {np.mean(rigideces):>12.2f} kN/mm")
    print(f"    - Desv. estándar:          {desviacion_std:>12.2f} kN/mm")
    print(f"    - Rango (max-min):         {rango:>12.2f} kN/mm")
    print(f"\n  VARIACIÓN DE RIGIDEZ:")
    print(f"    - Desviación relativa:     {desviacion_rel:>12.2f} %")
    print(f"    - Rango relativo:          {rango_rel:>12.2f} %")

    # Clasificación
    print(f"\n  CLASIFICACIÓN:")
    if desviacion_rel < 0.1:
        print(f"    → Comportamiento PERFECTAMENTE LINEAL (variación < 0.1%)")
    elif desviacion_rel < 1.0:
        print(f"    → Comportamiento MUY LINEAL (variación < 1%)")
    elif desviacion_rel < 5.0:
        print(f"    → Comportamiento APROXIMADAMENTE LINEAL (variación < 5%)")
    elif desviacion_rel < 15.0:
        print(f"    → Comportamiento LEVEMENTE NO LINEAL (variación 5-15%)")
    else:
        print(f"    → Comportamiento CLARAMENTE NO LINEAL (variación > 15%)")

    # Calcular R² para ajuste lineal
    coef = np.polyfit(despl, carga, 1)
    carga_ajuste = np.polyval(coef, despl)

    ss_res = np.sum((np.array(carga) - carga_ajuste)**2)
    ss_tot = np.sum((np.array(carga) - np.mean(carga))**2)
    r_squared = 1 - (ss_res / ss_tot)

    print(f"\n  AJUSTE LINEAL:")
    print(f"    - Ecuación: Carga = {coef[0]:.2f} × Despl + {coef[1]:.2f}")
    print(f"    - R² (coef. determinación): {r_squared:.8f}")

    if r_squared > 0.99999:
        print(f"    → Ajuste lineal PERFECTO (R² > 0.99999)")
    elif r_squared > 0.9999:
        print(f"    → Ajuste lineal EXCELENTE (R² > 0.9999)")
    elif r_squared > 0.999:
        print(f"    → Ajuste lineal MUY BUENO (R² > 0.999)")
    elif r_squared > 0.99:
        print(f"    → Ajuste lineal BUENO (R² > 0.99)")
    else:
        print(f"    → Desviación significativa de comportamiento lineal")

    return {
        'K_global': K_global,
        'rigideces': rigideces,
        'desviacion_std': desviacion_std,
        'desviacion_rel': desviacion_rel,
        'rango_rel': rango_rel,
        'r_squared': r_squared,
        'coef': coef
    }


def crear_grafica_diagnostico(carga_lin, despl_lin, carga_nl, despl_nl,
                               analisis_lin, analisis_nl):
    """Crea gráficas de diagnóstico detalladas"""

    print(f"\n{'='*70}")
    print("GENERANDO GRÁFICAS DE DIAGNÓSTICO")
    print('='*70)

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # ===== SUBPLOT 1: Curvas carga-desplazamiento =====
    ax1 = axes[0, 0]
    ax1.plot(despl_lin, carga_lin, 'b-o', linewidth=2, markersize=8,
             label='Modelo Lineal (Elástico)', alpha=0.8)
    ax1.plot(despl_nl, carga_nl, 'r-s', linewidth=2, markersize=8,
             label='Modelo No Lineal (Drucker-Prager)', alpha=0.8)

    ax1.set_xlabel('Desplazamiento vertical (mm)', fontsize=11)
    ax1.set_ylabel('Carga vertical (kN)', fontsize=11)
    ax1.set_title('Curvas Carga-Desplazamiento', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=10)

    info_text = (f"K lineal = {analisis_lin['K_global']:.2f} kN/mm\n"
                f"K no lineal = {analisis_nl['K_global']:.2f} kN/mm\n"
                f"Diferencia = {abs(analisis_lin['K_global']-analisis_nl['K_global'])/analisis_lin['K_global']*100:.1f}%")
    ax1.text(0.98, 0.02, info_text, transform=ax1.transAxes,
            fontsize=9, horizontalalignment='right', verticalalignment='bottom',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))

    # ===== SUBPLOT 2: Rigidez instantánea =====
    ax2 = axes[0, 1]

    # Puntos medios para rigidez instantánea
    despl_medio_lin = [(despl_lin[i] + despl_lin[i+1])/2
                       for i in range(len(despl_lin)-1)]
    despl_medio_nl = [(despl_nl[i] + despl_nl[i+1])/2
                      for i in range(len(despl_nl)-1)]

    ax2.plot(despl_medio_lin, analisis_lin['rigideces'],
            'b-o', linewidth=2, markersize=8, label='Lineal', alpha=0.8)
    ax2.plot(despl_medio_nl, analisis_nl['rigideces'],
            'r-s', linewidth=2, markersize=8, label='No Lineal', alpha=0.8)

    # Líneas de referencia (rigidez global)
    ax2.axhline(y=analisis_lin['K_global'], color='b',
               linestyle='--', alpha=0.4, linewidth=1, label=f'K global lineal')
    ax2.axhline(y=analisis_nl['K_global'], color='r',
               linestyle='--', alpha=0.4, linewidth=1, label=f'K global NL')

    ax2.set_xlabel('Desplazamiento vertical (mm)', fontsize=11)
    ax2.set_ylabel('Rigidez instantánea (kN/mm)', fontsize=11)
    ax2.set_title('Evolución de Rigidez Instantánea', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best', fontsize=9)

    var_text = (f"Variación NL: {analisis_nl['desviacion_rel']:.3f}%\n"
               f"Rango NL: {analisis_nl['rango_rel']:.3f}%")
    ax2.text(0.02, 0.98, var_text, transform=ax2.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.6))

    # ===== SUBPLOT 3: Residuos del ajuste lineal =====
    ax3 = axes[1, 0]

    # Calcular residuos
    carga_ajuste_nl = np.polyval(analisis_nl['coef'], despl_nl)
    residuos_nl = np.array(carga_nl) - carga_ajuste_nl

    ax3.plot(despl_nl, residuos_nl, 'r-o', linewidth=2, markersize=8, alpha=0.8)
    ax3.axhline(y=0, color='k', linestyle='--', alpha=0.5, linewidth=1)

    ax3.set_xlabel('Desplazamiento vertical (mm)', fontsize=11)
    ax3.set_ylabel('Residuo (kN)', fontsize=11)
    ax3.set_title('Residuos del Ajuste Lineal (Modelo No Lineal)',
                  fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)

    max_residuo = np.max(np.abs(residuos_nl))
    res_text = (f"R² = {analisis_nl['r_squared']:.8f}\n"
               f"Max |residuo| = {max_residuo:.4f} kN\n"
               f"({max_residuo/carga_nl[-1]*100:.3f}% de carga máxima)")
    ax3.text(0.02, 0.98, res_text, transform=ax3.transAxes,
            fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    # ===== SUBPLOT 4: Comparación de desplazamientos para misma carga =====
    ax4 = axes[1, 1]

    # Calcular factor de amplificación de desplazamiento
    factores = [despl_nl[i]/despl_lin[i] if despl_lin[i] > 0 else 0
                for i in range(len(carga_lin))]

    ax4.plot(carga_lin, factores, 'g-o', linewidth=2, markersize=8, alpha=0.8)
    ax4.axhline(y=1.0, color='k', linestyle='--', alpha=0.5, linewidth=1,
               label='Sin amplificación')

    ax4.set_xlabel('Carga vertical (kN)', fontsize=11)
    ax4.set_ylabel('Factor de amplificación\n(Despl_NL / Despl_Lineal)', fontsize=11)
    ax4.set_title('Amplificación de Desplazamiento por Plasticidad',
                  fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.legend(loc='best', fontsize=9)

    factor_final = factores[-1]
    factor_text = (f"Factor final: {factor_final:.2f}×\n"
                  f"Incremento: {(factor_final-1)*100:.1f}%")
    ax4.text(0.02, 0.98, factor_text, transform=ax4.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))

    plt.tight_layout()

    # Guardar
    os.makedirs('imagenes', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = os.path.join('imagenes', f'diagnostico_linealidad_{timestamp}.png')
    plt.savefig(archivo, dpi=300, bbox_inches='tight')
    print(f"\n  ✓ Gráfica guardada en: {archivo}")

    plt.close()

    return archivo


if __name__ == '__main__':
    print("\n" + "#"*70)
    print("# DIAGNÓSTICO: ¿POR QUÉ LA CURVA NO LINEAL APARECE LINEAL?")
    print("#"*70)
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Ejecutar modelos (10 pasos - funciona bien)
    print("[1/3] Ejecutando modelo LINEAL...")
    carga_lin, despl_lin = ejecutar_modelo(usar_drucker_prager=False)

    print("\n" + "="*70)
    print("[2/3] Ejecutando modelo NO LINEAL...")
    carga_nl, despl_nl = ejecutar_modelo(usar_drucker_prager=True)

    # Analizar linealidad
    print("\n" + "="*70)
    print("[3/3] Analizando linealidad de las curvas...")
    analisis_lin = analizar_linealidad(carga_lin, despl_lin, "MODELO LINEAL")
    analisis_nl = analizar_linealidad(carga_nl, despl_nl, "MODELO NO LINEAL (DRUCKER-PRAGER)")

    # Crear gráficas de diagnóstico
    archivo = crear_grafica_diagnostico(carga_lin, despl_lin, carga_nl, despl_nl,
                                        analisis_lin, analisis_nl)

    # ===== DIAGNÓSTICO FINAL =====
    print(f"\n{'#'*70}")
    print("# DIAGNÓSTICO FINAL")
    print("#"*70)

    var_nl = analisis_nl['desviacion_rel']
    r2_nl = analisis_nl['r_squared']

    print(f"\nRESULTADOS CLAVE:")
    print(f"  - Variación de rigidez (modelo NL): {var_nl:.4f}%")
    print(f"  - R² del ajuste lineal (modelo NL): {r2_nl:.8f}")
    print(f"  - Desplazamiento final lineal: {despl_lin[-1]:.3f} mm")
    print(f"  - Desplazamiento final no lineal: {despl_nl[-1]:.3f} mm")
    print(f"  - Factor de amplificación: {despl_nl[-1]/despl_lin[-1]:.2f}×")

    print(f"\n{'='*70}")
    print("RESPUESTA A LA PREGUNTA: ¿POR QUÉ LA CURVA NO LINEAL ES LINEAL?")
    print('='*70)

    if var_nl < 0.5 and r2_nl > 0.9999:
        print(f"\n1. ✓ CONFIRMADO: La curva es EFECTIVAMENTE muy lineal")
        print(f"   - Variación de rigidez < 0.5%")
        print(f"   - R² > 0.9999 (ajuste casi perfecto)")

        print(f"\n2. RAZÓN PRINCIPAL:")
        print(f"   La curva aparece lineal porque el material Drucker-Prager")
        print(f"   se comporta de manera CASI ELÁSTICA en este rango de carga.")

        print(f"\n3. EXPLICACIONES POSIBLES:")
        print(f"   a) Los esfuerzos podrían estar cerca pero bajo la superficie")
        print(f"      de fluencia, resultando en comportamiento predominantemente")
        print(f"      elástico con muy poca plasticidad.")

        print(f"\n   b) El endurecimiento plástico (H = 0.001×G) es suficientemente")
        print(f"      alto para mantener rigidez casi constante después de ceder.")

        print(f"\n   c) La diferencia en rigidez ({analisis_lin['K_global']:.1f} vs")
        print(f"      {analisis_nl['K_global']:.1f} kN/mm) se debe principalmente a")
        print(f"      diferencias en los módulos elásticos K y G calculados,")
        print(f"      NO a comportamiento plástico significativo.")

        print(f"\n4. EVIDENCIA DE PLASTICIDAD:")
        print(f"   - SÍ hay plasticidad: despl. final es {despl_nl[-1]/despl_lin[-1]:.2f}× mayor")
        print(f"   - PERO la rigidez tangente se mantiene casi constante")
        print(f"   - Esto produce una curva que PARECE lineal visualmente")

        print(f"\n5. PARA OBSERVAR NO-LINEALIDAD MÁS CLARA:")
        print(f"   a) Reducir σ_y (cohesión) → fluencia más temprana")
        print(f"   b) Aumentar la carga → mayor rango plástico")
        print(f"   c) Reducir H (endurecimiento) → mayor degradación de rigidez")
        print(f"   d) Usar más pasos de análisis (aunque con 10 es suficiente)")

    elif var_nl < 2.0:
        print(f"\n1. La curva muestra LEVE no-linealidad")
        print(f"   - Variación de rigidez: {var_nl:.2f}%")
        print(f"   - Suficiente para detectar, pero no muy pronunciada")

        print(f"\n2. El material SÍ está cediendo, pero:")
        print(f"   - El endurecimiento mantiene rigidez relativamente constante")
        print(f"   - La curvatura es sutil y requiere análisis detallado")

    else:
        print(f"\n1. ✓ La curva SÍ muestra no-linealidad significativa")
        print(f"   - Variación de rigidez: {var_nl:.2f}%")
        print(f"   - La curvatura debería ser visible en el gráfico")

    print(f"\n{'='*70}")
    print(f"GRÁFICA DE DIAGNÓSTICO DISPONIBLE EN:")
    print(f"{archivo}")
    print('='*70)

    print(f"\nLa gráfica incluye:")
    print(f"  1. Curvas carga-desplazamiento")
    print(f"  2. Evolución de rigidez instantánea (detecta degradación)")
    print(f"  3. Residuos del ajuste lineal (detecta curvatura)")
    print(f"  4. Factor de amplificación (cuantifica efecto de plasticidad)")
