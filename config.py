#!/usr/bin/env python3
"""
Archivo de configuración para la generación de mallas de zapatas.
"""

# Parámetros de la zapata
ZAPATA = {
    'B': 1.0,      # Ancho (m)
    'L': 1.0,      # Largo (m)
    'h': 0.4,      # Altura/espesor (m)
    'Df': 1.2,     # Profundidad de desplante (m)
}

# Estratos de suelo (de arriba hacia abajo)
ESTRATOS_SUELO = [
    {
        'nombre': 'Suelo Superior',
        'espesor': 10.0,  # metros
        'E': 50e6,        # Módulo de Young (Pa)
        'nu': 0.3,        # Coeficiente de Poisson
        'rho': 2000,      # Densidad (kg/m³)
    },
    {
        'nombre': 'Suelo Intermedio',
        'espesor': 7.0,
        'E': 80e6,
        'nu': 0.3,
        'rho': 2100,
    },
    {
        'nombre': 'Suelo Profundo',
        'espesor': 3.0,
        'E': 100e6,
        'nu': 0.3,
        'rho': 2200,
    },
]

# Propiedades de la zapata (concreto)
PROPIEDADES_ZAPATA = {
    'E': 25e9,      # 25 GPa
    'nu': 0.2,
    'rho': 2400,    # kg/m³
}

# Parámetros de malla
MALLA = {
    'graded': {
        'dx_min': 0.05,   # Tamaño mínimo cerca de la zapata (m)
        'dx_max': 2.0,    # Tamaño máximo en fronteras (m)
    }
}

def obtener_dimensiones_dominio():
    """
    Calcula las dimensiones del dominio completo.
    Regla típica: dominio debe ser al menos 5 veces el ancho de la zapata
    """
    B = ZAPATA['B']
    L = ZAPATA['L']
    
    # Dimensiones del dominio (valores completos)
    Lx = max(9.0, 5 * B)  # Al menos 9m o 5B
    Ly = max(9.0, 5 * L)  # Al menos 9m o 5L
    
    # Profundidad total
    Lz = sum(e['espesor'] for e in ESTRATOS_SUELO)
    
    return {
        'Lx': Lx,
        'Ly': Ly,
        'Lz': Lz
    }

if __name__ == "__main__":
    # Test de configuración
    print("Configuración de la malla:")
    print(f"  Zapata: {ZAPATA['B']}m × {ZAPATA['L']}m × {ZAPATA['h']}m")
    print(f"  Profundidad: {ZAPATA['Df']}m")
    
    dims = obtener_dimensiones_dominio()
    print(f"  Dominio: {dims['Lx']}m × {dims['Ly']}m × {dims['Lz']}m")
    print(f"  Estratos: {len(ESTRATOS_SUELO)} capas")
    
    for i, est in enumerate(ESTRATOS_SUELO, 1):
        print(f"    {i}. {est['nombre']}: {est['espesor']}m")
