#!/usr/bin/env python3
"""
Genera capturas estáticas de la malla 3D interactiva
"""

import sys
sys.path.insert(0, '/home/user/ZapataU')

from visualizar_malla_3d import VisualizadorMalla3D
import plotly.graph_objects as go

def generar_capturas():
    """Genera múltiples vistas de la malla"""
    print("Generando capturas de la malla 3D...")

    visualizador = VisualizadorMalla3D()
    visualizador.construir_modelo()
    fig = visualizador.crear_visualizacion_interactiva()

    # Vista 1: Isométrica
    fig.update_layout(
        scene_camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))
    )
    fig.write_image("ejemplos/resultados/malla_3d_vista1.png", width=1200, height=900)
    print("✓ Vista isométrica guardada")

    # Vista 2: Frontal
    fig.update_layout(
        scene_camera=dict(eye=dict(x=0, y=-2, z=0.5))
    )
    fig.write_image("ejemplos/resultados/malla_3d_vista2.png", width=1200, height=900)
    print("✓ Vista frontal guardada")

    # Vista 3: Lateral
    fig.update_layout(
        scene_camera=dict(eye=dict(x=2, y=0, z=0.5))
    )
    fig.write_image("ejemplos/resultados/malla_3d_vista3.png", width=1200, height=900)
    print("✓ Vista lateral guardada")

    print("\n✓ Todas las capturas generadas en ejemplos/resultados/")

if __name__ == '__main__':
    try:
        generar_capturas()
    except Exception as e:
        print(f"Error: {e}")
        print("\nGenerando vista simple con matplotlib...")

        # Fallback a matplotlib
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D

        visualizador = VisualizadorMalla3D()
        visualizador.construir_modelo()

        fig = plt.figure(figsize=(14, 10))
        ax = fig.add_subplot(111, projection='3d')

        # Dibujar nodos por tipo
        for elem in visualizador.elementos[:50]:  # Solo primeros 50 elementos
            nodos = elem['nodos']
            coords = [visualizador.nodos_coords[n] for n in nodos]

            # Dibujar líneas del elemento
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            zs = [c[2] for c in coords]

            color = 'gray' if elem['tipo'] == 'zapata' else 'brown'
            ax.scatter(xs, ys, zs, c=color, marker='o', s=5, alpha=0.5)

        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Z (m)')
        ax.set_title('Malla 3D - Vista Simplificada')

        plt.savefig('ejemplos/resultados/malla_3d_simple.png', dpi=200, bbox_inches='tight')
        print("✓ Vista simplificada guardada en ejemplos/resultados/malla_3d_simple.png")
