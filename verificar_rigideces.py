#!/usr/bin/env python3
"""
Script de Verificación de Cálculo de Rigideces
==============================================

Este script realiza el cálculo detallado de las rigideces del suelo
estratificado paso a paso, mostrando todos los valores intermedios.

Autor: Claude AI
"""

import json
import numpy as np


def cargar_configuracion(archivo='config_zapata.json'):
    """Carga la configuración del modelo"""
    with open(archivo, 'r') as f:
        return json.load(f)


def calcular_rigideces_detallado(config):
    """
    Calcula las rigideces del suelo estratificado con salida detallada
    """
    print("=" * 70)
    print("VERIFICACIÓN DE CÁLCULO DE RIGIDECES - SUELO ESTRATIFICADO")
    print("=" * 70)

    # Extraer datos
    capas = config['suelo_estratificado']['capas']
    geom = config['geometria']['zapata']

    # Geometría
    B_x = geom['ancho_x']
    B_y = geom['ancho_y']
    B = min(B_x, B_y)
    A = B_x * B_y

    print("\n" + "-" * 70)
    print("1. DATOS DE ENTRADA")
    print("-" * 70)

    print("\n1.1 GEOMETRÍA DE LA ZAPATA")
    print(f"  Ancho X (B_x):        {B_x:.2f} m")
    print(f"  Ancho Y (B_y):        {B_y:.2f} m")
    print(f"  Ancho mínimo (B):     {B:.2f} m")
    print(f"  Área (A):             {A:.2f} m²")

    print("\n1.2 PROPIEDADES DEL SUELO ESTRATIFICADO\n")

    for i, capa in enumerate(capas, 1):
        print(f"  Capa {i}: {capa['nombre']}")
        print(f"    Módulo de Young (E{i}):     {capa['E']:.2e} Pa = {capa['E']/1e6:.1f} MPa")
        print(f"    Coef. Poisson (ν{i}):       {capa['nu']:.2f}")
        print(f"    Espesor (H{i}):             {capa['espesor']:.2f} m")
        print(f"    Densidad (ρ{i}):            {capa['densidad']:.0f} kg/m³")

        # Calcular módulo de corte
        G = capa['E'] / (2 * (1 + capa['nu']))
        print(f"    Módulo de corte (G{i}):     {G:.2e} Pa = {G/1e6:.1f} MPa")
        print()

    # CÁLCULO DE RIGIDEZ VERTICAL
    print("-" * 70)
    print("2. CÁLCULO DE RIGIDEZ VERTICAL (K_v)")
    print("-" * 70)

    print("\n2.1 Teoría: Capas en Serie")
    print("  Para capas en serie, la flexibilidad total es la suma:")
    print("  δ_total = δ₁ + δ₂ + δ₃")
    print("  donde: δᵢ = Hᵢ / (Eᵢ × A)")

    print("\n2.2 Cálculo de Flexibilidades Individuales\n")

    flexibilidades = []
    for i, capa in enumerate(capas, 1):
        E = capa['E']
        H = capa['espesor']
        delta_i = H / (E * A)
        flexibilidades.append(delta_i)

        print(f"  Capa {i} - {capa['nombre']}:")
        print(f"    δ{i} = H{i} / (E{i} × A)")
        print(f"    δ{i} = {H:.2f} / ({E:.2e} × {A:.2f})")
        print(f"    δ{i} = {H:.2f} / {E*A:.2e}")
        print(f"    δ{i} = {delta_i:.3e} m/N")
        print()

    # Flexibilidad total
    delta_total = sum(flexibilidades)

    print("2.3 Flexibilidad Total\n")
    print(f"  δ_total = δ₁ + δ₂ + δ₃")
    suma_str = " + ".join([f"{d:.3e}" for d in flexibilidades])
    print(f"  δ_total = {suma_str}")
    print(f"  δ_total = {delta_total:.3e} m/N")

    # Rigidez vertical
    K_v = 1.0 / delta_total

    print("\n2.4 Rigidez Vertical Equivalente\n")
    print(f"  K_v = 1 / δ_total")
    print(f"  K_v = 1 / {delta_total:.3e}")
    print(f"  K_v = {K_v:.3e} N/m")
    print(f"  K_v = {K_v/1e6:.2f} MN/m")
    print(f"  K_v = {K_v/1e9:.4f} GN/m")

    # Análisis de contribución
    print("\n2.5 Contribución de Cada Capa a la Flexibilidad Total\n")
    for i, (capa, delta_i) in enumerate(zip(capas, flexibilidades), 1):
        porcentaje = (delta_i / delta_total) * 100
        print(f"  Capa {i} ({capa['nombre']}):")
        print(f"    Contribución: {porcentaje:.1f}%")

    print(f"\n  → La capa más deformable controla el comportamiento del sistema")

    # CÁLCULO DE RIGIDEZ HORIZONTAL
    print("\n" + "-" * 70)
    print("3. CÁLCULO DE RIGIDEZ HORIZONTAL (K_h)")
    print("-" * 70)

    print("\n3.1 Teoría")
    print("  Para fundaciones en suelos estratificados:")
    print("  K_h ≈ α × K_v")
    print("  donde α = 0.5 a 0.6 (se adopta 0.5 conservador)")

    alpha = 0.5
    K_h = alpha * K_v

    print("\n3.2 Cálculo\n")
    print(f"  K_h = {alpha} × K_v")
    print(f"  K_h = {alpha} × {K_v:.3e}")
    print(f"  K_h = {K_h:.3e} N/m")
    print(f"  K_h = {K_h/1e6:.2f} MN/m")
    print(f"  K_h = {K_h/1e9:.4f} GN/m")

    # CÁLCULO DE RIGIDEZ ROTACIONAL
    print("\n" + "-" * 70)
    print("4. CÁLCULO DE RIGIDEZ ROTACIONAL (K_rot)")
    print("-" * 70)

    print("\n4.1 Teoría")
    print("  La rigidez rotacional está relacionada con el momento")
    print("  de inercia del área de contacto:")
    print("  K_rot = K_v × (I / A)")
    print("  donde I = (B_x × B_y³) / 12 para zapata rectangular")

    I = (B_x * B_y**3) / 12

    print("\n4.2 Momento de Inercia\n")
    print(f"  I = (B_x × B_y³) / 12")
    print(f"  I = ({B_x} × {B_y}³) / 12")
    print(f"  I = ({B_x} × {B_y**3:.3f}) / 12")
    print(f"  I = {I:.3f} m⁴")

    K_rot = K_v * I / A

    print("\n4.3 Rigidez Rotacional\n")
    print(f"  K_rot = K_v × (I / A)")
    print(f"  K_rot = {K_v:.3e} × ({I:.3f} / {A:.2f})")
    print(f"  K_rot = {K_v:.3e} × {I/A:.4f}")
    print(f"  K_rot = {K_rot:.3e} N·m/rad")
    print(f"  K_rot = {K_rot/1e6:.2f} MN·m/rad")
    print(f"  K_rot = {K_rot/1e9:.4f} GN·m/rad")

    # VALIDACIÓN
    print("\n" + "-" * 70)
    print("5. VALIDACIÓN CON CARGA DE DISEÑO")
    print("-" * 70)

    P = config['cargas']['carga_vertical']
    F_h = config['cargas']['carga_horizontal_x']
    M = config['cargas']['momento_x']

    print(f"\n5.1 Cargas Aplicadas")
    print(f"  Carga vertical (P):     {P/1000:.1f} kN")
    print(f"  Carga horizontal (F):   {F_h/1000:.1f} kN")
    print(f"  Momento (M):            {M/1000:.1f} kN·m")

    # Predicciones
    delta_v = P / K_v * 1000  # en mm
    delta_h = F_h / K_h * 1000  # en mm
    theta = M / K_rot * 1000  # en mrad

    print(f"\n5.2 Desplazamientos Estimados")
    print(f"  Asentamiento (δ_v):     {delta_v:.2f} mm")
    print(f"  Desp. horizontal (δ_h): {delta_h:.2f} mm")
    print(f"  Rotación (θ):           {theta:.2f} mrad")

    # RESUMEN
    print("\n" + "=" * 70)
    print("6. RESUMEN DE RESULTADOS")
    print("=" * 70)

    print("\n┌" + "─" * 68 + "┐")
    print("│" + " " * 20 + "RIGIDECES CALCULADAS" + " " * 28 + "│")
    print("├" + "─" * 68 + "┤")
    print(f"│  Rigidez Vertical (K_v):      {K_v:.3e} N/m = {K_v/1e6:6.2f} MN/m  │")
    print(f"│  Rigidez Horizontal (K_h):    {K_h:.3e} N/m = {K_h/1e6:6.2f} MN/m  │")
    print(f"│  Rigidez Rotacional (K_rot):  {K_rot:.3e} N·m/rad = {K_rot/1e6:6.2f} MN·m/rad │")
    print("└" + "─" * 68 + "┘")

    print("\n" + "=" * 70)
    print("CÁLCULO COMPLETADO")
    print("=" * 70)

    return K_v, K_h, K_rot


