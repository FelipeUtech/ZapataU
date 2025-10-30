#!/usr/bin/env python3
"""
Script para visualizar resultados del modelo de zapata en OpenSees

Este script lee los archivos de resultados generados por opensees_zapata_model.py
y genera gráficas de desplazamientos, reacciones y distribución de presiones.

Autor: Claude AI
Fecha: 2025
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import os
import glob
import argparse


def leer_desplazamientos(archivo):
    """
    Lee el archivo de desplazamientos

    Args:
        archivo (str): Ruta al archivo de desplazamientos

    Returns:
        dict: Diccionario con arrays de coordenadas y desplazamientos
    """
    datos = np.loadtxt(archivo, delimiter=',', skiprows=1)

    return {
        'nodos': datos[:, 0].astype(int),
        'X': datos[:, 1],
        'Y': datos[:, 2],
        'Z': datos[:, 3],
        'Ux': datos[:, 4],
        'Uy': datos[:, 5],
        'Uz': datos[:, 6]
    }


def leer_reacciones(archivo):
    """
    Lee el archivo de reacciones

    Args:
        archivo (str): Ruta al archivo de reacciones

    Returns:
        dict: Diccionario con arrays de coordenadas y reacciones
    """
    try:
        datos = np.loadtxt(archivo, delimiter=',', skiprows=1)

        if datos.size == 0:
            return None

        return {
            'nodos': datos[:, 0].astype(int),
            'X': datos[:, 1],
            'Y': datos[:, 2],
            'Z': datos[:, 3],
            'Rx': datos[:, 4],
            'Ry': datos[:, 5],
            'Rz': datos[:, 6]
        }
    except:
        return None


def graficar_desplazamientos_3d(datos, output_file='desplazamientos_3d.png'):
    """
    Crea gráfica 3D de desplazamientos

    Args:
        datos (dict): Datos de desplazamientos
        output_file (str): Nombre del archivo de salida
    """
    fig = plt.figure(figsize=(15, 5))

    # Desplazamiento en X
    ax1 = fig.add_subplot(131, projection='3d')
    scatter1 = ax1.scatter(datos['X'], datos['Y'], datos['Z'],
                          c=datos['Ux']*1000, cmap='RdBu_r', s=10)
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_zlabel('Z (m)')
    ax1.set_title('Desplazamiento Ux (mm)')
    plt.colorbar(scatter1, ax=ax1, label='Ux (mm)')

    # Desplazamiento en Y
    ax2 = fig.add_subplot(132, projection='3d')
    scatter2 = ax2.scatter(datos['X'], datos['Y'], datos['Z'],
                          c=datos['Uy']*1000, cmap='RdBu_r', s=10)
    ax2.set_xlabel('X (m)')
    ax2.set_ylabel('Y (m)')
    ax2.set_zlabel('Z (m)')
    ax2.set_title('Desplazamiento Uy (mm)')
    plt.colorbar(scatter2, ax=ax2, label='Uy (mm)')

    # Desplazamiento en Z
    ax3 = fig.add_subplot(133, projection='3d')
    scatter3 = ax3.scatter(datos['X'], datos['Y'], datos['Z'],
                          c=datos['Uz']*1000, cmap='RdBu_r', s=10)
    ax3.set_xlabel('X (m)')
    ax3.set_ylabel('Y (m)')
    ax3.set_zlabel('Z (m)')
    ax3.set_title('Desplazamiento Uz (mm)')
    plt.colorbar(scatter3, ax=ax3, label='Uz (mm)')

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Gráfica guardada: {output_file}")
    plt.close()


def graficar_desplazamientos_vertical(datos, output_file='desplazamientos_vertical.png'):
    """
    Crea gráfica de desplazamiento vertical vs profundidad

    Args:
        datos (dict): Datos de desplazamientos
        output_file (str): Nombre del archivo de salida
    """
    # Filtrar nodos cerca del centro (X~0, Y~0)
    mask = (np.abs(datos['X']) < 0.3) & (np.abs(datos['Y']) < 0.3)
    z_centro = datos['Z'][mask]
    uz_centro = datos['Uz'][mask] * 1000  # Convertir a mm

    # Ordenar por Z
    idx_sort = np.argsort(z_centro)
    z_centro = z_centro[idx_sort]
    uz_centro = uz_centro[idx_sort]

    plt.figure(figsize=(8, 10))
    plt.plot(uz_centro, z_centro, 'b.-', linewidth=2, markersize=8)
    plt.xlabel('Desplazamiento Vertical Uz (mm)', fontsize=12)
    plt.ylabel('Elevación Z (m)', fontsize=12)
    plt.title('Desplazamiento Vertical vs Profundidad\n(Nodos en el centro)', fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.axvline(x=0, color='k', linestyle='--', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Gráfica guardada: {output_file}")
    plt.close()


def graficar_magnitud_desplazamientos(datos, output_file='magnitud_desplazamientos.png'):
    """
    Crea gráfica de magnitud total de desplazamientos

    Args:
        datos (dict): Datos de desplazamientos
        output_file (str): Nombre del archivo de salida
    """
    # Calcular magnitud total
    magnitud = np.sqrt(datos['Ux']**2 + datos['Uy']**2 + datos['Uz']**2) * 1000

    fig = plt.figure(figsize=(12, 5))

    # Vista 3D
    ax1 = fig.add_subplot(121, projection='3d')
    scatter = ax1.scatter(datos['X'], datos['Y'], datos['Z'],
                         c=magnitud, cmap='hot', s=10)
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_zlabel('Z (m)')
    ax1.set_title('Magnitud de Desplazamiento Total')
    plt.colorbar(scatter, ax=ax1, label='Magnitud (mm)')

    # Histograma
    ax2 = fig.add_subplot(122)
    ax2.hist(magnitud, bins=50, edgecolor='black', alpha=0.7)
    ax2.set_xlabel('Magnitud de Desplazamiento (mm)', fontsize=12)
    ax2.set_ylabel('Frecuencia', fontsize=12)
    ax2.set_title('Distribución de Desplazamientos')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Gráfica guardada: {output_file}")
    plt.close()


def graficar_reacciones(datos_reac, output_file='reacciones.png'):
    """
    Crea gráfica de reacciones en la base

    Args:
        datos_reac (dict): Datos de reacciones
        output_file (str): Nombre del archivo de salida
    """
    if datos_reac is None:
        print("✗ No hay datos de reacciones para graficar")
        return

    fig = plt.figure(figsize=(15, 5))

    # Reacción en Z (vertical)
    ax1 = fig.add_subplot(131)
    scatter1 = ax1.scatter(datos_reac['X'], datos_reac['Y'],
                          c=datos_reac['Rz']/1000, cmap='viridis', s=50)
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_title('Reacción Vertical Rz (kN)')
    ax1.set_aspect('equal')
    plt.colorbar(scatter1, ax=ax1, label='Rz (kN)')
    ax1.grid(True, alpha=0.3)

    # Reacción en X (horizontal)
    ax2 = fig.add_subplot(132)
    scatter2 = ax2.scatter(datos_reac['X'], datos_reac['Y'],
                          c=datos_reac['Rx']/1000, cmap='RdBu_r', s=50)
    ax2.set_xlabel('X (m)')
    ax2.set_ylabel('Y (m)')
    ax2.set_title('Reacción Horizontal Rx (kN)')
    ax2.set_aspect('equal')
    plt.colorbar(scatter2, ax=ax2, label='Rx (kN)')
    ax2.grid(True, alpha=0.3)

    # Reacción en Y (horizontal)
    ax3 = fig.add_subplot(133)
    scatter3 = ax3.scatter(datos_reac['X'], datos_reac['Y'],
                          c=datos_reac['Ry']/1000, cmap='RdBu_r', s=50)
    ax3.set_xlabel('X (m)')
    ax3.set_ylabel('Y (m)')
    ax3.set_title('Reacción Horizontal Ry (kN)')
    ax3.set_aspect('equal')
    plt.colorbar(scatter3, ax=ax3, label='Ry (kN)')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Gráfica guardada: {output_file}")
    plt.close()


def crear_resumen_visual(datos, datos_reac, output_file='resumen_visual.png'):
    """
    Crea una gráfica de resumen con información clave

    Args:
        datos (dict): Datos de desplazamientos
        datos_reac (dict): Datos de reacciones
        output_file (str): Nombre del archivo de salida
    """
    fig = plt.figure(figsize=(14, 10))

    # 1. Vista 3D de la estructura
    ax1 = fig.add_subplot(221, projection='3d')
    scatter = ax1.scatter(datos['X'], datos['Y'], datos['Z'],
                         c=datos['Z'], cmap='terrain', s=5, alpha=0.6)
    ax1.set_xlabel('X (m)')
    ax1.set_ylabel('Y (m)')
    ax1.set_zlabel('Z (m)')
    ax1.set_title('Geometría del Modelo', fontsize=12, fontweight='bold')

    # 2. Desplazamiento vertical
    ax2 = fig.add_subplot(222)
    mask = (np.abs(datos['X']) < 0.3) & (np.abs(datos['Y']) < 0.3)
    z_centro = datos['Z'][mask]
    uz_centro = datos['Uz'][mask] * 1000
    idx_sort = np.argsort(z_centro)
    ax2.plot(uz_centro[idx_sort], z_centro[idx_sort], 'b.-', linewidth=2)
    ax2.set_xlabel('Despl. Vertical (mm)', fontsize=10)
    ax2.set_ylabel('Elevación (m)', fontsize=10)
    ax2.set_title('Desplazamiento Vertical', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.axvline(x=0, color='k', linestyle='--', alpha=0.3)

    # 3. Magnitud de desplazamientos
    ax3 = fig.add_subplot(223, projection='3d')
    magnitud = np.sqrt(datos['Ux']**2 + datos['Uy']**2 + datos['Uz']**2) * 1000
    scatter3 = ax3.scatter(datos['X'], datos['Y'], datos['Z'],
                          c=magnitud, cmap='hot', s=10)
    ax3.set_xlabel('X (m)')
    ax3.set_ylabel('Y (m)')
    ax3.set_zlabel('Z (m)')
    ax3.set_title('Magnitud de Desplazamientos', fontsize=12, fontweight='bold')
    cbar3 = plt.colorbar(scatter3, ax=ax3, pad=0.1, shrink=0.8)
    cbar3.set_label('mm', fontsize=9)

    # 4. Estadísticas
    ax4 = fig.add_subplot(224)
    ax4.axis('off')

    stats_text = "ESTADÍSTICAS DEL ANÁLISIS\n" + "="*35 + "\n\n"
    stats_text += f"Desplazamientos:\n"
    stats_text += f"  Ux máx: {np.max(np.abs(datos['Ux']))*1000:.3f} mm\n"
    stats_text += f"  Uy máx: {np.max(np.abs(datos['Uy']))*1000:.3f} mm\n"
    stats_text += f"  Uz máx: {np.max(np.abs(datos['Uz']))*1000:.3f} mm\n"
    stats_text += f"  Uz mín: {np.min(datos['Uz'])*1000:.3f} mm\n"
    stats_text += f"  Magnitud máx: {np.max(magnitud):.3f} mm\n\n"

    if datos_reac is not None:
        stats_text += f"Reacciones totales:\n"
        stats_text += f"  Rx: {np.sum(datos_reac['Rx'])/1000:.2f} kN\n"
        stats_text += f"  Ry: {np.sum(datos_reac['Ry'])/1000:.2f} kN\n"
        stats_text += f"  Rz: {np.sum(datos_reac['Rz'])/1000:.2f} kN\n\n"

    stats_text += f"Número de nodos: {len(datos['nodos'])}\n"

    ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes,
            fontsize=11, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    plt.suptitle('Resumen del Análisis - Modelo de Zapata', fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Gráfica guardada: {output_file}")
    plt.close()


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Visualizar resultados del modelo de zapata en OpenSees'
    )
    parser.add_argument(
        '--carpeta',
        type=str,
        default='resultados',
        help='Carpeta con los archivos de resultados (default: resultados)'
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("VISUALIZACIÓN DE RESULTADOS - MODELO DE ZAPATA")
    print("="*60 + "\n")

    # Buscar archivos más recientes
    archivos_desp = glob.glob(os.path.join(args.carpeta, 'desplazamientos_*.txt'))
    archivos_reac = glob.glob(os.path.join(args.carpeta, 'reacciones_*.txt'))

    if not archivos_desp:
        print(f"✗ No se encontraron archivos de resultados en {args.carpeta}/")
        print("  Asegúrate de ejecutar primero: python opensees_zapata_model.py")
        return

    # Usar el archivo más reciente
    archivo_desp = max(archivos_desp, key=os.path.getctime)
    print(f"Leyendo: {archivo_desp}")

    # Leer datos
    datos = leer_desplazamientos(archivo_desp)
    print(f"✓ {len(datos['nodos'])} nodos leídos")

    datos_reac = None
    if archivos_reac:
        archivo_reac = max(archivos_reac, key=os.path.getctime)
        print(f"Leyendo: {archivo_reac}")
        datos_reac = leer_reacciones(archivo_reac)
        if datos_reac:
            print(f"✓ {len(datos_reac['nodos'])} reacciones leídas")

    # Crear carpeta para gráficas
    carpeta_graficas = os.path.join(args.carpeta, 'graficas')
    os.makedirs(carpeta_graficas, exist_ok=True)

    print(f"\nGenerando gráficas en {carpeta_graficas}/...")

    # Generar gráficas
    graficar_desplazamientos_3d(
        datos,
        os.path.join(carpeta_graficas, 'desplazamientos_3d.png')
    )

    graficar_desplazamientos_vertical(
        datos,
        os.path.join(carpeta_graficas, 'desplazamientos_vertical.png')
    )

    graficar_magnitud_desplazamientos(
        datos,
        os.path.join(carpeta_graficas, 'magnitud_desplazamientos.png')
    )

    if datos_reac:
        graficar_reacciones(
            datos_reac,
            os.path.join(carpeta_graficas, 'reacciones.png')
        )

    crear_resumen_visual(
        datos,
        datos_reac,
        os.path.join(carpeta_graficas, 'resumen_visual.png')
    )

    print("\n" + "="*60)
    print("VISUALIZACIÓN COMPLETADA")
    print("="*60)
    print(f"\nGráficas guardadas en: {carpeta_graficas}/")


if __name__ == '__main__':
    main()
