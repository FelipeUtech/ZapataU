#!/usr/bin/env python3
"""
Visualización de Resultados - Modelo 3D No Lineal
==================================================

Genera gráficas comparativas de los tres modelos disponibles

Autor: Claude AI
"""

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import Rectangle, FancyBboxPatch
import matplotlib.patches as mpatches

# Datos de los tres modelos
modelos = {
    'Simplificado': {
        'asentamiento': 29.0,  # mm
        'desp_horiz': 17.6,
        'tiempo': 1,  # segundos
        'tipo': 'Resortes 1D',
        'material': 'Lineal',
        'color': '#3498db'
    },
    '3D Lineal': {
        'asentamiento': None,  # Error
        'desp_horiz': None,
        'tiempo': 5,
        'tipo': 'Brick 3D',
        'material': 'Lineal',
        'color': '#e74c3c'
    },
    '3D No Lineal': {
        'asentamiento': 4.6,  # mm
        'desp_horiz': 0.067,
        'tiempo': 10,
        'tipo': 'Brick 3D',
        'material': 'J2 Plasticity',
        'color': '#2ecc71'
    }
}

# Crear figura con múltiples subplots
fig = plt.figure(figsize=(16, 12))

# =========================================================================
# 1. COMPARACIÓN DE ASENTAMIENTOS
# =========================================================================
ax1 = fig.add_subplot(2, 3, 1)

nombres = []
asentamientos = []
colores = []

for nombre, datos in modelos.items():
    if datos['asentamiento'] is not None:
        nombres.append(nombre)
        asentamientos.append(datos['asentamiento'])
        colores.append(datos['color'])

bars = ax1.bar(nombres, asentamientos, color=colores, alpha=0.8, edgecolor='black', linewidth=2)
ax1.set_ylabel('Asentamiento (mm)', fontsize=12, fontweight='bold')
ax1.set_title('Asentamiento - Comparación de Modelos', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='y')

# Añadir valores sobre las barras
for bar in bars:
    height = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., height,
            f'{height:.1f} mm',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

# Añadir nota
ax1.text(0.5, 0.95, 'Carga aplicada: 500 kN',
         transform=ax1.transAxes, ha='center', va='top',
         fontsize=9, style='italic',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

# =========================================================================
# 2. CARACTERÍSTICAS DE CADA MODELO
# =========================================================================
ax2 = fig.add_subplot(2, 3, 2)
ax2.axis('off')

tabla_data = [
    ['Modelo', 'Tipo', 'Material', 'Análisis'],
]

for nombre, datos in modelos.items():
    analisis = 'No lineal' if 'No Lineal' in nombre else 'Lineal'
    tabla_data.append([
        nombre,
        datos['tipo'],
        datos['material'],
        analisis
    ])

# Colores para las filas
colores_filas = [['#4472C4']*4]  # Header
for nombre, datos in modelos.items():
    if 'No Lineal' in nombre:
        colores_filas.append([datos['color']]*4)
    else:
        colores_filas.append(['white']*4)

table = ax2.table(cellText=tabla_data, cellLoc='center',
                 loc='center', colWidths=[0.3, 0.25, 0.25, 0.2])

table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 2.5)

# Estilo del header
for i in range(4):
    cell = table[(0, i)]
    cell.set_facecolor('#4472C4')
    cell.set_text_props(weight='bold', color='white')

# Estilo de las filas de datos
for i in range(1, len(tabla_data)):
    for j in range(4):
        cell = table[(i, j)]
        if i == 3:  # Fila del modelo 3D No Lineal
            cell.set_text_props(weight='bold')

ax2.set_title('Características de los Modelos', fontsize=13, fontweight='bold', pad=20)

# =========================================================================
# 3. TIEMPO DE CÓMPUTO
# =========================================================================
ax3 = fig.add_subplot(2, 3, 3)

nombres_tiempo = list(modelos.keys())
tiempos = [modelos[m]['tiempo'] for m in nombres_tiempo]
colores_tiempo = [modelos[m]['color'] for m in nombres_tiempo]

