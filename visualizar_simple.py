#!/usr/bin/env python3
"""
Visualización de resultados del modelo simplificado
"""

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D

# Datos del modelo
z_base = -11.50
z_base_zapata = -1.50
z_top_zapata = -0.90
z_top_pedestal = -0.40

# Desplazamientos (en mm)
disp_top = [12.554, -12.298, 29.042]  # Ux, Uy, Uz
disp_base_zapata = [5.800, 0.000, 29.000]

# Cargas aplicadas
Fz = 500  # kN
Fx = 50   # kN
Momento = 100  # kN·m

# Crear figura con múltiples subplots
fig = plt.figure(figsize=(16, 10))

# 1. Vista 3D del modelo con deformación
ax1 = fig.add_subplot(221, projection='3d')

# Geometría original
z_original = [z_base, z_base_zapata, z_top_zapata, z_top_pedestal]
x_original = [0, 0, 0, 0]
y_original = [0, 0, 0, 0]

# Geometría deformada (escala exagerada para visualización)
escala = 50
z_deformed = [
    z_base,
    z_base_zapata + disp_base_zapata[2]/1000,
    z_top_zapata + disp_base_zapata[2]/1000,
    z_top_pedestal + disp_top[2]/1000
]
x_deformed = [
    0,
    disp_base_zapata[0]/1000 * escala,
    disp_base_zapata[0]/1000 * escala,
    disp_top[0]/1000 * escala
]
y_deformed = [
    0,
    disp_base_zapata[1]/1000 * escala,
    disp_base_zapata[1]/1000 * escala,
    disp_top[1]/1000 * escala
]

# Dibujar configuración original
ax1.plot(x_original, y_original, z_original, 'b--', linewidth=2, label='Original', alpha=0.5)
ax1.plot(x_deformed, y_deformed, z_deformed, 'r-', linewidth=3, label='Deformada (×50)')

# Marcar puntos importantes
ax1.scatter([0], [0], [z_base], c='green', s=100, marker='s', label='Base fija')
ax1.scatter([x_deformed[1]], [y_deformed[1]], [z_deformed[1]], c='orange', s=100, marker='o', label='Base zapata')
ax1.scatter([x_deformed[3]], [y_deformed[3]], [z_deformed[3]], c='red', s=100, marker='^', label='Punto de carga')

# Dibujar zapata como un rectángulo
zapata_x = [-1.25, 1.25, 1.25, -1.25, -1.25]
zapata_y = [-1.25, -1.25, 1.25, 1.25, -1.25]
zapata_z = [z_base_zapata] * 5
ax1.plot(zapata_x, zapata_y, zapata_z, 'b-', linewidth=2, alpha=0.3)

ax1.set_xlabel('X (m)', fontsize=10)
ax1.set_ylabel('Y (m)', fontsize=10)
ax1.set_zlabel('Z (m)', fontsize=10)
ax1.set_title('Modelo 3D - Configuración y Deformada', fontsize=12, fontweight='bold')
ax1.legend(fontsize=8)
ax1.grid(True, alpha=0.3)

# 2. Desplazamientos horizontales y verticales
ax2 = fig.add_subplot(222)

posiciones = ['Base\nFija', 'Base\nZapata', 'Top\nZapata', 'Top\nPedestal']
desplaz_horiz = [0, np.sqrt(disp_base_zapata[0]**2 + disp_base_zapata[1]**2),
                np.sqrt(disp_base_zapata[0]**2 + disp_base_zapata[1]**2),
                np.sqrt(disp_top[0]**2 + disp_top[1]**2)]
desplaz_vert = [0, disp_base_zapata[2], disp_base_zapata[2], disp_top[2]]

x = np.arange(len(posiciones))
width = 0.35

bars1 = ax2.bar(x - width/2, desplaz_horiz, width, label='Horiz.', color='steelblue')
bars2 = ax2.bar(x + width/2, desplaz_vert, width, label='Vert.', color='coral')

