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

### Ejecución básica

```bash
python opensees_zapata_model.py
```

### Ejecución con configuración personalizada

```bash
python opensees_zapata_model.py --config mi_configuracion.json
```

### Visualización de resultados

```bash
python visualizar_resultados.py
```

## Estructura del Proyecto

```
ZapataU/
├── README.md                    # Este archivo
├── requirements.txt             # Dependencias de Python
├── config_zapata.json          # Configuración del modelo
├── opensees_zapata_model.py    # Script principal del modelo
├── visualizar_resultados.py    # Script de visualización
└── resultados/                 # Carpeta para resultados (creada automáticamente)
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