bars3 = ax3.barh(nombres_tiempo, tiempos, color=colores_tiempo, alpha=0.8, edgecolor='black', linewidth=2)
ax3.set_xlabel('Tiempo de Cómputo (segundos)', fontsize=12, fontweight='bold')
ax3.set_title('Eficiencia Computacional', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='x')

# Añadir valores
for i, (bar, tiempo) in enumerate(zip(bars3, tiempos)):
    width = bar.get_width()
    ax3.text(width + 0.2, bar.get_y() + bar.get_height()/2,
            f'{tiempo}s',
            ha='left', va='center', fontsize=11, fontweight='bold')

# =========================================================================
# 4. ESQUEMA DEL MODELO 3D NO LINEAL
# =========================================================================
ax4 = fig.add_subplot(2, 3, 4)

# Dibujar esquema
y_base = 0
y_capa1 = 2
y_capa2 = 5
y_capa3 = 10
y_zapata_base = 11.5
y_zapata_top = 12.1
y_superficie = 13

# Suelo
ax4.add_patch(Rectangle((0, y_base), 4, y_capa1-y_base,
                        facecolor='#8B4513', edgecolor='black', linewidth=2, alpha=0.6))
ax4.text(2, (y_base+y_capa1)/2, 'Capa 3\nGrava\n80 MPa',
         ha='center', va='center', fontsize=9, fontweight='bold')

ax4.add_patch(Rectangle((0, y_capa1), 4, y_capa2-y_capa1,
                        facecolor='#DEB887', edgecolor='black', linewidth=2, alpha=0.6))
ax4.text(2, (y_capa1+y_capa2)/2, 'Capa 2\nArena\n30 MPa',
         ha='center', va='center', fontsize=9, fontweight='bold')

ax4.add_patch(Rectangle((0, y_capa2), 4, y_capa3-y_capa2,
                        facecolor='#CD853F', edgecolor='black', linewidth=2, alpha=0.6))
ax4.text(2, (y_capa2+y_capa3)/2, 'Capa 1\nArcilla\n10 MPa',
         ha='center', va='center', fontsize=9, fontweight='bold')

# Zapata
ax4.add_patch(Rectangle((1, y_zapata_base), 2, y_zapata_top-y_zapata_base,
                        facecolor='#7f8c8d', edgecolor='black', linewidth=3))
ax4.text(2, (y_zapata_base+y_zapata_top)/2, 'ZAPATA\n2.5×2.5×0.6 m',
         ha='center', va='center', fontsize=9, fontweight='bold', color='white')

# Superficie
ax4.plot([0, 4], [y_superficie, y_superficie], 'k-', linewidth=2)
ax4.text(4.2, y_superficie, 'Superficie', va='center', fontsize=9)

# Profundidad de desplante
ax4.annotate('', xy=(4.5, y_superficie), xytext=(4.5, y_zapata_base),
            arrowprops=dict(arrowstyle='<->', color='red', linewidth=2))
ax4.text(5.2, (y_superficie+y_zapata_base)/2, 'Df=1.5m',
         rotation=90, va='center', fontsize=9, color='red', fontweight='bold')

# Cargas
ax4.annotate('', xy=(2, y_zapata_top+0.5), xytext=(2, y_zapata_top+0.1),
            arrowprops=dict(arrowstyle='->', color='red', linewidth=3, lw=3))
ax4.text(2, y_zapata_top+0.7, 'P=500 kN', ha='center', fontsize=10,
         fontweight='bold', color='red')

# Asentamiento
ax4.annotate('', xy=(0.5, y_zapata_base), xytext=(0.5, y_zapata_base-0.3),
            arrowprops=dict(arrowstyle='->', color='blue', linewidth=2))
ax4.text(0.5, y_zapata_base-0.5, 'δ=4.6mm', ha='center', fontsize=9,
         color='blue', fontweight='bold')

ax4.set_xlim(-0.5, 6)
ax4.set_ylim(-0.5, 14.5)
ax4.set_aspect('equal')
ax4.axis('off')
ax4.set_title('Esquema - Modelo 3D No Lineal', fontsize=13, fontweight='bold')

# =========================================================================
# 5. RESULTADOS DETALLADOS MODELO 3D NO LINEAL
# =========================================================================
ax5 = fig.add_subplot(2, 3, 5)
ax5.axis('off')

