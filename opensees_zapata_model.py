#!/usr/bin/env python3
"""
Modelo de Zapata con Suelo Estratificado en OpenSees
====================================================

Este script crea un modelo 3D de una zapata apoyada en suelo estratificado,
incluyendo pedestal y material de lleno sobre la zapata.

Autor: Claude AI
Fecha: 2025
"""

import openseespy.opensees as ops
import numpy as np
import json
import os
import sys
import argparse
from datetime import datetime


class ModeloZapata:
    """Clase para crear y analizar el modelo de zapata en OpenSees"""

    def __init__(self, config_file='config_zapata.json'):
        """
        Inicializa el modelo con configuración desde archivo JSON

        Args:
            config_file (str): Ruta al archivo de configuración JSON
        """
        self.config_file = config_file
        self.cargar_configuracion()
        self.node_counter = 1
        self.elem_counter = 1
        self.nodos = {}
        self.elementos = {}

    def cargar_configuracion(self):
        """Carga la configuración desde el archivo JSON"""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            print(f"✓ Configuración cargada desde {self.config_file}")
        except FileNotFoundError:
            print(f"✗ Error: No se encontró el archivo {self.config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"✗ Error al leer JSON: {e}")
            sys.exit(1)

    def inicializar_modelo(self):
        """Inicializa el modelo de OpenSees"""
        print("\n" + "="*60)
        print("INICIALIZANDO MODELO OPENSEES")
        print("="*60)

        # Limpiar cualquier modelo anterior
        ops.wipe()

        # Modelo 3D con 3 grados de libertad por nodo
        ops.model('basic', '-ndm', 3, '-ndf', 3)

        print("✓ Modelo 3D inicializado (3 NDM, 3 NDF)")

    def definir_materiales(self):
        """Define los materiales del modelo"""
        print("\n" + "-"*60)
        print("DEFINIENDO MATERIALES")
        print("-"*60)

        # Material para concreto de la zapata
        conc_zapata = self.config['materiales']['concreto_zapata']
        ops.nDMaterial('ElasticIsotropic', 1, conc_zapata['E'], conc_zapata['nu'])
        print(f"✓ Material 1: Concreto zapata (E={conc_zapata['E']:.2e} Pa)")

        # Material para concreto del pedestal
        conc_pedestal = self.config['materiales']['concreto_pedestal']
        ops.nDMaterial('ElasticIsotropic', 2, conc_pedestal['E'], conc_pedestal['nu'])
        print(f"✓ Material 2: Concreto pedestal (E={conc_pedestal['E']:.2e} Pa)")

        # Material para lleno
        lleno = self.config['materiales']['lleno']
        ops.nDMaterial('ElasticIsotropic', 3, lleno['E'], lleno['nu'])
        print(f"✓ Material 3: Lleno (E={lleno['E']:.2e} Pa)")

        # Materiales para capas de suelo
        mat_id = 10  # Empezamos en 10 para materiales de suelo
        for capa in self.config['suelo_estratificado']['capas']:
            ops.nDMaterial('ElasticIsotropic', mat_id, capa['E'], capa['nu'])
            print(f"✓ Material {mat_id}: {capa['nombre']} (E={capa['E']:.2e} Pa)")
            capa['mat_id'] = mat_id
            mat_id += 1

    def crear_malla_zapata(self):
        """Crea la malla de elementos para la zapata"""
        print("\n" + "-"*60)
        print("CREANDO MALLA DE ZAPATA")
        print("-"*60)

        geom = self.config['geometria']['zapata']
        prof_desp = self.config['geometria']['profundidad_desplante']
        mallado = self.config['mallado']

        Lx = geom['ancho_x']
        Ly = geom['ancho_y']
        Lz = geom['espesor']

        nx = mallado['elementos_zapata_x']
        ny = mallado['elementos_zapata_y']
        nz = mallado['elementos_zapata_z']

        # La zapata está a profundidad -prof_desp desde la superficie (z=0)
        z_base_zapata = -prof_desp
        z_top_zapata = z_base_zapata + Lz

        # Crear nodos de la zapata
        self.nodos['zapata'] = []

        for k in range(nz + 1):
            for j in range(ny + 1):
                for i in range(nx + 1):
                    x = -Lx/2 + i * Lx/nx
                    y = -Ly/2 + j * Ly/ny
                    z = z_base_zapata + k * Lz/nz

                    ops.node(self.node_counter, x, y, z)
                    self.nodos['zapata'].append(self.node_counter)
                    self.node_counter += 1

        # Crear elementos sólidos para la zapata (brick elements)
        node_map = {}
        for k in range(nz + 1):
            for j in range(ny + 1):
                for i in range(nx + 1):
                    idx = k * (ny + 1) * (nx + 1) + j * (nx + 1) + i
                    node_map[(i, j, k)] = self.nodos['zapata'][idx]

        # Crear elementos brick (8 nodos)
        for k in range(nz):
            for j in range(ny):
                for i in range(nx):
                    n1 = node_map[(i, j, k)]
                    n2 = node_map[(i+1, j, k)]
                    n3 = node_map[(i+1, j+1, k)]
                    n4 = node_map[(i, j+1, k)]
                    n5 = node_map[(i, j, k+1)]
                    n6 = node_map[(i+1, j, k+1)]
                    n7 = node_map[(i+1, j+1, k+1)]
                    n8 = node_map[(i, j+1, k+1)]

                    ops.element('stdBrick', self.elem_counter,
                               n1, n2, n3, n4, n5, n6, n7, n8, 1)
                    self.elem_counter += 1

        print(f"✓ Zapata: {len(self.nodos['zapata'])} nodos, {nx*ny*nz} elementos")
        print(f"  Ubicación: z = {z_base_zapata:.2f} m a {z_top_zapata:.2f} m")

        return z_top_zapata, node_map, nx, ny

    def crear_malla_pedestal(self, z_base, node_map_zapata, nx_zapata, ny_zapata):
        """Crea la malla de elementos para el pedestal"""
        print("\n" + "-"*60)
        print("CREANDO MALLA DE PEDESTAL")
        print("-"*60)

        ped = self.config['geometria']['pedestal']
        zap = self.config['geometria']['zapata']

        # El pedestal sale de la parte superior de la zapata
        h_ped = ped['altura']
        L_ped_x = ped['ancho_x']
        L_ped_y = ped['ancho_y']

        # Número de elementos en el pedestal
        n_elem_ped = 2

        # Encontrar nodos en el centro superior de la zapata
        # para conectar el pedestal
        nx_ped = 2
        ny_ped = 2
        nz_ped = n_elem_ped

        self.nodos['pedestal'] = []

        # Crear nodos del pedestal
        for k in range(nz_ped + 1):
            for j in range(ny_ped + 1):
                for i in range(nx_ped + 1):
                    x = -L_ped_x/2 + i * L_ped_x/nx_ped
                    y = -L_ped_y/2 + j * L_ped_y/ny_ped
                    z = z_base + k * h_ped/nz_ped

                    ops.node(self.node_counter, x, y, z)
                    self.nodos['pedestal'].append(self.node_counter)
                    self.node_counter += 1

        # Crear elementos del pedestal
        node_map_ped = {}
        for k in range(nz_ped + 1):
            for j in range(ny_ped + 1):
                for i in range(nx_ped + 1):
                    idx = k * (ny_ped + 1) * (nx_ped + 1) + j * (nx_ped + 1) + i
                    node_map_ped[(i, j, k)] = self.nodos['pedestal'][idx]

        for k in range(nz_ped):
            for j in range(ny_ped):
                for i in range(nx_ped):
                    n1 = node_map_ped[(i, j, k)]
                    n2 = node_map_ped[(i+1, j, k)]
                    n3 = node_map_ped[(i+1, j+1, k)]
                    n4 = node_map_ped[(i, j+1, k)]
                    n5 = node_map_ped[(i, j, k+1)]
                    n6 = node_map_ped[(i+1, j, k+1)]
                    n7 = node_map_ped[(i+1, j+1, k+1)]
                    n8 = node_map_ped[(i, j+1, k+1)]

                    ops.element('stdBrick', self.elem_counter,
                               n1, n2, n3, n4, n5, n6, n7, n8, 2)
                    self.elem_counter += 1

        z_top_ped = z_base + h_ped
        print(f"✓ Pedestal: {len(self.nodos['pedestal'])} nodos")
        print(f"  Altura: {h_ped} m (sobresale sobre la zapata)")
        print(f"  Ubicación: z = {z_base:.2f} m a {z_top_ped:.2f} m")

        # Guardar el nodo superior central para aplicar cargas
        self.nodo_carga = node_map_ped[(1, 1, nz_ped)]

        return z_top_ped

    def crear_malla_suelo(self):
        """Crea la malla de elementos para las capas de suelo estratificado"""
        print("\n" + "-"*60)
        print("CREANDO MALLA DE SUELO ESTRATIFICADO")
        print("-"*60)

        prof_desp = self.config['geometria']['profundidad_desplante']
        zap_geom = self.config['geometria']['zapata']
        mallado = self.config['mallado']

        # El suelo comienza en la base de la zapata
        z_current = -prof_desp

        # Dimensiones del volumen de suelo (más grande que la zapata)
        L_suelo_x = zap_geom['ancho_x'] * 3
        L_suelo_y = zap_geom['ancho_y'] * 3

        nx = mallado['elementos_suelo_x']
        ny = mallado['elementos_suelo_y']

        self.nodos['suelo'] = []

        # Crear cada capa de suelo
        for idx, capa in enumerate(self.config['suelo_estratificado']['capas']):
            espesor = capa['espesor']
            nz = mallado['elementos_por_capa']

            print(f"\n  Capa {idx+1}: {capa['nombre']}")
            print(f"    Espesor: {espesor} m")

            # Crear nodos para esta capa
            nodos_capa = []
            for k in range(nz + 1):
                for j in range(ny + 1):
                    for i in range(nx + 1):
                        x = -L_suelo_x/2 + i * L_suelo_x/nx
                        y = -L_suelo_y/2 + j * L_suelo_y/ny
                        z = z_current - k * espesor/nz

                        ops.node(self.node_counter, x, y, z)
                        nodos_capa.append(self.node_counter)
                        self.nodos['suelo'].append(self.node_counter)
                        self.node_counter += 1

            # Crear elementos para esta capa
            node_map_capa = {}
            for k in range(nz + 1):
                for j in range(ny + 1):
                    for i in range(nx + 1):
                        idx_node = k * (ny + 1) * (nx + 1) + j * (nx + 1) + i
                        node_map_capa[(i, j, k)] = nodos_capa[idx_node]

            mat_id = capa['mat_id']
            for k in range(nz):
                for j in range(ny):
                    for i in range(nx):
                        n1 = node_map_capa[(i, j, k)]
                        n2 = node_map_capa[(i+1, j, k)]
                        n3 = node_map_capa[(i+1, j+1, k)]
                        n4 = node_map_capa[(i, j+1, k)]
                        n5 = node_map_capa[(i, j, k+1)]
                        n6 = node_map_capa[(i+1, j, k+1)]
                        n7 = node_map_capa[(i+1, j+1, k+1)]
                        n8 = node_map_capa[(i, j+1, k+1)]

                        ops.element('stdBrick', self.elem_counter,
                                   n1, n2, n3, n4, n5, n6, n7, n8, mat_id)
                        self.elem_counter += 1

            z_current -= espesor
            print(f"    {len(nodos_capa)} nodos, {nx*ny*nz} elementos")

        print(f"\n✓ Suelo total: {len(self.nodos['suelo'])} nodos")

    def crear_malla_lleno(self):
        """Crea la malla para el material de lleno sobre la zapata"""
        print("\n" + "-"*60)
        print("CREANDO MALLA DE LLENO")
        print("-"*60)

        prof_desp = self.config['geometria']['profundidad_desplante']
        zap_geom = self.config['geometria']['zapata']

        # El lleno va desde la parte superior de la zapata hasta la superficie
        z_base_lleno = -prof_desp + zap_geom['espesor']
        z_top_lleno = 0.0  # Superficie

        espesor_lleno = z_top_lleno - z_base_lleno

        if espesor_lleno <= 0:
            print("✓ No se requiere lleno (zapata en superficie)")
            return

        # Usar dimensiones similares a la zapata
        Lx = zap_geom['ancho_x'] * 2
        Ly = zap_geom['ancho_y'] * 2

        nx = 6
        ny = 6
        nz = max(2, int(espesor_lleno / 0.3))  # Elemento cada 30 cm aprox

        self.nodos['lleno'] = []

        # Crear nodos del lleno
        for k in range(nz + 1):
            for j in range(ny + 1):
                for i in range(nx + 1):
                    x = -Lx/2 + i * Lx/nx
                    y = -Ly/2 + j * Ly/ny
                    z = z_base_lleno + k * espesor_lleno/nz

                    ops.node(self.node_counter, x, y, z)
                    self.nodos['lleno'].append(self.node_counter)
                    self.node_counter += 1

        # Crear elementos del lleno
        node_map_lleno = {}
        for k in range(nz + 1):
            for j in range(ny + 1):
                for i in range(nx + 1):
                    idx = k * (ny + 1) * (nx + 1) + j * (nx + 1) + i
                    node_map_lleno[(i, j, k)] = self.nodos['lleno'][idx]

        for k in range(nz):
            for j in range(ny):
                for i in range(nx):
                    n1 = node_map_lleno[(i, j, k)]
                    n2 = node_map_lleno[(i+1, j, k)]
                    n3 = node_map_lleno[(i+1, j+1, k)]
                    n4 = node_map_lleno[(i, j+1, k)]
                    n5 = node_map_lleno[(i, j, k+1)]
                    n6 = node_map_lleno[(i+1, j, k+1)]
                    n7 = node_map_lleno[(i+1, j+1, k+1)]
                    n8 = node_map_lleno[(i, j+1, k+1)]

                    ops.element('stdBrick', self.elem_counter,
                               n1, n2, n3, n4, n5, n6, n7, n8, 3)
                    self.elem_counter += 1

        print(f"✓ Lleno: {len(self.nodos['lleno'])} nodos, {nx*ny*nz} elementos")
        print(f"  Espesor: {espesor_lleno:.2f} m")
        print(f"  Ubicación: z = {z_base_lleno:.2f} m a {z_top_lleno:.2f} m")

    def aplicar_condiciones_frontera(self):
        """Aplica las condiciones de frontera (apoyos)"""
        print("\n" + "-"*60)
        print("APLICANDO CONDICIONES DE FRONTERA")
        print("-"*60)

        # Fijar la base del suelo (nodos en la capa más profunda)
        nodos_fijos = 0
        for node in self.nodos['suelo']:
            coord = ops.nodeCoord(node)
            z = coord[2]

            # Encontrar los nodos más bajos
            profundidad_total = sum([c['espesor'] for c in self.config['suelo_estratificado']['capas']])
            prof_desp = self.config['geometria']['profundidad_desplante']
            z_base = -prof_desp - profundidad_total

            if abs(z - z_base) < 0.01:  # Tolerancia
                ops.fix(node, 1, 1, 1)  # Fijar en x, y, z
                nodos_fijos += 1

        print(f"✓ {nodos_fijos} nodos fijos en la base del suelo")

    def aplicar_cargas(self):
        """Aplica las cargas sobre la estructura"""
        print("\n" + "-"*60)
        print("APLICANDO CARGAS")
        print("-"*60)

        cargas = self.config['cargas']

        # Crear patrón de cargas
        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)

        # Aplicar carga vertical en el nodo superior del pedestal
        ops.load(self.nodo_carga,
                cargas['carga_horizontal_x'],
                cargas['carga_horizontal_y'],
                cargas['carga_vertical'])

        print(f"✓ Cargas aplicadas en nodo {self.nodo_carga}:")
        print(f"  - Carga vertical: {cargas['carga_vertical']/1000:.1f} kN")
        print(f"  - Carga horizontal X: {cargas['carga_horizontal_x']/1000:.1f} kN")
        print(f"  - Carga horizontal Y: {cargas['carga_horizontal_y']/1000:.1f} kN")

        # Aplicar gravedad a todos los elementos
        g = self.config['analisis']['gravedad']

        # Gravedad en elementos de zapata
        densidad_zap = self.config['materiales']['concreto_zapata']['densidad']
        ops.eleLoad('-ele', *range(1, self.elem_counter), '-type', '-beamUniform', 0, 0, -densidad_zap*g)

        print(f"✓ Gravedad aplicada: {g} m/s²")

    def analizar(self):
        """Realiza el análisis estructural"""
        print("\n" + "="*60)
        print("EJECUTANDO ANÁLISIS")
        print("="*60)

        analisis = self.config['analisis']

        # Configurar análisis estático
        ops.system('BandGeneral')
        ops.numberer('RCM')
        ops.constraints('Plain')
        ops.integrator('LoadControl', 1.0/analisis['num_pasos'])
        ops.algorithm('Newton')
        ops.test('NormDispIncr', analisis['tolerancia'], analisis['max_iteraciones'])
        ops.analysis('Static')

        print(f"✓ Sistema de análisis configurado")
        print(f"  Tipo: {analisis['tipo']}")
        print(f"  Número de pasos: {analisis['num_pasos']}")

        # Ejecutar análisis
        print("\nEjecutando análisis...")
        try:
            ok = ops.analyze(analisis['num_pasos'])
            if ok == 0:
                print("✓ Análisis completado exitosamente")
            else:
                print(f"✗ Advertencia: El análisis retornó código {ok}")
        except Exception as e:
            print(f"✗ Error durante el análisis: {e}")
            return False

        return True

    def extraer_resultados(self):
        """Extrae y guarda los resultados del análisis"""
        print("\n" + "="*60)
        print("EXTRAYENDO RESULTADOS")
        print("="*60)

        config_salida = self.config['salida']
        carpeta = config_salida['carpeta']

        # Crear carpeta de resultados
        os.makedirs(carpeta, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Guardar desplazamientos
        if config_salida['guardar_desplazamientos']:
            archivo_desp = os.path.join(carpeta, f'desplazamientos_{timestamp}.txt')
            with open(archivo_desp, 'w') as f:
                f.write("# Nodo, X, Y, Z, Ux, Uy, Uz\n")
                for tipo in ['zapata', 'pedestal', 'suelo', 'lleno']:
                    if tipo in self.nodos:
                        for node in self.nodos[tipo]:
                            coord = ops.nodeCoord(node)
                            disp = ops.nodeDisp(node)
                            f.write(f"{node}, {coord[0]:.4f}, {coord[1]:.4f}, {coord[2]:.4f}, "
                                   f"{disp[0]:.6e}, {disp[1]:.6e}, {disp[2]:.6e}\n")

            print(f"✓ Desplazamientos guardados en: {archivo_desp}")

        # Desplazamiento del nodo de carga
        disp_carga = ops.nodeDisp(self.nodo_carga)
        print(f"\n✓ Desplazamiento en punto de carga (nodo {self.nodo_carga}):")
        print(f"  Ux = {disp_carga[0]*1000:.3f} mm")
        print(f"  Uy = {disp_carga[1]*1000:.3f} mm")
        print(f"  Uz = {disp_carga[2]*1000:.3f} mm")

        # Guardar reacciones
        if config_salida['guardar_reacciones']:
            archivo_reac = os.path.join(carpeta, f'reacciones_{timestamp}.txt')
            reacciones_totales = np.array([0.0, 0.0, 0.0])

            with open(archivo_reac, 'w') as f:
                f.write("# Nodo, X, Y, Z, Rx, Ry, Rz\n")
                for node in self.nodos['suelo']:
                    # Solo nodos con restricciones tienen reacciones
                    try:
                        coord = ops.nodeCoord(node)
                        reac = ops.nodeReaction(node)
                        if abs(reac[0]) > 1e-10 or abs(reac[1]) > 1e-10 or abs(reac[2]) > 1e-10:
                            f.write(f"{node}, {coord[0]:.4f}, {coord[1]:.4f}, {coord[2]:.4f}, "
                                   f"{reac[0]:.6e}, {reac[1]:.6e}, {reac[2]:.6e}\n")
                            reacciones_totales += np.array(reac)
                    except:
                        pass

            print(f"✓ Reacciones guardadas en: {archivo_reac}")
            print(f"\n✓ Reacciones totales en la base:")
            print(f"  Rx = {reacciones_totales[0]/1000:.2f} kN")
            print(f"  Ry = {reacciones_totales[1]/1000:.2f} kN")
            print(f"  Rz = {reacciones_totales[2]/1000:.2f} kN")

        # Guardar resumen
        archivo_resumen = os.path.join(carpeta, f'resumen_{timestamp}.txt')
        with open(archivo_resumen, 'w') as f:
            f.write("="*60 + "\n")
            f.write("RESUMEN DEL ANÁLISIS - MODELO DE ZAPATA\n")
            f.write("="*60 + "\n\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Archivo de configuración: {self.config_file}\n\n")

            f.write("GEOMETRÍA:\n")
            f.write(f"  Zapata: {self.config['geometria']['zapata']['ancho_x']} x "
                   f"{self.config['geometria']['zapata']['ancho_y']} x "
                   f"{self.config['geometria']['zapata']['espesor']} m\n")
            f.write(f"  Profundidad de desplante: {self.config['geometria']['profundidad_desplante']} m\n")
            f.write(f"  Pedestal: {self.config['geometria']['pedestal']['altura']} m altura\n\n")

            f.write("SUELO ESTRATIFICADO:\n")
            for i, capa in enumerate(self.config['suelo_estratificado']['capas']):
                f.write(f"  Capa {i+1} - {capa['nombre']}: {capa['espesor']} m, "
                       f"E={capa['E']:.2e} Pa\n")

            f.write(f"\nCARGAS:\n")
            f.write(f"  Vertical: {self.config['cargas']['carga_vertical']/1000:.1f} kN\n")
            f.write(f"  Horizontal X: {self.config['cargas']['carga_horizontal_x']/1000:.1f} kN\n")
            f.write(f"  Horizontal Y: {self.config['cargas']['carga_horizontal_y']/1000:.1f} kN\n")

            f.write(f"\nRESULTADOS:\n")
            f.write(f"  Desplazamiento vertical máximo: {disp_carga[2]*1000:.3f} mm\n")
            f.write(f"  Desplazamiento horizontal X: {disp_carga[0]*1000:.3f} mm\n")
            f.write(f"  Desplazamiento horizontal Y: {disp_carga[1]*1000:.3f} mm\n")

        print(f"✓ Resumen guardado en: {archivo_resumen}")

        return carpeta

    def ejecutar(self):
        """Ejecuta el modelo completo"""
        print("\n" + "#"*60)
        print("# MODELO DE ZAPATA CON SUELO ESTRATIFICADO - OpenSees")
        print("#"*60)
        print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            self.inicializar_modelo()
            self.definir_materiales()

            # Crear mallas
            z_top_zapata, node_map, nx, ny = self.crear_malla_zapata()
            z_top_pedestal = self.crear_malla_pedestal(z_top_zapata, node_map, nx, ny)
            self.crear_malla_suelo()
            self.crear_malla_lleno()

            # Aplicar condiciones y cargas
            self.aplicar_condiciones_frontera()
            self.aplicar_cargas()

            # Analizar
            exito = self.analizar()

            if exito:
                # Extraer resultados
                carpeta_resultados = self.extraer_resultados()

                print("\n" + "="*60)
                print("ANÁLISIS COMPLETADO EXITOSAMENTE")
                print("="*60)
                print(f"\nResultados guardados en: {carpeta_resultados}/")
                print(f"Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                return True
            else:
                print("\n" + "="*60)
                print("ANÁLISIS FALLÓ")
                print("="*60)
                return False

        except Exception as e:
            print(f"\n✗ Error durante la ejecución: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Modelo de zapata con suelo estratificado en OpenSees'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config_zapata.json',
        help='Archivo de configuración JSON (default: config_zapata.json)'
    )

    args = parser.parse_args()

    # Crear y ejecutar el modelo
    modelo = ModeloZapata(config_file=args.config)
    exito = modelo.ejecutar()

    if not exito:
        sys.exit(1)


if __name__ == '__main__':
    main()
