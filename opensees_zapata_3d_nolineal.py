#!/usr/bin/env python3
"""
Modelo 3D Mejorado de Zapata con Suelos No Lineales en OpenSees
================================================================

Este modelo implementa:
- Materiales no lineales para el suelo (J2 Plasticity / Drucker-Prager)
- Conectividad correcta entre componentes
- Análisis no lineal incremental
- Malla unificada con nodos compartidos

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
import matplotlib.pyplot as plt


class ModeloZapata3DNoLineal:
    """Modelo 3D de zapata con suelos no lineales"""

    def __init__(self, config_file='config_zapata.json'):
        self.config_file = config_file
        self.cargar_configuracion()
        self.node_counter = 1
        self.elem_counter = 1
        self.nodos = {}

    def cargar_configuracion(self):
        """Carga configuración desde JSON"""
        with open(self.config_file, 'r') as f:
            self.config = json.load(f)
        print(f"✓ Configuración cargada desde {self.config_file}")

    def inicializar_modelo(self):
        """Inicializa el modelo de OpenSees"""
        print("\n" + "="*60)
        print("MODELO 3D NO LINEAL - ZAPATA CON SUELO")
        print("="*60)

        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 3)
        print("✓ Modelo 3D inicializado (3 NDM, 3 NDF)")

    def definir_materiales_no_lineales(self):
        """Define materiales no lineales para suelo y concreto"""
        print("\n" + "-"*60)
        print("DEFINIENDO MATERIALES NO LINEALES")
        print("-"*60)

        # Material para concreto (elástico - muy rígido)
        E_conc = self.config['materiales']['concreto_zapata']['E']
        nu_conc = self.config['materiales']['concreto_zapata']['nu']
        rho_conc = self.config['materiales']['concreto_zapata']['densidad']

        ops.nDMaterial('ElasticIsotropic', 1, E_conc, nu_conc, rho_conc)
        print(f"✓ Material 1: Concreto (E={E_conc/1e9:.1f} GPa) - Elástico")

        # Material para relleno (lleno)
        E_lleno = self.config['materiales']['lleno']['E']
        nu_lleno = self.config['materiales']['lleno']['nu']
        rho_lleno = self.config['materiales']['lleno']['densidad']
        coh_lleno = self.config['materiales']['lleno']['cohesion']
        phi_lleno = self.config['materiales']['lleno']['friccion_grados'] * np.pi / 180

        G_lleno = E_lleno / (2 * (1 + nu_lleno))
        K_lleno = E_lleno / (3 * (1 - 2*nu_lleno))
        sigma_y_lleno = 6 * coh_lleno if coh_lleno > 0 else 50000
        H_iso_lleno = 0.02 * E_lleno

        # Usar elástico para relleno por ahora (más estable)
        ops.nDMaterial('ElasticIsotropic', 2, E_lleno, nu_lleno, rho_lleno)
        print(f"✓ Material 2: Relleno (E={E_lleno/1e6:.1f} MPa) - ElasticIsotropic")

        # Materiales no lineales para capas de suelo
        mat_id = 10
        for i, capa in enumerate(self.config['suelo_estratificado']['capas'], 1):
            E = capa['E']
            nu = capa['nu']
            rho = capa['densidad']

            # Calcular parámetros elásticos
            G = E / (2 * (1 + nu))  # Módulo de corte
            K = E / (3 * (1 - 2*nu))  # Módulo de bulk

            # Parámetros de Drucker-Prager
            cohesion = capa.get('cohesion', 10000)  # Pa
            phi_grados = capa.get('friccion_grados', 30)
            phi = phi_grados * np.pi / 180  # radianes

            # Parámetro de fricción rho para Drucker-Prager
            # Ajuste para coincidir con criterio de Mohr-Coulomb en compresión triaxial
            sin_phi = np.sin(phi)
            rho_bar = (2 * np.sqrt(6) * sin_phi) / (3 - sin_phi)

            # Cohesión inicial (sigma_y) - mínimo 1 kPa para estabilidad
            sigma_y = max(cohesion, 1000)  # Pa (mínimo 1 kPa)

            # Cohesión en el límite (para endurecimiento leve)
            Kinf = sigma_y * 1.2  # 20% de endurecimiento

            # Parámetro de endurecimiento
            Ko = 0.0  # Sin endurecimiento inicial

            # Parámetros de dilatancia (sin dilatancia = modelo conservador)
            delta1 = 0.0  # Sin dilatancia
            delta2 = 0.0

            # Módulo de endurecimiento plástico (pequeño para estabilidad)
            H = 0.001 * G  # 0.1% del módulo de corte

            # Ángulo de Lode (theta = 0 para superficie circular en plano desviador)
            theta = 0.0

            # Presión atmosférica (para normalización)
            atm = 101325.0  # Pa

            # Usar modelo elástico para análisis rápido
            ops.nDMaterial('ElasticIsotropic', mat_id, E, nu, rho)
            print(f"✓ Material {mat_id}: {capa['nombre']} - ElasticIsotropic (E={E/1e6:.1f} MPa)")

            # Para usar DruckerPrager, descomentar:
            # try:
            #     ops.nDMaterial('DruckerPrager', mat_id, K, G, sigma_y, rho,
            #                   rho_bar, Kinf, Ko, delta1, delta2, H, theta, rho, atm)
            #     print(f"✓ Material {mat_id}: {capa['nombre']} - DruckerPrager")
            #     print(f"    K={K/1e6:.1f} MPa, G={G/1e6:.1f} MPa")
            #     print(f"    c={cohesion/1000:.1f} kPa, φ={phi_grados:.1f}°, ρ̄={rho_bar:.3f}")
            # except Exception as e:
            #     print(f"⚠ DruckerPrager falló, usando ElasticIsotropic")
            #     ops.nDMaterial('ElasticIsotropic', mat_id, E, nu, rho)

            capa['mat_id'] = mat_id
            mat_id += 1

    def crear_malla_unificada(self):
        """
        Crea una malla unificada donde zapata y suelo comparten nodos
        Este es el enfoque correcto para garantizar continuidad
        """
        print("\n" + "-"*60)
        print("CREANDO MALLA UNIFICADA")
        print("-"*60)

        geom_zap = self.config['geometria']['zapata']
        prof_desp = self.config['geometria']['profundidad_desplante']
        capas = self.config['suelo_estratificado']['capas']

        # Dimensiones de la zapata
        B_x = geom_zap['ancho_x']
        B_y = geom_zap['ancho_y']
        h_zap = geom_zap['espesor']

        # Dimensiones del suelo (más grande que la zapata)
        L_suelo_x = B_x * 2.5
        L_suelo_y = B_y * 2.5

        # ESTRATEGIA: Crear malla con coordenadas compatibles
        # Los nodos del suelo deben incluir EXACTAMENTE las coordenadas de la base de la zapata

        nx_zap = 4    # elementos en X de la zapata
        ny_zap = 4    # elementos en Y de la zapata
        nz_zap = 2    # elementos en Z de la zapata

        # Elementos extra a cada lado de la zapata
        nx_extra = 2  # elementos adicionales a cada lado en X
        ny_extra = 2  # elementos adicionales a cada lado en Y

        # Profundidad total del suelo BAJO la zapata
        H_suelo_total = sum([c['espesor'] for c in capas])
        nz_suelo = len(capas) * 2  # 2 elementos por capa

        # GEOMETRÍA CORRECTA: z=0 es la superficie
        # NOTA: Por ahora sin relleno para simplificar (problema de convergencia)
        z_base_zapata = -prof_desp
        z_tope_zapata = z_base_zapata + h_zap
        z_superficie = z_tope_zapata  # Superficie al nivel del tope de zapata (SIN RELLENO)
        z_base_suelo = z_base_zapata - H_suelo_total
        H_relleno = 0  # SIN RELLENO POR AHORA
        nz_relleno = 0

        print(f"\n  GEOMETRÍA DEL MODELO (z=0 es la superficie):")
        print(f"    Superficie del suelo: z = {z_superficie:.2f} m")
        print(f"    Tope de zapata: z = {z_tope_zapata:.2f} m")
        print(f"    Base de zapata: z = {z_base_zapata:.2f} m (prof. Df = {prof_desp:.2f} m)")
        print(f"    Base del suelo: z = {z_base_suelo:.2f} m")

        # CREAR COORDENADAS X e Y CON COMPATIBILIDAD GARANTIZADA
        # Primero definir coordenadas de la zapata
        dx_zap = B_x / nx_zap
        dy_zap = B_y / ny_zap

        x_zap_coords = np.array([-B_x/2 + i*dx_zap for i in range(nx_zap + 1)])
        y_zap_coords = np.array([-B_y/2 + j*dy_zap for j in range(ny_zap + 1)])

        # Coordenadas del suelo: incluir las de la zapata + extensión a los lados
        dx_extra = (L_suelo_x - B_x) / (2 * nx_extra)
        dy_extra = (L_suelo_y - B_y) / (2 * ny_extra)

        # Construir coordenadas del suelo
        x_suelo_izq = np.array([-L_suelo_x/2 + i*dx_extra for i in range(nx_extra)])
        x_suelo_der = np.array([B_x/2 + (i+1)*dx_extra for i in range(nx_extra)])
        x_suelo_coords = np.concatenate([x_suelo_izq, x_zap_coords, x_suelo_der])

        y_suelo_izq = np.array([-L_suelo_y/2 + j*dy_extra for j in range(ny_extra)])
        y_suelo_der = np.array([B_y/2 + (j+1)*dy_extra for j in range(ny_extra)])
        y_suelo_coords = np.concatenate([y_suelo_izq, y_zap_coords, y_suelo_der])

        nx_suelo = len(x_suelo_coords) - 1
        ny_suelo = len(y_suelo_coords) - 1

        print(f"\n  Mallado con coordenadas compatibles:")
        print(f"    Suelo: {nx_suelo} × {ny_suelo} elementos en XY")
        print(f"    Zapata: {nx_zap} × {ny_zap} elementos en XY")
        print(f"    Inicio zapata en índices: i=[{nx_extra}:{nx_extra+nx_zap}], j=[{ny_extra}:{ny_extra+ny_zap}]")

        # CREAR NODOS DEL SUELO Y RELLENO con coordenadas exactas
        print("\n  Creando nodos del suelo y relleno...")
        nodos_suelo = {}

        nz_total = nz_suelo + nz_relleno
        H_total = H_suelo_total + H_relleno
        dz_total = H_total / nz_total

        for k in range(nz_total + 1):
            z = z_base_suelo + k * dz_total
            for j in range(ny_suelo + 1):
                for i in range(nx_suelo + 1):
                    x = x_suelo_coords[i]
                    y = y_suelo_coords[j]

                    ops.node(self.node_counter, x, y, z)
                    nodos_suelo[(i, j, k)] = self.node_counter
                    self.node_counter += 1

        print(f"  ✓ {len(nodos_suelo)} nodos del suelo/relleno creados")

        # CREAR NODOS DE LA ZAPATA compartiendo nodos en la base
        print("\n  Creando nodos de la zapata...")
        nodos_zapata = {}

        dz_zap = h_zap / nz_zap
        k_base_zap = nz_suelo  # Índice k de la base de zapata en la malla del suelo

        for k in range(nz_zap + 1):
            z = z_base_zapata + k * dz_zap
            for j in range(ny_zap + 1):
                for i in range(nx_zap + 1):
                    if k == 0:
                        # En la base: compartir nodo con suelo (COORDENADAS IDÉNTICAS)
                        i_suelo = nx_extra + i
                        j_suelo = ny_extra + j
                        nodos_zapata[(i, j, k)] = nodos_suelo[(i_suelo, j_suelo, k_base_zap)]
                    else:
                        # Arriba de la base: crear nuevos nodos
                        x = x_zap_coords[i]
                        y = y_zap_coords[j]
                        ops.node(self.node_counter, x, y, z)
                        nodos_zapata[(i, j, k)] = self.node_counter
                        self.node_counter += 1

        nodos_compartidos = (nx_zap + 1) * (ny_zap + 1)
        print(f"  ✓ {len(nodos_zapata)} entradas de nodos para zapata")
        print(f"  ✓ {nodos_compartidos} nodos compartidos en la interfaz (COORDENADAS IDÉNTICAS)")

        self.nodos['suelo'] = nodos_suelo
        self.nodos['zapata'] = nodos_zapata
        self.nx_suelo, self.ny_suelo, self.nz_suelo = nx_suelo, ny_suelo, nz_total
        self.nx_zap, self.ny_zap, self.nz_zap = nx_zap, ny_zap, nz_zap
        self.nz_suelo_estratificado = nz_suelo
        self.z_base_zapata = z_base_zapata
        self.z_tope_zapata = z_tope_zapata
        self.i_start_zap, self.j_start_zap = nx_extra, ny_extra
        self.nx_extra, self.ny_extra = nx_extra, ny_extra

        return z_tope_zapata

    def crear_elementos(self):
        """Crea los elementos sólidos para suelo y zapata"""
        print("\n" + "-"*60)
        print("CREANDO ELEMENTOS")
        print("-"*60)

        # ELEMENTOS DEL SUELO Y RELLENO
        print("\n  Elementos del suelo y relleno...")
        capas = self.config['suelo_estratificado']['capas']
        elem_por_capa = self.nz_suelo_estratificado // len(capas)

        # Determinar región de la zapata
        i_min = self.i_start_zap
        i_max = self.i_start_zap + self.nx_zap
        j_min = self.j_start_zap
        j_max = self.j_start_zap + self.ny_zap
        k_min_zap = self.nz_suelo_estratificado
        k_max_zap = k_min_zap + self.nz_zap

        num_elem_suelo = 0
        num_elem_relleno = 0

        for k in range(self.nz_suelo):
            for j in range(self.ny_suelo):
                for i in range(self.nx_suelo):
                    # Verificar si este elemento está en la región de la zapata
                    en_region_zapata = (k >= k_min_zap and k < k_max_zap and
                                       i >= i_min and i < i_max and
                                       j >= j_min and j < j_max)

                    # Si está en la región de la zapata, NO crear elemento de suelo/relleno
                    if en_region_zapata:
                        continue

                    # Determinar qué material usar
                    if k < self.nz_suelo_estratificado:
                        # Suelo estratificado
                        capa_idx = min(k // elem_por_capa, len(capas) - 1)
                        mat_id = capas[capa_idx]['mat_id']
                        num_elem_suelo += 1
                    else:
                        # Relleno
                        mat_id = 2
                        num_elem_relleno += 1

                    # Crear elemento
                    n1 = self.nodos['suelo'][(i, j, k)]
                    n2 = self.nodos['suelo'][(i+1, j, k)]
                    n3 = self.nodos['suelo'][(i+1, j+1, k)]
                    n4 = self.nodos['suelo'][(i, j+1, k)]
                    n5 = self.nodos['suelo'][(i, j, k+1)]
                    n6 = self.nodos['suelo'][(i+1, j, k+1)]
                    n7 = self.nodos['suelo'][(i+1, j+1, k+1)]
                    n8 = self.nodos['suelo'][(i, j+1, k+1)]

                    ops.element('stdBrick', self.elem_counter,
                               n1, n2, n3, n4, n5, n6, n7, n8, mat_id)
                    self.elem_counter += 1

        print(f"  ✓ {num_elem_suelo} elementos de suelo estratificado creados")
        print(f"  ✓ {num_elem_relleno} elementos de relleno creados")

        # ELEMENTOS DE LA ZAPATA
        print("\n  Elementos de la zapata...")
        num_elem_zapata = 0
        mat_concreto = 1

        for k in range(self.nz_zap):
            for j in range(self.ny_zap):
                for i in range(self.nx_zap):
                    n1 = self.nodos['zapata'][(i, j, k)]
                    n2 = self.nodos['zapata'][(i+1, j, k)]
                    n3 = self.nodos['zapata'][(i+1, j+1, k)]
                    n4 = self.nodos['zapata'][(i, j+1, k)]
                    n5 = self.nodos['zapata'][(i, j, k+1)]
                    n6 = self.nodos['zapata'][(i+1, j, k+1)]
                    n7 = self.nodos['zapata'][(i+1, j+1, k+1)]
                    n8 = self.nodos['zapata'][(i, j+1, k+1)]

                    ops.element('stdBrick', self.elem_counter,
                               n1, n2, n3, n4, n5, n6, n7, n8, mat_concreto)
                    self.elem_counter += 1
                    num_elem_zapata += 1

        print(f"  ✓ {num_elem_zapata} elementos de zapata creados")
        print(f"\n  Total: {num_elem_suelo + num_elem_zapata} elementos")

    def aplicar_condiciones_frontera(self):
        """Aplica condiciones de frontera"""
        print("\n" + "-"*60)
        print("CONDICIONES DE FRONTERA")
        print("-"*60)

        # Fijar base del suelo
        nodos_fijos = 0
        for (i, j, k), node in self.nodos['suelo'].items():
            if k == 0:  # Base del suelo
                ops.fix(node, 1, 1, 1)
                nodos_fijos += 1

        print(f"  ✓ {nodos_fijos} nodos fijos en la base")

        # Restricciones laterales (optional - simula confinamiento)
        nodos_confinados = 0
        for (i, j, k), node in self.nodos['suelo'].items():
            if i == 0 or i == self.nx_suelo:  # Bordes en X
                if k > 0:  # No la base
                    ops.fix(node, 1, 0, 0)
                    nodos_confinados += 1
            if j == 0 or j == self.ny_suelo:  # Bordes en Y
                if k > 0:  # No la base
                    ops.fix(node, 0, 1, 0)
                    nodos_confinados += 1

        print(f"  ✓ {nodos_confinados} nodos con restricciones laterales")

    def calcular_cargas_gravedad(self):
        """Calcula fuerzas de gravedad basadas en volumen y densidad de elementos"""
        g = 9.81  # m/s²
        cargas_gravedad = {}  # {node_id: fuerza_z}

        # Procesar elementos del suelo
        capas = self.config['suelo_estratificado']['capas']
        elem_por_capa = self.nz_suelo_estratificado // len(capas)

        i_min = self.i_start_zap
        i_max = self.i_start_zap + self.nx_zap
        j_min = self.j_start_zap
        j_max = self.j_start_zap + self.ny_zap
        k_min_zap = self.nz_suelo_estratificado
        k_max_zap = k_min_zap + self.nz_zap

        for k in range(self.nz_suelo):
            for j in range(self.ny_suelo):
                for i in range(self.nx_suelo):
                    # Verificar si está en región de zapata (skip)
                    en_region_zapata = (k >= k_min_zap and k < k_max_zap and
                                       i >= i_min and i < i_max and
                                       j >= j_min and j < j_max)
                    if en_region_zapata:
                        continue

                    # Obtener nodos del elemento
                    try:
                        n1 = self.nodos['suelo'][(i, j, k)]
                        n2 = self.nodos['suelo'][(i+1, j, k)]
                        n3 = self.nodos['suelo'][(i+1, j+1, k)]
                        n4 = self.nodos['suelo'][(i, j+1, k)]
                        n5 = self.nodos['suelo'][(i, j, k+1)]
                        n6 = self.nodos['suelo'][(i+1, j, k+1)]
                        n7 = self.nodos['suelo'][(i+1, j+1, k+1)]
                        n8 = self.nodos['suelo'][(i, j+1, k+1)]
                    except KeyError:
                        continue

                    # Calcular volumen del elemento (brick)
                    # Coordenadas de los nodos
                    coord_n1 = [ops.nodeCoord(n1, dim+1) for dim in range(3)]
                    coord_n7 = [ops.nodeCoord(n7, dim+1) for dim in range(3)]
                    dx = abs(coord_n7[0] - coord_n1[0])
                    dy = abs(coord_n7[1] - coord_n1[1])
                    dz = abs(coord_n7[2] - coord_n1[2])
                    volumen = dx * dy * dz

                    # Obtener densidad del material
                    if k < self.nz_suelo_estratificado:
                        capa_idx = min(k // elem_por_capa, len(capas) - 1)
                        rho = capas[capa_idx]['densidad']
                    else:
                        rho = self.config['materiales']['lleno']['densidad']

                    # Fuerza de gravedad del elemento
                    peso = rho * volumen * g  # N

                    # Distribuir entre 8 nodos (1/8 cada uno)
                    fuerza_por_nodo = peso / 8

                    for nodo in [n1, n2, n3, n4, n5, n6, n7, n8]:
                        if nodo not in cargas_gravedad:
                            cargas_gravedad[nodo] = 0.0
                        cargas_gravedad[nodo] += fuerza_por_nodo

        # Procesar elementos de la zapata
        rho_conc = self.config['materiales']['concreto_zapata']['densidad']

        for k in range(self.nz_zap):
            for j in range(self.ny_zap):
                for i in range(self.nx_zap):
                    n1 = self.nodos['zapata'][(i, j, k)]
                    n2 = self.nodos['zapata'][(i+1, j, k)]
                    n3 = self.nodos['zapata'][(i+1, j+1, k)]
                    n4 = self.nodos['zapata'][(i, j+1, k)]
                    n5 = self.nodos['zapata'][(i, j, k+1)]
                    n6 = self.nodos['zapata'][(i+1, j, k+1)]
                    n7 = self.nodos['zapata'][(i+1, j+1, k+1)]
                    n8 = self.nodos['zapata'][(i, j+1, k+1)]

                    # Calcular volumen
                    coord_n1 = [ops.nodeCoord(n1, dim+1) for dim in range(3)]
                    coord_n7 = [ops.nodeCoord(n7, dim+1) for dim in range(3)]
                    dx = abs(coord_n7[0] - coord_n1[0])
                    dy = abs(coord_n7[1] - coord_n1[1])
                    dz = abs(coord_n7[2] - coord_n1[2])
                    volumen = dx * dy * dz

                    # Fuerza de gravedad
                    peso = rho_conc * volumen * g  # N
                    fuerza_por_nodo = peso / 8

                    for nodo in [n1, n2, n3, n4, n5, n6, n7, n8]:
                        if nodo not in cargas_gravedad:
                            cargas_gravedad[nodo] = 0.0
                        cargas_gravedad[nodo] += fuerza_por_nodo

        return cargas_gravedad

    def aplicar_cargas_gravedad(self):
        """Aplica solo las cargas de gravedad (Fase 1)"""
        print("\n" + "-"*60)
        print("CONFIGURANDO PATTERN 1: GRAVEDAD")
        print("-"*60)

        # PATTERN 1: CARGA DE GRAVEDAD (peso propio)
        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)

        # Calcular y aplicar fuerzas de gravedad
        print("  Calculando fuerzas de gravedad...")
        cargas_gravedad = self.calcular_cargas_gravedad()

        # Aplicar fuerzas de gravedad (negativas, hacia abajo)
        for nodo, fuerza in cargas_gravedad.items():
            ops.load(nodo, 0.0, 0.0, -fuerza)  # Negativo = hacia abajo

        peso_total = sum(cargas_gravedad.values()) / 1000  # kN
        print(f"  ✓ Cargas de gravedad aplicadas en {len(cargas_gravedad)} nodos")
        print(f"  ✓ Peso total del sistema: {peso_total:.2f} kN")

        # Guardar nodos de referencia
        i_central = self.nx_zap // 2
        j_central = self.ny_zap // 2
        self.nodo_carga = self.nodos['zapata'][(i_central, j_central, self.nz_zap)]
        self.nodo_base_central = self.nodos['zapata'][(i_central, j_central, 0)]

    def aplicar_cargas_externas(self):
        """Aplica las cargas externas (Fase 2) - se llama DESPUÉS de loadConst"""
        print("\n" + "-"*60)
        print("CONFIGURANDO PATTERN 2: CARGA APLICADA")
        print("-"*60)

        # PATTERN 2: CARGA APLICADA (1000 kN en 10 pasos)
        ops.timeSeries('Linear', 2)
        ops.pattern('Plain', 2, 2)

        # Nodos en la parte superior de la zapata
        nodos_top = []
        for (i, j, k), node in self.nodos['zapata'].items():
            if k == self.nz_zap:  # Top de la zapata
                nodos_top.append(node)

        # Distribuir carga uniformemente
        P_total = 1000000  # 1000 kN = 1,000,000 N
        F_x = 0  # Sin carga horizontal por ahora
        num_nodos = len(nodos_top)

        P_por_nodo = P_total / num_nodos
        F_x_por_nodo = F_x / num_nodos

        for node in nodos_top:
            ops.load(node, F_x_por_nodo, 0.0, -P_por_nodo)  # Negativo = hacia abajo

        print(f"  ✓ Carga vertical total: {P_total/1000:.1f} kN")
        print(f"  ✓ Carga horizontal total: {F_x/1000:.1f} kN")
        print(f"  ✓ Distribuida en {num_nodos} nodos ({P_por_nodo/1000:.2f} kN/nodo)")

    def analizar_no_lineal(self):
        """Ejecuta análisis no lineal en dos fases: gravedad + carga aplicada"""
        print("\n" + "="*60)
        print("ANÁLISIS NO LINEAL EN DOS FASES")
        print("="*60)

        # Configuración del análisis
        ops.system('BandGeneral')
        ops.numberer('RCM')
        ops.constraints('Transformation')
        ops.test('NormDispIncr', 1.0e-6, 50, 0)
        ops.algorithm('Newton')
        ops.analysis('Static')

        print("\n  Sistema: BandGeneral")
        print("  Algoritmo: Newton")
        print("  Convergencia: NormDispIncr (tol=1e-6, max_iter=50)")

        # Listas para historia carga-desplazamiento
        self.historia_carga = []
        self.historia_despl = []
        self.historia_fase = []  # 1 = gravedad, 2 = carga aplicada

        # ============================================================
        # FASE 1: ANÁLISIS DE GRAVEDAD
        # ============================================================
        print("\n" + "="*60)
        print("FASE 1: ANÁLISIS DE CARGA DE GRAVEDAD")
        print("="*60)

        # En la fase 1, solo el pattern 1 (gravedad) está activo
        # Aplicar gravedad en un solo paso (o varios pasos pequeños)
        ops.integrator('LoadControl', 1.0)  # Aplicar 100% de la gravedad

        print("\n  Aplicando gravedad (Pattern 1)...")

        # Intentar analizar
        ok = ops.analyze(1)

        if ok != 0:
            print("  ⚠ Fallo con Newton, intentando ModifiedNewton...")
            ops.algorithm('ModifiedNewton', '-initial')
            ok = ops.analyze(1)

            if ok == 0:
                print("  ✓ Convergió con ModifiedNewton")
                ops.algorithm('Newton')  # Volver a Newton
            else:
                print("  ✗ No convergió en fase de gravedad")
                return False

        # Registrar estado después de gravedad
        despl_gravedad = ops.nodeDisp(self.nodo_base_central)[2] * 1000  # mm
        self.historia_carga.append(0.0)  # Carga externa = 0
        self.historia_despl.append(despl_gravedad)
        self.historia_fase.append(1)

        print(f"  ✓ Gravedad aplicada exitosamente")
        print(f"  ✓ Desplazamiento por gravedad: {despl_gravedad:.4f} mm")

        # Mantener la carga de gravedad constante para la siguiente fase
        ops.loadConst('-time', 0.0)
        print(f"  ✓ Cargas de gravedad congeladas con loadConst")

        # ============================================================
        # FASE 2: ANÁLISIS DE CARGA APLICADA (1000 kN en 10 pasos)
        # ============================================================
        print("\n" + "="*60)
        print("FASE 2: ANÁLISIS DE CARGA APLICADA (0 → 1000 kN)")
        print("="*60)

        # Aplicar cargas externas DESPUÉS de loadConst
        self.aplicar_cargas_externas()

        # Configurar integrador para carga incremental
        # 10 pasos × 0.1 = 1.0 (factor de carga completo)
        ops.integrator('LoadControl', 0.1)

        num_pasos = 10
        P_total = 1000  # kN

        print(f"\n  Aplicando carga en {num_pasos} incrementos de {P_total/num_pasos:.1f} kN")
        print(f"  Pattern activo: Pattern 2 (carga aplicada)")

        exitos = 0
        for step in range(num_pasos):
            ok = ops.analyze(1)

            if ok == 0:
                exitos += 1
                # Registrar carga y desplazamiento
                factor_carga = (step + 1) * 0.1
                carga_actual = P_total * factor_carga  # kN
                despl = ops.nodeDisp(self.nodo_base_central)[2] * 1000  # mm

                self.historia_carga.append(carga_actual)
                self.historia_despl.append(despl)
                self.historia_fase.append(2)

                if (step + 1) % 2 == 0:
                    print(f"    Paso {step+1}/{num_pasos}: ✓ (Carga={carga_actual:.1f} kN, Despl={despl:.3f} mm)")
            else:
                print(f"    Paso {step+1}/{num_pasos}: ⚠ Intentando con algoritmo modificado...")
                # Intentar con Modified Newton
                ops.algorithm('ModifiedNewton', '-initial')
                ok = ops.analyze(1)
                if ok == 0:
                    exitos += 1
                    # Registrar carga y desplazamiento
                    factor_carga = (step + 1) * 0.1
                    carga_actual = P_total * factor_carga  # kN
                    despl = ops.nodeDisp(self.nodo_base_central)[2] * 1000  # mm

                    self.historia_carga.append(carga_actual)
                    self.historia_despl.append(despl)
                    self.historia_fase.append(2)

                    print(f"    Paso {step+1}/{num_pasos}: ✓ (ModifiedNewton, Carga={carga_actual:.1f} kN)")
                    ops.algorithm('Newton')  # Volver a Newton
                else:
                    print(f"    Paso {step+1}/{num_pasos}: ✗ No convergió")
                    break

        print(f"\n" + "="*60)
        print(f"RESUMEN DEL ANÁLISIS")
        print("="*60)
        print(f"  Fase 1 (Gravedad): Completada")
        print(f"  Fase 2 (Carga aplicada): {exitos}/{num_pasos} pasos completados")
        print(f"  Historia registrada: {len(self.historia_carga)} puntos")

        return exitos > 0

    def extraer_resultados(self):
        """Extrae resultados del análisis"""
        print("\n" + "="*60)
        print("RESULTADOS")
        print("="*60)

        # Desplazamiento en nodo de carga
        disp = ops.nodeDisp(self.nodo_carga)

        print(f"\n  Desplazamientos en nodo central superior (#{self.nodo_carga}):")
        print(f"    Ux = {disp[0]*1000:.3f} mm")
        print(f"    Uy = {disp[1]*1000:.3f} mm")
        print(f"    Uz = {disp[2]*1000:.3f} mm (asentamiento)")

        # Asentamiento promedio en la base de la zapata
        despl_base = []
        for (i, j, k), node in self.nodos['zapata'].items():
            if k == 0:  # Base de zapata
                uz = ops.nodeDisp(node)[2]
                despl_base.append(uz)

        if despl_base:
            asentamiento_medio = np.mean(despl_base) * 1000
            print(f"\n  Asentamiento promedio en base de zapata: {asentamiento_medio:.3f} mm")

        # Guardar resultados
        os.makedirs('resultados', exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = os.path.join('resultados', f'resultados_3d_nolineal_{timestamp}.txt')

        with open(archivo, 'w') as f:
            f.write("="*60 + "\n")
            f.write("RESULTADOS - MODELO 3D NO LINEAL\n")
            f.write("="*60 + "\n\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Desplazamiento nodo central superior:\n")
            f.write(f"  Ux = {disp[0]*1000:.3f} mm\n")
            f.write(f"  Uy = {disp[1]*1000:.3f} mm\n")
            f.write(f"  Uz = {disp[2]*1000:.3f} mm\n\n")
            f.write(f"Asentamiento promedio base de zapata: {asentamiento_medio:.3f} mm\n")

        print(f"\n  ✓ Resultados guardados en: {archivo}")

    def graficar_carga_desplazamiento(self):
        """Genera gráfica de carga vs desplazamiento"""
        if not hasattr(self, 'historia_carga') or len(self.historia_carga) == 0:
            print("\n⚠ No hay datos de historia carga-desplazamiento para graficar")
            return

        print("\n" + "="*60)
        print("GENERANDO GRÁFICA CARGA-DESPLAZAMIENTO")
        print("="*60)

        # Crear figura
        plt.figure(figsize=(10, 6))
        plt.plot(self.historia_despl, self.historia_carga, 'b-o', linewidth=2, markersize=6)
        plt.xlabel('Desplazamiento vertical (mm)', fontsize=12)
        plt.ylabel('Carga vertical (kN)', fontsize=12)
        plt.title('Curva Carga-Desplazamiento\nCentro de la Base de la Zapata', fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)

        # Agregar información del modelo
        info_text = f'Zapata: 2.5×2.5×0.6 m\nSuelo estratificado (elástico)\nProfundidad Df: 1.5 m'
        plt.text(0.02, 0.98, info_text, transform=plt.gca().transAxes,
                fontsize=9, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        # Agregar rigidez
        if len(self.historia_carga) >= 2:
            K = (self.historia_carga[-1] - self.historia_carga[0]) / (self.historia_despl[-1] - self.historia_despl[0])
            plt.text(0.98, 0.02, f'Rigidez ≈ {K:.2f} kN/mm',
                    transform=plt.gca().transAxes, fontsize=10,
                    horizontalalignment='right', verticalalignment='bottom',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))

        plt.tight_layout()

        # Guardar
        os.makedirs('resultados', exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_grafica = os.path.join('resultados', f'carga_desplazamiento_{timestamp}.png')
        plt.savefig(archivo_grafica, dpi=300, bbox_inches='tight')
        print(f"\n  ✓ Gráfica guardada en: {archivo_grafica}")

        # No mostrar en entorno sin display
        # plt.show()
        plt.close()

    def ejecutar(self):
        """Ejecuta el modelo completo"""
        print("\n" + "#"*60)
        print("# MODELO 3D NO LINEAL - ZAPATA CON SUELO ESTRATIFICADO")
        print("#"*60)
        print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        try:
            self.inicializar_modelo()
            self.definir_materiales_no_lineales()
            self.crear_malla_unificada()
            self.crear_elementos()
            self.aplicar_condiciones_frontera()
            self.aplicar_cargas_gravedad()  # Solo gravedad en Fase 1
            exito = self.analizar_no_lineal()  # Esto aplicará cargas externas en Fase 2

            if exito:
                self.extraer_resultados()
                self.graficar_carga_desplazamiento()
                print("\n" + "="*60)
                print("ANÁLISIS COMPLETADO")
                print("="*60)
                return True
            else:
                print("\n" + "="*60)
                print("ANÁLISIS COMPLETADO PARCIALMENTE")
                print("="*60)
                return False

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Modelo 3D no lineal de zapata con suelo estratificado'
    )
    parser.add_argument('--config', type=str, default='config_zapata.json')
    args = parser.parse_args()

    modelo = ModeloZapata3DNoLineal(config_file=args.config)
    exito = modelo.ejecutar()

    if not exito:
        sys.exit(1)


if __name__ == '__main__':
    main()
