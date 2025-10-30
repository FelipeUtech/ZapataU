# ZapataU - Modelo de Zapata en OpenSees

Modelo de zapata (footing) con interacción suelo-estructura usando OpenSees.

## Descripción

Este proyecto implementa un modelo tridimensional de una zapata apoyada en suelo estratificado, incluyendo:

- **Zapata**: Elemento de fundación con dimensiones configurables
- **Suelo estratificado**: Múltiples capas de suelo con propiedades diferentes
- **Profundidad de desplante (Df)**: Zapata ubicada a profundidad Df bajo la superficie
- **Pedestal**: Columna que sobresale 0.5 m sobre la zapata
- **Lleno**: Material de relleno sobre la zapata hasta la superficie

## Características del Modelo

- Modelado 3D con elementos finitos
- Suelo modelado con elementos sólidos y resortes no lineales
- Interacción suelo-estructura
- Análisis estático y dinámico disponible
- Configuración paramétrica mediante archivo JSON
- Dos versiones disponibles: modelo 3D completo y modelo simplificado

## Ejemplo de Resultados

![Resultados del Modelo](ejemplos/resultados/graficas_modelo_zapata.png)

*Ejemplo de análisis con carga vertical de 500 kN mostrando asentamiento de 29 mm*

## Requisitos

- Python 3.7+
- OpenSeesPy
- NumPy
- Matplotlib

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

### Modelo Simplificado (Recomendado)

El modelo simplificado usa resortes equivalentes para representar el suelo estratificado. Es más robusto y eficiente computacionalmente.

```bash
# Ejecutar modelo simplificado
python opensees_zapata_simple.py

# Generar visualizaciones
python visualizar_simple.py
```

### Modelo 3D Completo

Modelo con elementos sólidos brick para todos los componentes.

```bash
# Ejecutar modelo 3D completo
python opensees_zapata_model.py

# Visualizar resultados
python visualizar_resultados.py
```

### Ejecución con configuración personalizada

```bash
python opensees_zapata_simple.py --config mi_configuracion.json
```

## Estructura del Proyecto

```
ZapataU/
├── README.md                      # Este archivo
├── requirements.txt               # Dependencias de Python
├── config_zapata.json            # Configuración del modelo
├── opensees_zapata_simple.py     # Modelo simplificado (recomendado)
├── opensees_zapata_model.py      # Modelo 3D completo
├── visualizar_simple.py          # Visualización modelo simplificado
├── visualizar_resultados.py      # Visualización modelo 3D
├── ejemplo_ejecucion.sh          # Script de ejemplo
├── ejemplos/                     # Ejemplos de resultados
│   └── resultados/
│       ├── graficas_modelo_zapata.png
│       └── ejemplo_resultados.txt
└── resultados/                   # Carpeta para resultados (auto-generada)
```

## Configuración del Modelo

Edita `config_zapata.json` para modificar:

- Dimensiones de la zapata
- Propiedades de capas de suelo
- Profundidad de desplante
- Cargas aplicadas
- Parámetros de análisis

## Resultados

El modelo genera:

- Desplazamientos nodales
- Reacciones en la base
- Distribución de presiones
- Gráficos de deformada
- Archivos de salida para post-procesamiento

## Autor

Desarrollado con Claude AI para análisis de fundaciones.

## Licencia

MIT License