ax2.set_ylabel('Desplazamiento (mm)', fontsize=11)
ax2.set_title('Desplazamientos en Puntos Clave', fontsize=12, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(posiciones, fontsize=9)
ax2.legend()
ax2.grid(True, alpha=0.3, axis='y')

# Añadir valores sobre las barras
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        if height > 0.1:
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}',
                    ha='center', va='bottom', fontsize=8)

# 3. Cargas aplicadas
ax3 = fig.add_subplot(223)

cargas_nombres = ['Vertical\n(Fz)', 'Horizontal\n(Fx)', 'Horizontal\n(Fy)', 'Momento\n(Mx)']
cargas_valores = [Fz, Fx, 0, Momento]
colores = ['darkred', 'darkblue', 'darkgreen', 'purple']

bars = ax3.bar(cargas_nombres, cargas_valores, color=colores, alpha=0.7, edgecolor='black')
ax3.set_ylabel('Magnitud (kN, kN·m)', fontsize=11)
ax3.set_title('Cargas Aplicadas en el Pedestal', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='y')

# Añadir valores sobre las barras
for bar in bars:
    height = bar.get_height()
    if abs(height) > 0.1:
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}',
                ha='center', va='bottom' if height > 0 else 'top', fontsize=10, fontweight='bold')

# 4. Tabla de resultados
ax4 = fig.add_subplot(224)
ax4.axis('off')

# Crear tabla con resultados
tabla_data = [
    ['PARÁMETRO', 'VALOR'],
    ['', ''],
    ['DESPLAZAMIENTOS - Punto de Carga:', ''],
    ['  Horizontal X', f'{disp_top[0]:.2f} mm'],
    ['  Horizontal Y', f'{disp_top[1]:.2f} mm'],
    ['  Vertical (asentamiento)', f'{disp_top[2]:.2f} mm'],
    ['  Magnitud horizontal total', f'{np.sqrt(disp_top[0]**2 + disp_top[1]**2):.2f} mm'],
    ['', ''],
    ['DESPLAZAMIENTOS - Base de Zapata:', ''],
    ['  Horizontal X', f'{disp_base_zapata[0]:.2f} mm'],
    ['  Vertical (asentamiento)', f'{disp_base_zapata[2]:.2f} mm'],
    ['', ''],
    ['CARGAS APLICADAS:', ''],
    ['  Carga vertical', f'{Fz:.0f} kN'],
    ['  Carga horizontal X', f'{Fx:.0f} kN'],
    ['  Momento X', f'{Momento:.0f} kN·m'],
    ['', ''],
    ['GEOMETRÍA:', ''],
    ['  Zapata', '2.5 × 2.5 × 0.6 m'],
    ['  Profundidad desplante', '1.5 m'],
    ['  Pedestal', '0.5 m altura'],
]

# Colores alternados para filas
colores_filas = []
for i, row in enumerate(tabla_data):
    if row[0].startswith('  '):
        colores_filas.append('#f0f0f0')
    elif row[0] and not ':' in row[0]:
        colores_filas.append('#e0e0ff')
    else:
        colores_filas.append('white')

table = ax4.table(cellText=tabla_data, cellLoc='left',
                 loc='center', colWidths=[0.6, 0.4],
                 cellColours=[[colores_filas[i]]*2 for i in range(len(tabla_data))])

table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1, 1.8)

# Estilo de la primera fila (encabezado)
for i in range(2):
    cell = table[(0, i)]
    cell.set_facecolor('#4472C4')
    cell.set_text_props(weight='bold', color='white')

ax4.set_title('Resumen de Resultados', fontsize=12, fontweight='bold', pad=20)

plt.suptitle('MODELO DE ZAPATA CON SUELO ESTRATIFICADO - OpenSees',
            fontsize=14, fontweight='bold', y=0.98)

plt.tight_layout()
plt.savefig('resultados/graficas_modelo_zapata.png', dpi=300, bbox_inches='tight')
print("✓ Gráfica guardada en: resultados/graficas_modelo_zapata.png")

plt.show()
