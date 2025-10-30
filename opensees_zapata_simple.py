#!/usr/bin/env python3
"""
Modelo Simplificado de Zapata con Suelo Estratificado en OpenSees
================================================================

Modelo simplificado usando resortes para representar el suelo estratificado.
Este enfoque es más robusto y computacionalmente eficiente.

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


class ModeloZapataSimple:
    """Modelo simplificado de zapata con resortes para el suelo"""

    def __init__(self, config_file='config_zapata.json'):
        self.config_file = config_file
        self.cargar_configuracion()

    def cargar_configuracion(self):
        """Carga la configuración"""
        with open(self.config_file, 'r') as f:
            self.config = json.load(f)
        print(f"✓ Configuración cargada desde {self.config_file}")

    def calcular_rigidez_suelo(self):
        """
        Calcula la rigidez del suelo estratificado usando la teoría de Boussinesq
        y considerando las capas en serie
        """
        capas = self.config['suelo_estratificado']['capas']
        geom = self.config['geometria']['zapata']

        B = min(geom['ancho_x'], geom['ancho_y'])  # Ancho mínimo
        area = geom['ancho_x'] * geom['ancho_y']

        # Rigidez vertical equivalente (capas en serie)
        flexibilidad_total = 0
        for capa in capas:
            E = capa['E']
            nu = capa['nu']
            H = capa['espesor']

            # Módulo de corte
            G = E / (2 * (1 + nu))

            # Flexibilidad de la capa (aproximación)
            flex_capa = H / (E * area)
            flexibilidad_total += flex_capa

        K_vertical = 1.0 / flexibilidad_total

        # Rigidez horizontal (aproximadamente 50-60% de la vertical para suelo)
        K_horizontal = 0.5 * K_vertical

        # Rigidez rotacional
        I = (geom['ancho_x'] * geom['ancho_y']**3) / 12
        K_rotacional = K_vertical * I / area

        return K_vertical, K_horizontal, K_rotacional

    def crear_modelo(self):
        """Crea el modelo completo"""
        print("\n" + "="*60)
        print("MODELO SIMPLIFICADO DE ZAPATA")
        print("="*60)

        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)

        geom_zap = self.config['geometria']['zapata']
        geom_ped = self.config['geometria']['pedestal']
        prof_desp = self.config['geometria']['profundidad_desplante']

        # Calcular rigidez del suelo
        K_v, K_h, K_r = self.calcular_rigidez_suelo()

        print(f"\n✓ Rigideces del suelo estratificado:")
        print(f"  Vertical: {K_v/1e9:.2f} GN/m")
        print(f"  Horizontal: {K_h/1e9:.2f} GN/m")
        print(f"  Rotacional: {K_r/1e12:.2f} GN·m/rad (×10¹²)")

        # Nodo en la base (fijo - representa el suelo profundo)
        z_base = -prof_desp - sum([c['espesor'] for c in self.config['suelo_estratificado']['capas']])
        ops.node(1, 0, 0, z_base)
        ops.fix(1, 1, 1, 1, 1, 1, 1)

        # Nodo en la base de la zapata (conectado al suelo con resortes)
        z_base_zapata = -prof_desp
        ops.node(2, 0, 0, z_base_zapata)

        # Nodo en la parte superior de la zapata
        z_top_zapata = z_base_zapata + geom_zap['espesor']
        ops.node(3, 0, 0, z_top_zapata)

        # Nodo en la parte superior del pedestal (donde se aplica la carga)
        z_top_pedestal = z_top_zapata + geom_ped['altura']
        ops.node(4, 0, 0, z_top_pedestal)

        print(f"\n✓ Nodos creados:")
        print(f"  Nodo 1: Base fija a z = {z_base:.2f} m")
        print(f"  Nodo 2: Base de zapata a z = {z_base_zapata:.2f} m")
        print(f"  Nodo 3: Top de zapata a z = {z_top_zapata:.2f} m")
        print(f"  Nodo 4: Top de pedestal a z = {z_top_pedestal:.2f} m")

        # Materiales para resortes del suelo (uniaxiales)
        ops.uniaxialMaterial('Elastic', 1, K_v)  # Vertical
        ops.uniaxialMaterial('Elastic', 2, K_h)  # Horizontal X
        ops.uniaxialMaterial('Elastic', 3, K_h)  # Horizontal Y
        ops.uniaxialMaterial('Elastic', 4, K_r)  # Rotación X
        ops.uniaxialMaterial('Elastic', 5, K_r)  # Rotación Y
        ops.uniaxialMaterial('Elastic', 6, K_r)  # Rotación Z

        # Resortes del suelo (conectan nodo 1 a nodo 2)
        # zeroLength con los 6 grados de libertad
        ops.element('zeroLength', 1, 1, 2, '-mat', 2, 3, 1, 4, 5, 6,
                   '-dir', 1, 2, 3, 4, 5, 6)

        print(f"\n✓ Resortes de suelo creados (elemento 1)")

        # Materiales para concreto (muy rígido)
        E_conc = self.config['materiales']['concreto_zapata']['E']
        G_conc = E_conc / (2 * (1 + self.config['materiales']['concreto_zapata']['nu']))
        A_zapata = geom_zap['ancho_x'] * geom_zap['ancho_y']
        I_zapata = (geom_zap['ancho_x'] * geom_zap['ancho_y']**3) / 12
        A_pedestal = geom_ped['ancho_x'] * geom_ped['ancho_y']
        I_pedestal = (geom_ped['ancho_x'] * geom_ped['ancho_y']**3) / 12

        # Transformación geométrica
        ops.geomTransf('Linear', 1, 1, 0, 0)

        # Elemento para la zapata (nodo 2 a nodo 3)
        ops.element('elasticBeamColumn', 2, 2, 3,
                   A_zapata, E_conc, G_conc,
                   I_zapata, I_zapata, 2*I_zapata, 1)

        # Elemento para el pedestal (nodo 3 a nodo 4)
        ops.element('elasticBeamColumn', 3, 3, 4,
                   A_pedestal, E_conc, G_conc,
                   I_pedestal, I_pedestal, 2*I_pedestal, 1)

        print(f"✓ Elementos de concreto creados (zapata y pedestal)")

        return K_v, K_h, K_r

    def aplicar_cargas(self):
        """Aplica las cargas"""
        print("\n" + "="*60)
        print("APLICANDO CARGAS")
        print("="*60)

        cargas = self.config['cargas']

        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)

        # Aplicar cargas en el nodo 4 (top del pedestal)
        ops.load(4,
                cargas['carga_horizontal_x'],
                cargas['carga_horizontal_y'],
                cargas['carga_vertical'],
                cargas['momento_x'],
                cargas['momento_y'],
                0.0)

        print(f"✓ Cargas aplicadas en nodo 4 (top del pedestal):")
        print(f"  Fx = {cargas['carga_horizontal_x']/1000:.1f} kN")
        print(f"  Fy = {cargas['carga_horizontal_y']/1000:.1f} kN")
        print(f"  Fz = {cargas['carga_vertical']/1000:.1f} kN")
        print(f"  Mx = {cargas['momento_x']/1000:.1f} kN·m")
        print(f"  My = {cargas['momento_y']/1000:.1f} kN·m")

    def analizar(self):
        """Ejecuta el análisis"""
        print("\n" + "="*60)
        print("EJECUTANDO ANÁLISIS")
        print("="*60)

        ops.system('BandGen')
        ops.numberer('RCM')
        ops.constraints('Plain')
        ops.integrator('LoadControl', 0.1)
        ops.algorithm('Linear')
        ops.analysis('Static')

        print("✓ Análisis configurado (Linear - modelo elástico)")

        # Analizar
        ok = ops.analyze(10)

        if ok == 0:
            print("✓ Análisis completado exitosamente")
            return True
        else:
            print(f"✗ Error en análisis: código {ok}")
            return False

    def extraer_resultados(self):
        """Extrae y muestra resultados"""
        print("\n" + "="*60)
        print("RESULTADOS")
        print("="*60)

        # Desplazamientos del nodo de carga (nodo 4)
        disp4 = ops.nodeDisp(4)
        print(f"\n✓ Desplazamientos en punto de carga (nodo 4 - top del pedestal):")
        print(f"  Ux = {disp4[0]*1000:.3f} mm")
        print(f"  Uy = {disp4[1]*1000:.3f} mm")
        print(f"  Uz = {disp4[2]*1000:.3f} mm (asentamiento)")
        print(f"  Rx = {disp4[3]*1000:.3f} mrad")
        print(f"  Ry = {disp4[4]*1000:.3f} mrad")

        # Desplazamientos en la base de la zapata (nodo 2)
        disp2 = ops.nodeDisp(2)
        print(f"\n✓ Desplazamientos en base de zapata (nodo 2):")
        print(f"  Ux = {disp2[0]*1000:.3f} mm")
        print(f"  Uy = {disp2[1]*1000:.3f} mm")
        print(f"  Uz = {disp2[2]*1000:.3f} mm (asentamiento)")
        print(f"  Rx = {disp2[3]*1000:.3f} mrad")
        print(f"  Ry = {disp2[4]*1000:.3f} mrad")

        # Reacciones en la base
        reac1 = ops.nodeReaction(1)
        print(f"\n✓ Reacciones en la base (nodo 1 - suelo profundo):")
        print(f"  Rx = {-reac1[0]/1000:.2f} kN")
        print(f"  Ry = {-reac1[1]/1000:.2f} kN")
        print(f"  Rz = {-reac1[2]/1000:.2f} kN")
        print(f"  Mx = {-reac1[3]/1000:.2f} kN·m")
        print(f"  My = {-reac1[4]/1000:.2f} kN·m")

        # Guardar resultados
        os.makedirs('resultados', exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_res = os.path.join('resultados', f'resultados_simple_{timestamp}.txt')

        with open(archivo_res, 'w') as f:
            f.write("="*60 + "\n")
            f.write("RESULTADOS DEL ANÁLISIS - MODELO SIMPLIFICADO\n")
            f.write("="*60 + "\n\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("DESPLAZAMIENTOS EN PUNTO DE CARGA (top del pedestal):\n")
            f.write(f"  Horizontal X: {disp4[0]*1000:.3f} mm\n")
            f.write(f"  Horizontal Y: {disp4[1]*1000:.3f} mm\n")
            f.write(f"  Vertical (asentamiento): {disp4[2]*1000:.3f} mm\n")
            f.write(f"  Rotación X: {disp4[3]*1000:.3f} mrad\n")
            f.write(f"  Rotación Y: {disp4[4]*1000:.3f} mrad\n\n")

            f.write("DESPLAZAMIENTOS EN BASE DE ZAPATA:\n")
            f.write(f"  Horizontal X: {disp2[0]*1000:.3f} mm\n")
            f.write(f"  Horizontal Y: {disp2[1]*1000:.3f} mm\n")
            f.write(f"  Vertical (asentamiento): {disp2[2]*1000:.3f} mm\n")
            f.write(f"  Rotación X: {disp2[3]*1000:.3f} mrad\n")
            f.write(f"  Rotación Y: {disp2[4]*1000:.3f} mrad\n\n")

            f.write("REACCIONES EN LA BASE:\n")
            f.write(f"  Rx: {-reac1[0]/1000:.2f} kN\n")
            f.write(f"  Ry: {-reac1[1]/1000:.2f} kN\n")
            f.write(f"  Rz: {-reac1[2]/1000:.2f} kN\n")
            f.write(f"  Mx: {-reac1[3]/1000:.2f} kN·m\n")
            f.write(f"  My: {-reac1[4]/1000:.2f} kN·m\n")

        print(f"\n✓ Resultados guardados en: {archivo_res}")

        return disp4, disp2, reac1

    def ejecutar(self):
        """Ejecuta el modelo completo"""
        print("\n" + "#"*60)
        print("# MODELO SIMPLIFICADO DE ZAPATA CON SUELO ESTRATIFICADO")
        print("#"*60)
        print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        try:
            K_v, K_h, K_r = self.crear_modelo()
            self.aplicar_cargas()
            exito = self.analizar()

            if exito:
                self.extraer_resultados()

                print("\n" + "="*60)
                print("ANÁLISIS COMPLETADO EXITOSAMENTE")
                print("="*60)
                return True
            else:
                return False

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Modelo simplificado de zapata con suelo estratificado'
    )
    parser.add_argument('--config', type=str, default='config_zapata.json',
                       help='Archivo de configuración')

    args = parser.parse_args()

    modelo = ModeloZapataSimple(config_file=args.config)
    exito = modelo.ejecutar()

    if not exito:
        sys.exit(1)


if __name__ == '__main__':
    main()