resultados_text = """
RESULTADOS MODELO 3D NO LINEAL
═══════════════════════════════════════

✓ CONVERGENCIA
  • 10/10 pasos completados (100%)
  • Algoritmo: Newton-Raphson
  • Tolerancia: 1×10⁻⁶

✓ DESPLAZAMIENTOS
  • Asentamiento (centro):     4.60 mm
  • Asentamiento (promedio):   4.36 mm
  • Horizontal X:              0.07 mm
  • Horizontal Y:              0.05 mm

✓ MATERIALES NO LINEALES
  • Arcilla:  E=10 MPa, σy=120 kPa
  • Arena:    E=30 MPa, σy=30 kPa
  • Grava:    E=80 MPa, σy=50 kPa

✓ MALLA
  • 397 nodos (343 suelo + 54 zapata)
  • 248 elementos (216 suelo + 32 zapata)
  • Nodos compartidos en interfaz ✓

✓ VALIDACIÓN
  • Conectividad correcta
  • Comportamiento elastoplástico
  • Confinamiento lateral incluido
"""

ax5.text(0.05, 0.95, resultados_text, transform=ax5.transAxes,
        fontsize=9.5, verticalalignment='top', fontfamily='monospace',
        bbox=dict(boxstyle='round', facecolor='#ecf0f1', alpha=0.8, pad=1))

ax5.set_title('Resultados Detallados', fontsize=13, fontweight='bold', pad=20)

# =========================================================================
# 6. GRÁFICO DE VENTAJAS Y DESVENTAJAS
# =========================================================================
ax6 = fig.add_subplot(2, 3, 6)
ax6.axis('off')

ventajas_desvs = """
COMPARACIÓN Y RECOMENDACIONES
═════════════════════════════════════

📊 MODELO SIMPLIFICADO
  ✓ Rápido (< 1s)
  ✓ Fácil de usar
  ✓ Bueno para diseño preliminar
  ✗ No captura efectos 3D
  ✗ Sin confinamiento lateral

📊 MODELO 3D LINEAL
  ✗ Nodos desconectados (BUG)
  ✗ Solo materiales elásticos
  ✗ Resultados incorrectos
  → No recomendado

⭐ MODELO 3D NO LINEAL (RECOMENDADO)
  ✓ Materiales elastoplásticos
  ✓ Conectividad correcta
  ✓ Confinamiento 3D realista
  ✓ Análisis no lineal robusto
  ✓ Diseño detallado confiable
  ✓ Convergencia 100%
  ∼ Más lento (10s)

═════════════════════════════════════
RECOMENDACIÓN:
  • Preliminar → Modelo Simplificado
  • Detallado  → Modelo 3D No Lineal ⭐
═════════════════════════════════════
"""

ax6.text(0.05, 0.95, ventajas_desvs, transform=ax6.transAxes,
        fontsize=9.5, verticalalignment='top', fontfamily='monospace',
        bbox=dict(boxstyle='round', facecolor='#d5f4e6', alpha=0.8, pad=1))

ax6.set_title('Análisis Comparativo', fontsize=13, fontweight='bold', pad=20)

# =========================================================================
# TÍTULO GENERAL
# =========================================================================
plt.suptitle('ANÁLISIS COMPARATIVO - MODELOS DE ZAPATA EN OpenSees',
            fontsize=16, fontweight='bold', y=0.98)

plt.tight_layout()
plt.savefig('resultados/comparacion_modelos_zapata.png', dpi=300, bbox_inches='tight')
print("✓ Gráfica guardada en: resultados/comparacion_modelos_zapata.png")

# =========================================================================
# CREAR SEGUNDA FIGURA: DIAGRAMA DE FLUJO DEL ANÁLISIS NO LINEAL
# =========================================================================
fig2, ax = plt.subplots(1, 1, figsize=(12, 10))
ax.axis('off')

# Título
ax.text(0.5, 0.98, 'FLUJO DE ANÁLISIS NO LINEAL - MODELO 3D',
        ha='center', va='top', fontsize=16, fontweight='bold',
        transform=ax.transAxes)

