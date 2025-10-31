#!/usr/bin/env python3
"""
Script para visualizar resultados del análisis en dos fases
Muestra claramente la fase de gravedad y la fase de carga aplicada
"""

import matplotlib.pyplot as plt
import numpy as np
import json
from datetime import datetime

def visualizar_dos_fases():
    """Genera visualizaciones del análisis en dos fases"""

    # Ejecutar el modelo y capturar datos
    print("Ejecutando modelo...")
    from opensees_zapata_3d_nolineal import ModeloZapata3DNoLineal

    modelo = ModeloZapata3DNoLineal()
    modelo.inicializar_modelo()
    modelo.definir_materiales_no_lineales()
    modelo.crear_malla_unificada()
    modelo.crear_elementos()
    modelo.aplicar_condiciones_frontera()
    modelo.aplicar_cargas_gravedad()  # Solo gravedad en Fase 1
    exito = modelo.analizar_no_lineal()  # Esto aplicará cargas externas en Fase 2

    if not exito:
        print("El análisis falló")
        return

    # Extraer datos
    cargas = np.array(modelo.historia_carga)
    despls = np.array(modelo.historia_despl)
    fases = np.array(modelo.historia_fase)

    # Separar por fase
    fase1_idx = fases == 1
    fase2_idx = fases == 2

    cargas_f1 = cargas[fase1_idx]
    despls_f1 = despls[fase1_idx]
    cargas_f2 = cargas[fase2_idx]
    despls_f2 = despls[fase2_idx]

    print(f"\nDatos capturados:")
    print(f"  Fase 1 (Gravedad): {len(cargas_f1)} puntos")
    print(f"  Fase 2 (Carga aplicada): {len(cargas_f2)} puntos")
    print(f"  Desplazamiento por gravedad: {despls_f1[-1]:.4f} mm")
    print(f"  Desplazamiento final: {despls_f2[-1]:.4f} mm")
    print(f"  Desplazamiento incremental Fase 2: {despls_f2[-1] - despls_f1[-1]:.6f} mm")

    # Crear figura con 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # =============================================================
    # Subplot 1: Curva carga-desplazamiento completa
    # =============================================================
    ax1 = axes[0]

    # Fase 1: línea vertical en despl por gravedad
    ax1.plot([despls_f1[-1], despls_f1[-1]], [0, 0], 'ro', markersize=8, label='Fase 1: Gravedad')
    ax1.axvline(despls_f1[-1], color='red', linestyle='--', alpha=0.3)

    # Fase 2: curva de carga aplicada
    ax1.plot(despls_f2, cargas_f2, 'b-o', linewidth=2, markersize=5, label='Fase 2: Carga aplicada')

    ax1.set_xlabel('Desplazamiento vertical (mm)', fontsize=11)
    ax1.set_ylabel('Carga aplicada (kN)', fontsize=11)
    ax1.set_title('Curva Carga-Desplazamiento\n(Ambas Fases)', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best')

    # Anotación
    ax1.annotate(f'Gravedad:\nΔz = {despls_f1[-1]:.2f} mm',
                xy=(despls_f1[-1], 0), xytext=(despls_f1[-1]-1, 300),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5),
                fontsize=9, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    # =============================================================
    # Subplot 2: Desplazamiento incremental en Fase 2
    # =============================================================
    ax2 = axes[1]

    # Calcular desplazamiento incremental (respecto al final de fase 1)
    despls_incrementales = despls_f2 - despls_f1[-1]

    ax2.plot(despls_incrementales, cargas_f2, 'g-o', linewidth=2, markersize=6)
    ax2.set_xlabel('Desplazamiento incremental (mm)', fontsize=11)
    ax2.set_ylabel('Carga aplicada (kN)', fontsize=11)
    ax2.set_title('Fase 2: Desplazamiento Incremental\n(Desde fin de Fase 1)',
                  fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)

    # Calcular rigidez en Fase 2
    if len(despls_incrementales) > 1:
        K_fase2 = (cargas_f2[-1] - cargas_f2[0]) / (despls_incrementales[-1] - despls_incrementales[0])
        ax2.text(0.02, 0.98, f'Rigidez Fase 2:\nK = {K_fase2:.2f} kN/mm',
                transform=ax2.transAxes, fontsize=10,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))

    # =============================================================
    # Subplot 3: Historia de desplazamiento vs paso de análisis
    # =============================================================
    ax3 = axes[2]

    # Crear eje x con pasos
    pasos_totales = np.arange(len(despls))

    # Colorear por fase
    colores = ['red' if f == 1 else 'blue' for f in fases]

    for i in range(len(pasos_totales)):
        ax3.plot(pasos_totales[i], despls[i], 'o', color=colores[i], markersize=8)

    # Líneas
    ax3.plot(pasos_totales[fase1_idx], despls_f1, 'r-', linewidth=2, label='Fase 1: Gravedad')
    ax3.plot(pasos_totales[fase2_idx], despls_f2, 'b-', linewidth=2, label='Fase 2: Carga')

    ax3.set_xlabel('Paso de análisis', fontsize=11)
    ax3.set_ylabel('Desplazamiento total (mm)', fontsize=11)
    ax3.set_title('Historia de Desplazamiento\n(Por Fase)', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc='best')

    # Línea divisoria entre fases
    ax3.axvline(np.where(fase1_idx)[0][-1] + 0.5, color='gray', linestyle='--',
               alpha=0.5, linewidth=2, label='Separación fases')

    plt.tight_layout()

    # Guardar
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = f'resultados/analisis_dos_fases_{timestamp}.png'
    plt.savefig(archivo, dpi=300, bbox_inches='tight')
    print(f"\n✓ Gráfica guardada en: {archivo}")

    # Resumen numérico
    print("\n" + "="*60)
    print("RESUMEN NUMÉRICO")
    print("="*60)
    print(f"\nFASE 1 - GRAVEDAD:")
    print(f"  Peso total sistema: 7369.15 kN (estimado)")
    print(f"  Desplazamiento: {despls_f1[-1]:.4f} mm")

    print(f"\nFASE 2 - CARGA APLICADA (0 → 1000 kN):")
    print(f"  Desplazamiento inicial: {despls_f2[0]:.4f} mm")
    print(f"  Desplazamiento final: {despls_f2[-1]:.4f} mm")
    print(f"  Desplazamiento incremental: {despls_f2[-1] - despls_f1[-1]:.6f} mm")
    if len(despls_incrementales) > 1:
        print(f"  Rigidez Fase 2: {K_fase2:.2f} kN/mm")

    print(f"\nCOMPARACIÓN:")
    print(f"  Carga aplicada / Peso propio: {1000/7369.15*100:.1f}%")
    print(f"  Despl Fase 2 / Despl Fase 1: {abs(despls_f2[-1] - despls_f1[-1])/abs(despls_f1[-1])*100:.3f}%")

    plt.close()

if __name__ == '__main__':
    visualizar_dos_fases()
