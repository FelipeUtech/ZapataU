#!/usr/bin/env python3
"""
Visualizador Mejorado de Malla 3D - Solo Puntos y Líneas
==========================================================

Versión mejorada que muestra la malla como puntos y líneas para
mejor visualización de la estructura.

Autor: Claude AI
Fecha: 2025
"""

import openseespy.opensees as ops
import numpy as np
import json
import plotly.graph_objects as go
import argparse


class VisualizadorMallaMejorado:
    """Visualizador mejorado con puntos y líneas"""

    def __init__(self, config_file='config_zapata.json'):
        self.config_file = config_file
        self.cargar_configuracion()
        self.nodos_coords = {}
        self.nodos_suelo = set()
        self.nodos_zapata = set()
        self.nodos_interfaz = set()
        self.elementos = []
        self.aristas = set()

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

        self._crear_geometria()

        print("\n✓ Modelo construido exitosamente")

    def _crear_geometria(self):
        """Crea geometría del modelo"""
        geom_zap = self.config['geometria']['zapata']
        geom_ped = self.config['geometria']['pedestal']
        prof_desp = self.config['geometria']['profundidad_desplante']
        capas = self.config['suelo_estratificado']['capas']

        # Dimensiones
        B_x = geom_zap['ancho_x']
        B_y = geom_zap['ancho_y']
        h_zap = geom_zap['espesor']
        h_ped = geom_ped['altura']
        L_suelo_x = B_x * 2.5
        L_suelo_y = B_y * 2.5
        H_suelo_total = sum([c['espesor'] for c in capas])

        # Mallado
        nx_suelo, ny_suelo = 6, 6
        nz_suelo_estratificado = 6
        nz_relleno = 2
        nz_total = nz_suelo_estratificado + nz_relleno
        nx_zap, ny_zap, nz_zap = 4, 4, 2
        nx_ped, ny_ped, nz_ped = 2, 2, 2

        # GEOMETRÍA CORRECTA: z=0 es la superficie
        z_superficie = 0.0
        z_base_zapata = -prof_desp
        z_top_zapata = z_base_zapata + h_zap
        z_base_suelo = z_base_zapata - H_suelo_total
        z_top_pedestal = z_top_zapata + h_ped
        H_relleno = z_superficie - z_top_zapata
        H_total = H_suelo_total + H_relleno

        node_counter = 1
        elem_counter = 1

        # === CREAR NODOS DEL SUELO Y RELLENO ===
        print("  Creando nodos del suelo...")
        nodos_suelo_map = {}
        dx_suelo = L_suelo_x / nx_suelo
        dy_suelo = L_suelo_y / ny_suelo
        dz_total = H_total / nz_total

        for k in range(nz_total + 1):
            for j in range(ny_suelo + 1):
                for i in range(nx_suelo + 1):
                    x = -L_suelo_x/2 + i * dx_suelo
                    y = -L_suelo_y/2 + j * dy_suelo
                    z = z_base_suelo + k * dz_total

                    ops.node(node_counter, x, y, z)
                    self.nodos_coords[node_counter] = (x, y, z)
                    self.nodos_suelo.add(node_counter)
                    nodos_suelo_map[(i, j, k)] = node_counter
                    node_counter += 1

        # === CREAR NODOS DE LA ZAPATA ===
        print("  Creando nodos de la zapata...")
        nodos_zapata_map = {}
        dx_zap = B_x / nx_zap
        dy_zap = B_y / ny_zap
        dz_zap = h_zap / nz_zap

        i_start_zap = (nx_suelo - nx_zap) // 2
        j_start_zap = (ny_suelo - ny_zap) // 2
        k_base_zap = nz_suelo_estratificado  # La zapata empieza en el nivel de la base de zapata

        for k in range(nz_zap + 1):
            for j in range(ny_zap + 1):
                for i in range(nx_zap + 1):
                    x = -B_x/2 + i * dx_zap
                    y = -B_y/2 + j * dy_zap
                    z = z_base_zapata + k * dz_zap

                    if k == 0:
                        # Compartir nodos con suelo (INTERFAZ)
                        i_suelo = min(max(0, int(round(i_start_zap + i * 1.5))), nx_suelo)
                        j_suelo = min(max(0, int(round(j_start_zap + j * 1.5))), ny_suelo)
                        k_suelo = k_base_zap

                        if (i_suelo, j_suelo, k_suelo) in nodos_suelo_map:
                            node_id = nodos_suelo_map[(i_suelo, j_suelo, k_suelo)]
                            nodos_zapata_map[(i, j, k)] = node_id
                            # Marcar como nodo de interfaz
                            self.nodos_interfaz.add(node_id)
                            if node_id in self.nodos_suelo:
                                self.nodos_suelo.remove(node_id)
                        else:
                            ops.node(node_counter, x, y, z)
                            self.nodos_coords[node_counter] = (x, y, z)
                            self.nodos_zapata.add(node_counter)
                            nodos_zapata_map[(i, j, k)] = node_counter
                            node_counter += 1
                    else:
                        ops.node(node_counter, x, y, z)
                        self.nodos_coords[node_counter] = (x, y, z)
                        self.nodos_zapata.add(node_counter)
                        nodos_zapata_map[(i, j, k)] = node_counter
                        node_counter += 1

        # === CREAR NODOS DEL PEDESTAL ===
        print("  Creando nodos del pedestal...")
        nodos_pedestal_map = {}
        dx_ped = geom_ped['ancho_x'] / nx_ped
        dy_ped = geom_ped['ancho_y'] / ny_ped
        dz_ped = h_ped / nz_ped

        for k in range(nz_ped + 1):
            for j in range(ny_ped + 1):
                for i in range(nx_ped + 1):
                    x = -geom_ped['ancho_x']/2 + i * dx_ped
                    y = -geom_ped['ancho_y']/2 + j * dy_ped
                    z = z_top_zapata + k * dz_ped

                    if k == 0:
                        # Conectar con zapata superior
                        i_zap = min(int(round(i * nx_zap / nx_ped)), nx_zap)
                        j_zap = min(int(round(j * ny_zap / ny_ped)), ny_zap)
                        k_zap = nz_zap

                        if (i_zap, j_zap, k_zap) in nodos_zapata_map:
                            nodos_pedestal_map[(i, j, k)] = nodos_zapata_map[(i_zap, j_zap, k_zap)]
                        else:
                            ops.node(node_counter, x, y, z)
                            self.nodos_coords[node_counter] = (x, y, z)
                            self.nodos_zapata.add(node_counter)
                            nodos_pedestal_map[(i, j, k)] = node_counter
                            node_counter += 1
                    else:
                        ops.node(node_counter, x, y, z)
                        self.nodos_coords[node_counter] = (x, y, z)
                        self.nodos_zapata.add(node_counter)
                        nodos_pedestal_map[(i, j, k)] = node_counter
                        node_counter += 1

        # === CREAR ELEMENTOS Y EXTRAER ARISTAS ===
        print("  Creando elementos y extrayendo aristas...")

        # Determinar región de la zapata
        i_min_zap = i_start_zap
        i_max_zap = i_start_zap + nx_zap
        j_min_zap = j_start_zap
        j_max_zap = j_start_zap + ny_zap
        k_min_zap = nz_suelo_estratificado
        k_max_zap = k_min_zap + nz_zap

        # Elementos del suelo y relleno (omitiendo región de zapata)
        for k in range(nz_total):
            for j in range(ny_suelo):
                for i in range(nx_suelo):
                    # Verificar si este elemento está en la región de la zapata
                    en_region_zapata = (k >= k_min_zap and k < k_max_zap and
                                       i >= i_min_zap and i < i_max_zap and
                                       j >= j_min_zap and j < j_max_zap)

                    # Si está en la región de la zapata, NO crear elemento
                    if en_region_zapata:
                        continue

                    nodos = [
                        nodos_suelo_map[(i, j, k)],
                        nodos_suelo_map[(i+1, j, k)],
                        nodos_suelo_map[(i+1, j+1, k)],
                        nodos_suelo_map[(i, j+1, k)],
                        nodos_suelo_map[(i, j, k+1)],
                        nodos_suelo_map[(i+1, j, k+1)],
                        nodos_suelo_map[(i+1, j+1, k+1)],
                        nodos_suelo_map[(i, j+1, k+1)]
                    ]
                    self._agregar_aristas_brick(nodos)

        # Elementos de la zapata
        for k in range(nz_zap):
            for j in range(ny_zap):
                for i in range(nx_zap):
                    nodos = [
                        nodos_zapata_map[(i, j, k)],
                        nodos_zapata_map[(i+1, j, k)],
                        nodos_zapata_map[(i+1, j+1, k)],
                        nodos_zapata_map[(i, j+1, k)],
                        nodos_zapata_map[(i, j, k+1)],
                        nodos_zapata_map[(i+1, j, k+1)],
                        nodos_zapata_map[(i+1, j+1, k+1)],
                        nodos_zapata_map[(i, j+1, k+1)]
                    ]
                    self._agregar_aristas_brick(nodos)

        # Elementos del pedestal
        for k in range(nz_ped):
            for j in range(ny_ped):
                for i in range(nx_ped):
                    nodos = [
                        nodos_pedestal_map[(i, j, k)],
                        nodos_pedestal_map[(i+1, j, k)],
                        nodos_pedestal_map[(i+1, j+1, k)],
                        nodos_pedestal_map[(i, j+1, k)],
                        nodos_pedestal_map[(i, j, k+1)],
                        nodos_pedestal_map[(i+1, j, k+1)],
                        nodos_pedestal_map[(i+1, j+1, k+1)],
                        nodos_pedestal_map[(i, j+1, k+1)]
                    ]
                    self._agregar_aristas_brick(nodos)

        print(f"\n  ✓ {len(self.nodos_coords)} nodos totales")
        print(f"  ✓ {len(self.nodos_suelo)} nodos de suelo (café)")
        print(f"  ✓ {len(self.nodos_zapata)} nodos de zapata/pedestal (gris)")
        print(f"  ✓ {len(self.nodos_interfaz)} nodos de interfaz (rojo)")
        print(f"  ✓ {len(self.aristas)} aristas (líneas)")

    def _agregar_aristas_brick(self, nodos):
        """Agrega las aristas de un elemento brick"""
        # Aristas de la base (4 aristas)
        aristas_brick = [
            (nodos[0], nodos[1]),
            (nodos[1], nodos[2]),
            (nodos[2], nodos[3]),
            (nodos[3], nodos[0]),
            # Aristas de la tapa (4 aristas)
            (nodos[4], nodos[5]),
            (nodos[5], nodos[6]),
            (nodos[6], nodos[7]),
            (nodos[7], nodos[4]),
            # Aristas verticales (4 aristas)
            (nodos[0], nodos[4]),
            (nodos[1], nodos[5]),
            (nodos[2], nodos[6]),
            (nodos[3], nodos[7])
        ]

        for n1, n2 in aristas_brick:
            # Guardar como tupla ordenada para evitar duplicados
            arista = tuple(sorted([n1, n2]))
            self.aristas.add(arista)

    def crear_visualizacion_mejorada(self):
        """Crea visualización mejorada con puntos y líneas"""
        print("\n" + "="*60)
        print("CREANDO VISUALIZACIÓN MEJORADA")
        print("="*60)

        fig = go.Figure()

        # === 1. DIBUJAR LÍNEAS (ARISTAS) ===
        print("  Dibujando aristas...")
        x_lineas, y_lineas, z_lineas = [], [], []

        for n1, n2 in self.aristas:
            coord1 = self.nodos_coords[n1]
            coord2 = self.nodos_coords[n2]

            x_lineas.extend([coord1[0], coord2[0], None])
            y_lineas.extend([coord1[1], coord2[1], None])
            z_lineas.extend([coord1[2], coord2[2], None])

        fig.add_trace(go.Scatter3d(
            x=x_lineas,
            y=y_lineas,
            z=z_lineas,
            mode='lines',
            line=dict(color='lightgray', width=1),
            name='Aristas',
            hoverinfo='skip',
            showlegend=True
        ))

        # === 2. DIBUJAR NODOS DE SUELO (CAFÉ) ===
        print("  Dibujando nodos de suelo...")
        x_suelo = [self.nodos_coords[n][0] for n in self.nodos_suelo]
        y_suelo = [self.nodos_coords[n][1] for n in self.nodos_suelo]
        z_suelo = [self.nodos_coords[n][2] for n in self.nodos_suelo]

        fig.add_trace(go.Scatter3d(
            x=x_suelo,
            y=y_suelo,
            z=z_suelo,
            mode='markers',
            marker=dict(
                size=4,
                color='#8B4513',  # Café (saddle brown)
                symbol='circle',
                line=dict(color='black', width=0.5)
            ),
            name=f'Suelo ({len(self.nodos_suelo)} nodos)',
            hovertemplate='<b>Nodo Suelo</b><br>x: %{x:.2f} m<br>y: %{y:.2f} m<br>z: %{z:.2f} m<extra></extra>'
        ))

        # === 3. DIBUJAR NODOS DE ZAPATA/PEDESTAL (GRIS) ===
        print("  Dibujando nodos de zapata/pedestal...")
        x_zapata = [self.nodos_coords[n][0] for n in self.nodos_zapata]
        y_zapata = [self.nodos_coords[n][1] for n in self.nodos_zapata]
        z_zapata = [self.nodos_coords[n][2] for n in self.nodos_zapata]

        fig.add_trace(go.Scatter3d(
            x=x_zapata,
            y=y_zapata,
            z=z_zapata,
            mode='markers',
            marker=dict(
                size=5,
                color='#808080',  # Gris
                symbol='circle',
                line=dict(color='black', width=0.5)
            ),
            name=f'Zapata/Pedestal ({len(self.nodos_zapata)} nodos)',
            hovertemplate='<b>Nodo Zapata/Pedestal</b><br>x: %{x:.2f} m<br>y: %{y:.2f} m<br>z: %{z:.2f} m<extra></extra>'
        ))

        # === 4. DIBUJAR NODOS DE INTERFAZ (ROJO) ===
        print("  Dibujando nodos de interfaz...")
        x_interfaz = [self.nodos_coords[n][0] for n in self.nodos_interfaz]
        y_interfaz = [self.nodos_coords[n][1] for n in self.nodos_interfaz]
        z_interfaz = [self.nodos_coords[n][2] for n in self.nodos_interfaz]

        fig.add_trace(go.Scatter3d(
            x=x_interfaz,
            y=y_interfaz,
            z=z_interfaz,
            mode='markers',
            marker=dict(
                size=7,
                color='red',
                symbol='diamond',
                line=dict(color='darkred', width=1)
            ),
            name=f'Interfaz Suelo-Zapata ({len(self.nodos_interfaz)} nodos)',
            hovertemplate='<b>Nodo de Interfaz</b><br>x: %{x:.2f} m<br>y: %{y:.2f} m<br>z: %{z:.2f} m<extra></extra>'
        ))

        # === CONFIGURAR LAYOUT ===
        fig.update_layout(
            title={
                'text': 'Visualización de Malla 3D - Modelo de Zapata<br>' +
                       '<sub>🟤 Suelo  |  ⚫ Zapata/Pedestal  |  🔴 Interfaz  |  ▬ Aristas</sub>',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18}
            },
            scene=dict(
                xaxis=dict(
                    title='X (m)',
                    backgroundcolor="rgb(245, 245, 245)",
                    gridcolor="white",
                    showbackground=True,
                    zeroline=True
                ),
                yaxis=dict(
                    title='Y (m)',
                    backgroundcolor="rgb(245, 245, 245)",
                    gridcolor="white",
                    showbackground=True,
                    zeroline=True
                ),
                zaxis=dict(
                    title='Z (m)',
                    backgroundcolor="rgb(245, 245, 245)",
                    gridcolor="white",
                    showbackground=True,
                    zeroline=True
                ),
                aspectmode='data',
                camera=dict(
                    eye=dict(x=1.8, y=1.8, z=1.3)
                ),
            ),
            width=1400,
            height=1000,
            showlegend=True,
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(255, 255, 255, 0.9)',
                bordercolor='black',
                borderwidth=2,
                font=dict(size=11)
            ),
            hovermode='closest',
            paper_bgcolor='white',
            plot_bgcolor='white'
        )

        return fig

    def guardar_html(self, fig, filename='malla_3d_mejorada.html'):
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
        print("# VISUALIZADOR MEJORADO DE MALLA 3D")
        print("#"*60)

        try:
            self.construir_modelo()
            fig = self.crear_visualizacion_mejorada()

            if guardar:
                self.guardar_html(fig)

            if mostrar:
                print("\n  Abriendo visualización en navegador...")
                self.mostrar(fig)

            print("\n" + "="*60)
            print("VISUALIZACIÓN COMPLETADA")
            print("="*60)
            print("\nControles:")
            print("  • Click izquierdo + arrastrar: Rotar 360°")
            print("  • Scroll: Zoom in/out")
            print("  • Click derecho + arrastrar: Desplazar (pan)")
            print("  • Click en leyenda: Mostrar/ocultar componentes")
            print("  • Hover sobre nodos: Ver coordenadas")
            print("\nColores:")
            print("  🟤 Café: Nodos del suelo")
            print("  ⚫ Gris: Nodos de zapata y pedestal")
            print("  🔴 Rojo: Nodos de interfaz (compartidos)")
            print("  ▬ Gris claro: Aristas de elementos")

            return True

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Visualizador mejorado de malla 3D con puntos y líneas'
    )
    parser.add_argument('--config', type=str, default='config_zapata.json',
                       help='Archivo de configuración')
    parser.add_argument('--no-show', action='store_true',
                       help='No abrir en navegador automáticamente')
    parser.add_argument('--output', type=str, default='malla_3d_mejorada.html',
                       help='Archivo de salida HTML')

    args = parser.parse_args()

    visualizador = VisualizadorMallaMejorado(config_file=args.config)
    visualizador.ejecutar(guardar=True, mostrar=not args.no_show)


if __name__ == '__main__':
    main()
