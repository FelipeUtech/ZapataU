#!/bin/bash
# Script de ejemplo para ejecutar el modelo de zapata en OpenSees
# Este script ejecuta el análisis completo y genera visualizaciones

echo "=========================================="
echo "Modelo de Zapata en OpenSees - Ejemplo"
echo "=========================================="
echo ""

# Verificar que existe Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 no está instalado"
    exit 1
fi

# Instalar dependencias si es necesario
echo "Instalando dependencias..."
pip install -r requirements.txt -q

echo ""
echo "=========================================="
echo "Ejecutando modelo de OpenSees..."
echo "=========================================="
echo ""

# Ejecutar el modelo
python3 opensees_zapata_model.py

# Verificar si el análisis fue exitoso
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Generando visualizaciones..."
    echo "=========================================="
    echo ""

    # Generar visualizaciones
    python3 visualizar_resultados.py

    echo ""
    echo "=========================================="
    echo "COMPLETADO"
    echo "=========================================="
    echo ""
    echo "Revisa los resultados en:"
    echo "  - resultados/          : Archivos de datos"
    echo "  - resultados/graficas/ : Gráficas generadas"
    echo ""
else
    echo ""
    echo "Error: El análisis falló"
    exit 1
fi
