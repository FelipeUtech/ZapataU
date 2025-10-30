#!/usr/bin/env python3
"""
Visualizador Interactivo de Malla 3D - Modelo de Zapata en OpenSees
====================================================================

Este script permite visualizar la malla 3D del modelo de manera interactiva,
con capacidad de rotación, zoom y selección de componentes.

Autor: Claude AI
Fecha: 2025
"""

import openseespy.opensees as ops
import numpy as np
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import argparse


class VisualizadorMalla3D:
    """Visualizador interactivo de malla 3D"""

    def __init__(self, config_file='config_zapata.json'):
        self.config_file = config_file
        self.cargar_configuracion()
        self.nodos_coords = {}
        self.elementos = []

    def cargar_configuracion(self):
        """Carga la configuración"""
        with open(self.config_file, 'r') as f:
            self.config = json.load(f)
        print(f"✓ Configuración cargada desde {self.config_file}")

    def construir_modelo(self):
        """Construye el modelo para extraer la geometría"""
        print("\n" + "="*60)
        print("CONSTRUYENDO MODELO PARA VISUALIZACIÓN")
        print("="*60)

        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 3)

        # Construir el modelo simplificado
        self._crear_geometria_simple()

        print("\n✓ Modelo construido exitosamente")

    def _crear_geometria_simple(self):
        """Crea geometría simplificada para visualización"""
        geom_zap = self.config['geometria']['zapata']
        prof_desp = self.config['geometria']['profundidad_desplante']
        capas = self.config['suelo_estratificado']['capas']

        # Dimensiones
        B_x = geom_zap['ancho_x']
        B_y = geom_zap['ancho_y']
        h_zap = geom_zap['espesor']
        L_suelo_x = B_x * 2.5
        L_suelo_y = B_y * 2.5
        H_suelo_total = sum([c['espesor'] for c in capas])

        # Mallado
        nx_suelo, ny_suelo, nz_suelo = 6, 6, 6
        nx_zap, ny_zap, nz_zap = 4, 4, 2

        # Coordenadas Z
        z_base_suelo = -prof_desp - H_suelo_total
        z_base_zapata = -prof_desp
        z_top_zapata = z_base_zapata + h_zap

        node_counter = 1
        elem_counter = 1

        # === CREAR NODOS DEL SUELO ===
        print("  Creando nodos del suelo...")
        nodos_suelo = {}
        dx_suelo = L_suelo_x / nx_suelo
        dy_suelo = L_suelo_y / ny_suelo
        dz_suelo = H_suelo_total / nz_suelo

        for k in range(nz_suelo + 1):
            for j in range(ny_suelo + 1):
                for i in range(nx_suelo + 1):
                    x = -L_suelo_x/2 + i * dx_suelo
                    y = -L_suelo_y/2 + j * dy_suelo
                    z = z_base_suelo + k * dz_suelo

                    ops.node(node_counter, x, y, z)
                    self.nodos_coords[node_counter] = (x, y, z)
                    nodos_suelo[(i, j, k)] = node_counter
                    node_counter += 1

        # === CREAR NODOS DE LA ZAPATA ===
        print("  Creando nodos de la zapata...")
        nodos_zapata = {}
        dx_zap = B_x / nx_zap
        dy_zap = B_y / ny_zap
        dz_zap = h_zap / nz_zap

        i_start_zap = (nx_suelo - nx_zap) // 2
        j_start_zap = (ny_suelo - ny_zap) // 2
        k_base_zap = nz_suelo

        for k in range(nz_zap + 1):
            for j in range(ny_zap + 1):
                for i in range(nx_zap + 1):
                    x = -B_x/2 + i * dx_zap
                    y = -B_y/2 + j * dy_zap
                    z = z_base_zapata + k * dz_zap

                    if k == 0:
                        # Compartir nodos con suelo
                        i_suelo = min(max(0, int(round(i_start_zap + i * 1.5))), nx_suelo)
                        j_suelo = min(max(0, int(round(j_start_zap + j * 1.5))), ny_suelo)
                        k_suelo = k_base_zap

                        if (i_suelo, j_suelo, k_suelo) in nodos_suelo:
                            nodos_zapata[(i, j, k)] = nodos_suelo[(i_suelo, j_suelo, k_suelo)]
                        else:
                            ops.node(node_counter, x, y, z)
                            self.nodos_coords[node_counter] = (x, y, z)
                            nodos_zapata[(i, j, k)] = node_counter
                            node_counter += 1
                    else:
                        ops.node(node_counter, x, y, z)
                        self.nodos_coords[node_counter] = (x, y, z)
                        nodos_zapata[(i, j, k)] = node_counter
                        node_counter += 1

        # === CREAR ELEMENTOS DEL SUELO ===
        print("  Creando elementos del suelo...")
        elem_por_capa = nz_suelo // len(capas)

        for k in range(nz_suelo):
            capa_idx = min(k // elem_por_capa, len(capas) - 1)
            for j in range(ny_suelo):
                for i in range(nx_suelo):
                    n1 = nodos_suelo[(i, j, k)]
                    n2 = nodos_suelo[(i+1, j, k)]
                    n3 = nodos_suelo[(i+1, j+1, k)]
                    n4 = nodos_suelo[(i, j+1, k)]
                    n5 = nodos_suelo[(i, j, k+1)]
                    n6 = nodos_suelo[(i+1, j, k+1)]
                    n7 = nodos_suelo[(i+1, j+1, k+1)]
                    n8 = nodos_suelo[(i, j+1, k+1)]

                    self.elementos.append({
                        'id': elem_counter,
                        'tipo': 'suelo',
                        'capa': capas[capa_idx]['nombre'],
                        'nodos': [n1, n2, n3, n4, n5, n6, n7, n8]
                    })
                    elem_counter += 1

        # === CREAR ELEMENTOS DE LA ZAPATA ===
        print("  Creando elementos de la zapata...")
        for k in range(nz_zap):
            for j in range(ny_zap):
                for i in range(nx_zap):
                    n1 = nodos_zapata[(i, j, k)]
                    n2 = nodos_zapata[(i+1, j, k)]
                    n3 = nodos_zapata[(i+1, j+1, k)]
                    n4 = nodos_zapata[(i, j+1, k)]
                    n5 = nodos_zapata[(i, j, k+1)]
                    n6 = nodos_zapata[(i+1, j, k+1)]
                    n7 = nodos_zapata[(i+1, j+1, k+1)]
                    n8 = nodos_zapata[(i, j+1, k+1)]

                    self.elementos.append({
                        'id': elem_counter,
                        'tipo': 'zapata',
                        'capa': 'Concreto',
                        'nodos': [n1, n2, n3, n4, n5, n6, n7, n8]
                    })
                    elem_counter += 1

        print(f"\n  ✓ {len(self.nodos_coords)} nodos creados")
        print(f"  ✓ {len(self.elementos)} elementos creados")

    def crear_visualizacion_interactiva(self):
        """Crea visualización 3D interactiva con Plotly"""
        print("\n" + "="*60)
        print("CREANDO VISUALIZACIÓN INTERACTIVA")
        print("="*60)

        fig = go.Figure()

        # Colores por tipo
        colores = {
            'zapata': 'rgb(127, 140, 141)',  # Gris
            'Arcilla blanda': 'rgb(205, 133, 63)',  # Marrón claro
            'Arena limosa': 'rgb(222, 184, 135)',  # Beige
            'Grava arenosa': 'rgb(139, 69, 19)'  # Marrón oscuro
        }

        # Agrupar elementos por tipo/capa
        grupos = {}
        for elem in self.elementos:
            if elem['tipo'] == 'zapata':
                key = 'zapata'
            else:
                key = elem['capa']

            if key not in grupos:
                grupos[key] = []
            grupos[key].append(elem)

        # Dibujar cada grupo
        for nombre, elementos_grupo in grupos.items():
            print(f"  Dibujando {nombre}: {len(elementos_grupo)} elementos")

            # Extraer coordenadas para este grupo
            x_all, y_all, z_all = [], [], []
            i_all, j_all, k_all = [], [], []

            for elem in elementos_grupo:
                nodos = elem['nodos']

                # Obtener coordenadas de los 8 nodos del brick
                coords = [self.nodos_coords[n] for n in nodos]

                # Para brick: caras son
                # Bottom: 0,1,2,3
                # Top: 4,5,6,7
                # Sides: conectar bottom y top

                # Definir las 6 caras del hexahedro
                caras = [
                    [0, 1, 2, 3],  # Bottom
                    [4, 5, 6, 7],  # Top
                    [0, 1, 5, 4],  # Front
                    [2, 3, 7, 6],  # Back
                    [0, 3, 7, 4],  # Left
                    [1, 2, 6, 5],  # Right
                ]

                # Para mesh3d, necesitamos triangular cada cara
                for cara in caras:
                    # Dividir cara cuadrada en 2 triángulos
                    i_all.extend([cara[0], cara[0]])
                    j_all.extend([cara[1], cara[2]])
                    k_all.extend([cara[2], cara[3]])

                    for idx in [cara[0], cara[1], cara[2], cara[0], cara[2], cara[3]]:
                        x_all.append(coords[idx][0])
                        y_all.append(coords[idx][1])
                        z_all.append(coords[idx][2])

            # Crear mesh para este grupo
            color = colores.get(nombre, 'rgb(150, 150, 150)')

            fig.add_trace(go.Mesh3d(
                x=x_all,
                y=y_all,
                z=z_all,
                alphahull=0,
                opacity=0.5 if nombre != 'zapata' else 0.8,
                color=color,
                name=nombre,
                hovertemplate=f'<b>{nombre}</b><br>' +
                             'x: %{x:.2f}<br>' +
                             'y: %{y:.2f}<br>' +
                             'z: %{z:.2f}<br>' +
                             '<extra></extra>',
            ))

        # Añadir nodos como puntos (opcional, solo algunos)
        print("  Añadiendo nodos clave...")
        nodos_mostrar = list(self.nodos_coords.keys())[::10]  # Cada 10 nodos
        x_nodos = [self.nodos_coords[n][0] for n in nodos_mostrar]
        y_nodos = [self.nodos_coords[n][1] for n in nodos_mostrar]
        z_nodos = [self.nodos_coords[n][2] for n in nodos_mostrar]

        fig.add_trace(go.Scatter3d(
            x=x_nodos,
            y=y_nodos,
            z=z_nodos,
            mode='markers',
            marker=dict(size=2, color='red'),
            name='Nodos',
            hovertemplate='Nodo<br>x: %{x:.2f}<br>y: %{y:.2f}<br>z: %{z:.2f}<extra></extra>',
        ))

        # Configurar layout
        fig.update_layout(
            title={
                'text': 'Visualización Interactiva de Malla 3D - Modelo de Zapata<br>' +
                       '<sub>Usa el mouse para rotar, zoom y desplazar</sub>',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18}
            },
            scene=dict(
                xaxis_title='X (m)',
                yaxis_title='Y (m)',
                zaxis_title='Z (m)',
                aspectmode='data',
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.2)
                ),
                xaxis=dict(backgroundcolor="rgb(240, 240, 240)",
                          gridcolor="white",
                          showbackground=True),
                yaxis=dict(backgroundcolor="rgb(240, 240, 240)",
                          gridcolor="white",
                          showbackground=True),
                zaxis=dict(backgroundcolor="rgb(240, 240, 240)",
                          gridcolor="white",
                          showbackground=True),
            ),
            width=1200,
            height=900,
            showlegend=True,
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='black',
                borderwidth=1
            ),
            hovermode='closest'
        )

        return fig

    def guardar_html(self, fig, filename='malla_3d_interactiva.html'):
        """Guarda la visualización como HTML"""
        fig.write_html(filename)
        print(f"\n✓ Visualización guardada en: {filename}")
        print(f"  Abre el archivo en un navegador web para ver la malla 3D interactiva")

    def mostrar(self, fig):
        """Muestra la visualización en el navegador"""
        fig.show()

    def ejecutar(self, guardar=True, mostrar=True):
        """Ejecuta el visualizador completo"""
        print("\n" + "#"*60)
        print("# VISUALIZADOR INTERACTIVO DE MALLA 3D")
        print("#"*60)

        try:
            self.construir_modelo()
            fig = self.crear_visualizacion_interactiva()

            if guardar:
                self.guardar_html(fig)

            if mostrar:
                print("\n  Abriendo visualización en navegador...")
                self.mostrar(fig)

            print("\n" + "="*60)
            print("VISUALIZACIÓN COMPLETADA")
            print("="*60)
            print("\nControles:")
            print("  • Click izquierdo + arrastrar: Rotar")
            print("  • Scroll: Zoom in/out")
            print("  • Click derecho + arrastrar: Desplazar (pan)")
            print("  • Click en leyenda: Mostrar/ocultar componentes")
            print("  • Hover sobre elementos: Ver información")

            return True

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Visualizador interactivo de malla 3D para modelo de zapata'
    )
    parser.add_argument('--config', type=str, default='config_zapata.json',
                       help='Archivo de configuración')
    parser.add_argument('--no-show', action='store_true',
                       help='No abrir en navegador automáticamente')
    parser.add_argument('--output', type=str, default='malla_3d_interactiva.html',
                       help='Archivo de salida HTML')

    args = parser.parse_args()

    visualizador = VisualizadorMalla3D(config_file=args.config)
    visualizador.ejecutar(guardar=True, mostrar=not args.no_show)


if __name__ == '__main__':
    main()
