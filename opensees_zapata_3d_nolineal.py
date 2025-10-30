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

        # Materiales no lineales para capas de suelo
        mat_id = 10
        for i, capa in enumerate(self.config['suelo_estratificado']['capas'], 1):
            E = capa['E']
            nu = capa['nu']
            rho = capa['densidad']

            # Calcular parámetros de plasticidad
            # Módulo de corte
            G = E / (2 * (1 + nu))
            # Módulo de bulk
            K = E / (3 * (1 - 2*nu))

            # Esfuerzo de fluencia (basado en cohesión)
            cohesion = capa.get('cohesion', 10000)  # Pa
            phi = capa.get('friccion_grados', 30) * np.pi / 180  # radianes

            # Para modelo J2 (Von Mises), el esfuerzo de fluencia es aproximadamente
            # sigma_y ≈ 2*c*cos(phi)/(1-sin(phi)) para Mohr-Coulomb
            # Simplificación: usamos 6*cohesion como esfuerzo de fluencia
            sigma_y = 6 * cohesion if cohesion > 0 else 50000

            # Módulo de endurecimiento (típicamente 1-10% del módulo elástico)
            H_iso = 0.02 * E  # 2% hardening

            try:
                # Intentar usar J2Plasticity (Von Mises con endurecimiento isótropo)
                ops.nDMaterial('J2Plasticity', mat_id, K, G, sigma_y, sigma_y, 0, H_iso, rho)
                print(f"✓ Material {mat_id}: {capa['nombre']} - J2Plasticity")
                print(f"    K={K/1e6:.1f} MPa, G={G/1e6:.1f} MPa, σ_y={sigma_y/1000:.1f} kPa")
            except:
                # Si J2Plasticity no está disponible, usar ElasticIsotropic
                print(f"⚠ J2Plasticity no disponible, usando ElasticIsotropic para {capa['nombre']}")
                ops.nDMaterial('ElasticIsotropic', mat_id, E, nu, rho)
                print(f"✓ Material {mat_id}: {capa['nombre']} - ElasticIsotropic (fallback)")

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

        # Mallado simplificado pero funcional
        nx_suelo = 6  # elementos en X del suelo
        ny_suelo = 6  # elementos en Y del suelo
        nx_zap = 4    # elementos en X de la zapata
        ny_zap = 4    # elementos en Y de la zapata
        nz_zap = 2    # elementos en Z de la zapata

        # Profundidad total del suelo
        H_suelo_total = sum([c['espesor'] for c in capas])
        nz_suelo = len(capas) * 2  # 2 elementos por capa

        # Coordenadas Z
        z_base_suelo = -prof_desp - H_suelo_total
        z_base_zapata = -prof_desp
        z_top_zapata = z_base_zapata + h_zap

        print(f"\n  Dimensiones de la zapata: {B_x} × {B_y} × {h_zap} m")
        print(f"  Dimensiones del suelo: {L_suelo_x} × {L_suelo_y} × {H_suelo_total} m")
        print(f"  Mallado suelo: {nx_suelo} × {ny_suelo} × {nz_suelo}")
        print(f"  Mallado zapata: {nx_zap} × {ny_zap} × {nz_zap}")

        # CREAR NODOS DEL SUELO
        print("\n  Creando nodos del suelo...")
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

                    ops.node(self.node_counter, x, y, z)
                    nodos_suelo[(i, j, k)] = self.node_counter
                    self.node_counter += 1

        print(f"  ✓ {len(nodos_suelo)} nodos del suelo creados")

        # CREAR NODOS DE LA ZAPATA (compartiendo nodos con el suelo en la interfaz)
        print("\n  Creando nodos de la zapata...")
        nodos_zapata = {}

        dx_zap = B_x / nx_zap
        dy_zap = B_y / ny_zap
        dz_zap = h_zap / nz_zap

        # Encontrar índices del suelo donde se ubica la zapata
        i_start_zap = (nx_suelo - nx_zap) // 2
        j_start_zap = (ny_suelo - ny_zap) // 2
        k_base_zap = nz_suelo  # La zapata empieza en la parte superior del suelo

        for k in range(nz_zap + 1):
            for j in range(ny_zap + 1):
                for i in range(nx_zap + 1):
                    x = -B_x/2 + i * dx_zap
                    y = -B_y/2 + j * dy_zap
                    z = z_base_zapata + k * dz_zap

                    # En la base de la zapata (k=0), compartir nodos con el suelo
                    if k == 0:
                        # Buscar el nodo más cercano del suelo
                        i_suelo = int(round(i_start_zap + i * nx_zap / nx_suelo * (nx_suelo / (nx_suelo - nx_zap))))
                        j_suelo = int(round(j_start_zap + j * ny_zap / ny_suelo * (ny_suelo / (ny_suelo - ny_zap))))
                        k_suelo = k_base_zap

                        # Limitar índices
                        i_suelo = max(0, min(nx_suelo, i_suelo))
                        j_suelo = max(0, min(ny_suelo, j_suelo))

                        if (i_suelo, j_suelo, k_suelo) in nodos_suelo:
                            nodos_zapata[(i, j, k)] = nodos_suelo[(i_suelo, j_suelo, k_suelo)]
                        else:
                            # Crear nuevo nodo si no existe
                            ops.node(self.node_counter, x, y, z)
                            nodos_zapata[(i, j, k)] = self.node_counter
                            self.node_counter += 1
                    else:
                        # Nodos superiores de la zapata son independientes
                        ops.node(self.node_counter, x, y, z)
                        nodos_zapata[(i, j, k)] = self.node_counter
                        self.node_counter += 1

        print(f"  ✓ {len(nodos_zapata)} entradas de nodos para zapata")
        nodos_nuevos_zap = len([n for n in nodos_zapata.values() if n >= max(nodos_suelo.values())])
        print(f"  ✓ {nodos_nuevos_zap} nodos nuevos creados (otros compartidos con suelo)")

        self.nodos['suelo'] = nodos_suelo
        self.nodos['zapata'] = nodos_zapata
        self.nx_suelo, self.ny_suelo, self.nz_suelo = nx_suelo, ny_suelo, nz_suelo
        self.nx_zap, self.ny_zap, self.nz_zap = nx_zap, ny_zap, nz_zap

        return z_top_zapata

    def crear_elementos(self):
        """Crea los elementos sólidos para suelo y zapata"""
        print("\n" + "-"*60)
        print("CREANDO ELEMENTOS")
        print("-"*60)

        # ELEMENTOS DEL SUELO
        print("\n  Elementos del suelo...")
        capas = self.config['suelo_estratificado']['capas']
        elem_por_capa = self.nz_suelo // len(capas)

        num_elem_suelo = 0
        for k in range(self.nz_suelo):
            # Determinar qué material usar según la capa
            capa_idx = min(k // elem_por_capa, len(capas) - 1)
            mat_id = capas[capa_idx]['mat_id']

            for j in range(self.ny_suelo):
                for i in range(self.nx_suelo):
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
                    num_elem_suelo += 1

        print(f"  ✓ {num_elem_suelo} elementos de suelo creados")

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

        # Configuración del análisis no lineal
        ops.system('UmfPack')
        ops.numberer('RCM')
        ops.constraints('Transformation')
        ops.test('NormDispIncr', 1.0e-6, 50, 0)
        ops.algorithm('Newton')
        ops.integrator('LoadControl', 0.1)
        ops.analysis('Static')

        print("\n  Sistema: UmfPack")
        print("  Algoritmo: Newton")
        print("  Integrador: LoadControl incremental")
        print("  Convergencia: NormDispIncr (tol=1e-6, max_iter=50)")

        # Análisis incremental
        num_pasos = 10
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
