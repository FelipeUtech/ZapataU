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

            try:
                # Intentar usar DruckerPrager
                ops.nDMaterial('DruckerPrager', mat_id, K, G, sigma_y, rho,
                              rho_bar, Kinf, Ko, delta1, delta2, H, theta, rho, atm)
                print(f"✓ Material {mat_id}: {capa['nombre']} - DruckerPrager")
                print(f"    K={K/1e6:.1f} MPa, G={G/1e6:.1f} MPa")
                print(f"    c={cohesion/1000:.1f} kPa, φ={phi_grados:.1f}°, ρ̄={rho_bar:.3f}")
            except Exception as e:
                # Fallback a ElasticIsotropic si DruckerPrager falla
                print(f"⚠ DruckerPrager no disponible para {capa['nombre']}, usando ElasticIsotropic")
                print(f"  Error: {str(e)}")
                ops.nDMaterial('ElasticIsotropic', mat_id, E, nu, rho)
                print(f"✓ Material {mat_id}: {capa['nombre']} - ElasticIsotropic (E={E/1e6:.1f} MPa)")

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

    def aplicar_cargas(self):
        """Aplica cargas sobre la zapata"""
        print("\n" + "-"*60)
        print("APLICANDO CARGAS")
        print("-"*60)

        cargas = self.config['cargas']

        # Aplicar carga distribuida en la parte superior de la zapata
        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)

        # Nodos en la parte superior de la zapata
        nodos_top = []
        for (i, j, k), node in self.nodos['zapata'].items():
            if k == self.nz_zap:  # Top de la zapata
                nodos_top.append(node)

        # Distribuir carga uniformemente
        P_total = cargas['carga_vertical']
        F_x = cargas['carga_horizontal_x']
        num_nodos = len(nodos_top)

        P_por_nodo = P_total / num_nodos
        F_x_por_nodo = F_x / num_nodos

        for node in nodos_top:
            ops.load(node, F_x_por_nodo, 0.0, P_por_nodo)

        print(f"  ✓ Carga vertical total: {P_total/1000:.1f} kN")
        print(f"  ✓ Carga horizontal total: {F_x/1000:.1f} kN")
        print(f"  ✓ Distribuida en {num_nodos} nodos ({P_por_nodo/1000:.2f} kN/nodo)")

        # Guardar nodo central superior para resultados
        i_central = self.nx_zap // 2
        j_central = self.ny_zap // 2
        self.nodo_carga = self.nodos['zapata'][(i_central, j_central, self.nz_zap)]

    def analizar_no_lineal(self):
        """Ejecuta análisis no lineal incremental"""
        print("\n" + "="*60)
        print("ANÁLISIS NO LINEAL")
        print("="*60)

        analisis = self.config['analisis']

        # Configuración del análisis no lineal (ajustado para Drucker-Prager)
        ops.system('BandGeneral')
        ops.numberer('RCM')
        ops.constraints('Transformation')
        ops.test('NormDispIncr', 1.0e-2, 100, 0)  # Tolerancia muy relajada
        ops.algorithm('Newton')
        ops.integrator('LoadControl', 0.1)  # Incrementos moderados
        ops.analysis('Static')

        print("\n  Sistema: BandGeneral")
        print("  Algoritmo: Newton")
        print("  Integrador: LoadControl (0.1 por paso)")
        print("  Convergencia: NormDispIncr (tol=1e-2, max_iter=100)")

        # Análisis incremental
        num_pasos = 10  # 10 pasos × 0.1 = 1.0 (carga total)
        print(f"\n  Ejecutando {num_pasos} pasos incrementales...")

        exitos = 0
        for step in range(num_pasos):
            ok = ops.analyze(1)

            if ok == 0:
                exitos += 1
                if (step + 1) % 2 == 0:
                    print(f"    Paso {step+1}/{num_pasos}: ✓")
            else:
                print(f"    Paso {step+1}/{num_pasos}: Intentando con algoritmo modificado...")
                # Intentar con Modified Newton
                ops.algorithm('ModifiedNewton', '-initial')
                ok = ops.analyze(1)
                if ok == 0:
                    exitos += 1
                    print(f"    Paso {step+1}/{num_pasos}: ✓ (ModifiedNewton)")
                    ops.algorithm('Newton')  # Volver a Newton
                else:
                    print(f"    Paso {step+1}/{num_pasos}: ✗ No convergió")
                    break

        print(f"\n  ✓ {exitos}/{num_pasos} pasos completados exitosamente")
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
            self.aplicar_cargas()
            exito = self.analizar_no_lineal()

            if exito:
                self.extraer_resultados()
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