def comparar_con_opensees(K_v, K_h, K_rot):
    """Compara con resultados de OpenSees"""
    print("\n" + "=" * 70)
    print("7. COMPARACIÓN CON RESULTADOS DE OpenSees")
    print("=" * 70)

    # Valores del análisis de OpenSees
    K_v_opensees = 0.01724e9  # GN/m convertido a N/m
    K_h_opensees = 0.00862e9
    asentamiento_opensees = 29.0  # mm
    desp_horiz_opensees = 5.8  # mm

    print("\n┌" + "─" * 68 + "┐")
    print("│" + " " * 15 + "Parámetro          │   Calculado   │  OpenSees    │")
    print("├" + "─" * 68 + "┤")
    print(f"│  K_v (MN/m)                   │  {K_v/1e6:10.2f}   │  {K_v_opensees/1e6:10.2f}  │")
    print(f"│  K_h (MN/m)                   │  {K_h/1e6:10.2f}   │  {K_h_opensees/1e6:10.2f}  │")
    print("└" + "─" * 68 + "┘")

    error_kv = abs(K_v - K_v_opensees) / K_v_opensees * 100
    error_kh = abs(K_h - K_h_opensees) / K_h_opensees * 100

    print(f"\n  Error K_v:  {error_kv:.2f}%")
    print(f"  Error K_h:  {error_kh:.2f}%")

    if error_kv < 1 and error_kh < 1:
        print("\n  ✓ Excelente concordancia con OpenSees (error < 1%)")
    elif error_kv < 5 and error_kh < 5:
        print("\n  ✓ Buena concordancia con OpenSees (error < 5%)")
    else:
        print("\n  ⚠ Verificar cálculos (error > 5%)")


def main():
    """Función principal"""
    config = cargar_configuracion()
    K_v, K_h, K_rot = calcular_rigideces_detallado(config)
    comparar_con_opensees(K_v, K_h, K_rot)

    print("\nPara más detalles, consultar: MEMORIA_CALCULO_RIGIDECES.md\n")


if __name__ == '__main__':
    main()