# Crear cajas para el diagrama de flujo
boxes = [
    (0.5, 0.90, 'INICIO\nModelo 3D No Lineal', '#3498db'),
    (0.5, 0.82, 'Crear Malla Unificada\n397 nodos, 248 elementos', '#95a5a6'),
    (0.5, 0.74, 'Definir Materiales J2Plasticity\nArcilla, Arena, Grava', '#9b59b6'),
    (0.5, 0.66, 'Aplicar Condiciones de Frontera\nBase fija + Confinamiento lateral', '#e67e22'),
    (0.5, 0.58, 'Aplicar Cargas\n500 kN vertical + 50 kN horizontal', '#e74c3c'),
    (0.5, 0.48, 'Análisis Incremental\n10 pasos × 10% carga', '#f39c12'),
    (0.25, 0.38, 'Newton-Raphson\nIteración i', '#16a085'),
    (0.75, 0.38, '¿Convergió?', '#27ae60'),
    (0.25, 0.28, 'Modified Newton\nAlgoritmo alternativo', '#d35400'),
    (0.5, 0.18, 'Paso Completado\nActualizar desplazamientos', '#2ecc71'),
    (0.5, 0.08, '¿Todos los pasos?\n10/10', '#8e44ad'),
    (0.5, 0.02, 'FIN\nResultados: δ = 4.6 mm', '#27ae60'),
]

for x, y, text, color in boxes:
    if '¿' in text:
        # Diamante para decisiones
        ax.add_patch(mpatches.FancyBboxPatch((x-0.12, y-0.03), 0.24, 0.06,
                                            boxstyle="round,pad=0.01",
                                            facecolor=color, edgecolor='black',
                                            linewidth=2, alpha=0.8))
    else:
        # Rectángulo para procesos
        ax.add_patch(mpatches.FancyBboxPatch((x-0.15, y-0.03), 0.3, 0.06,
                                            boxstyle="round,pad=0.01",
                                            facecolor=color, edgecolor='black',
                                            linewidth=2, alpha=0.8))

    ax.text(x, y, text, ha='center', va='center', fontsize=9,
           fontweight='bold', color='white')

# Flechas de conexión
arrows = [
    (0.5, 0.87, 0.5, 0.85),  # 1->2
    (0.5, 0.79, 0.5, 0.77),  # 2->3
    (0.5, 0.71, 0.5, 0.69),  # 3->4
    (0.5, 0.63, 0.5, 0.61),  # 4->5
    (0.5, 0.55, 0.5, 0.51),  # 5->6
    (0.5, 0.45, 0.25, 0.41),  # 6->7
    (0.25, 0.35, 0.5, 0.41),  # 7->8 (diagonal)
    (0.75, 0.35, 0.75, 0.25),  # 8->9 SI
    (0.75, 0.25, 0.5, 0.21),  # 9->10 (diagonal)
    (0.25, 0.25, 0.25, 0.15),  # 7alt->9
    (0.25, 0.15, 0.5, 0.21),  # 9alt->10
    (0.5, 0.15, 0.5, 0.11),  # 10->11
    (0.5, 0.05, 0.5, 0.05),  # 11->12
]

for x1, y1, x2, y2 in arrows:
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
               arrowprops=dict(arrowstyle='->', color='black',
                             linewidth=2, lw=2))

# Etiquetas en las flechas
ax.text(0.78, 0.30, 'SÍ', fontsize=9, fontweight='bold', color='green')
ax.text(0.68, 0.38, 'NO', fontsize=9, fontweight='bold', color='red')
ax.text(0.43, 0.11, 'SÍ', fontsize=9, fontweight='bold', color='green')
ax.text(0.40, 0.05, 'NO\n(loop)', fontsize=8, fontweight='bold', color='red')

# Flecha de loop (si no todos los pasos)
ax.annotate('', xy=(0.35, 0.48), xytext=(0.35, 0.08),
           arrowprops=dict(arrowstyle='->', color='red',
                         linewidth=1.5, linestyle='dashed'))

ax.set_xlim(0, 1)
ax.set_ylim(0, 1)

plt.tight_layout()
plt.savefig('resultados/flujo_analisis_nolineal.png', dpi=300, bbox_inches='tight')
print("✓ Gráfica guardada en: resultados/flujo_analisis_nolineal.png")

plt.show()
