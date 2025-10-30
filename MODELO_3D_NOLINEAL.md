# MODELO 3D NO LINEAL - ZAPATA CON SUELO ESTRATIFICADO

**Archivo:** `opensees_zapata_3d_nolineal.py`
**Versión:** 2.0
**Fecha:** Octubre 2025

---

## RESUMEN

Este documento describe el modelo 3D mejorado de zapata con suelos no lineales en OpenSees. El modelo corrige los problemas del modelo original e implementa materiales no lineales para capturar el comportamiento elastoplástico del suelo.

---

## PROBLEMAS CORREGIDOS DEL MODELO ANTERIOR

### 1. **Problema: Nodos No Conectados**

**Modelo Original:**
- Cada componente (zapata, pedestal, suelo, lleno) creaba sus propios nodos independientes
- No había conectividad física entre componentes
- Resultado: Desplazamientos irreales (>100 m)

**Solución Implementada:**
- Malla unificada donde zapata y suelo **comparten nodos** en la interfaz
- Los nodos de la base de la zapata son los mismos nodos de la superficie del suelo
- Resultado: Continuidad de desplazamientos garantizada

```python
# En la base de la zapata (k=0), compartir nodos con el suelo
if k == 0:
    i_suelo = calcular_indice_suelo(i)
    j_suelo = calcular_indice_suelo(j)
    k_suelo = k_base_zap
    nodos_zapata[(i, j, k)] = nodos_suelo[(i_suelo, j_suelo, k_suelo)]
```

### 2. **Problema: Materiales Puramente Elásticos**

**Modelo Original:**
- Materiales ElasticIsotropic para todo
- No captura plasticidad del suelo
- No representa correctamente el comportamiento bajo cargas grandes

**Solución Implementada:**
- Materiales J2Plasticity (Von Mises) para suelo
- Incluye esfuerzo de fluencia y endurecimiento
- Captura comportamiento elastoplástico

```python
# Parámetros de plasticidad
sigma_y = 6 * cohesion  # Esfuerzo de fluencia
H_iso = 0.02 * E  # Módulo de endurecimiento (2%)

ops.nDMaterial('J2Plasticity', mat_id, K, G, sigma_y, sigma_y, 0, H_iso, rho)
```

### 3. **Problema: Análisis Inadecuado**

**Modelo Original:**
- Análisis lineal simple
- No maneja no linealidad del material
- Convergencia problemática

**Solución Implementada:**
- Análisis no lineal incremental
- Algoritmo Newton-Raphson con fallback a Modified Newton
- Control de convergencia con tolerancia estricta

---

## CARACTERÍSTICAS DEL NUEVO MODELO

### Geometría

```
┌────────────────────────────────────┐
│         SUPERFICIE (z=0)           │
├────────────────────────────────────┤
│                                    │
│  ┌────────────────┐               │
│  │    ZAPATA      │               │
│  │  2.5 × 2.5 m   │  Df = 1.5 m   │
│  │  h = 0.6 m     │               │
│  └────────────────┘               │
├────────────────────────────────────┤
│  CAPA 1: Arcilla (2.0 m)           │
│    E=10 MPa, σ_y=120 kPa          │
├────────────────────────────────────┤
│  CAPA 2: Arena (3.0 m)             │
│    E=30 MPa, σ_y=30 kPa           │
├────────────────────────────────────┤
│  CAPA 3: Grava (5.0 m)             │
│    E=80 MPa, σ_y=50 kPa           │
└────────────────────────────────────┘
       BASE FIJA (z=-11.5 m)
```

### Mallado

| Componente | Elementos en X | Elementos en Y | Elementos en Z | Total |
|------------|----------------|----------------|----------------|-------|
| Suelo | 6 | 6 | 6 | 216 |
| Zapata | 4 | 4 | 2 | 32 |
| **Total** | - | - | - | **248** |

**Nodos:**
- Suelo: 343 nodos
- Zapata: 54 nodos nuevos + 21 compartidos con suelo
- **Total: 397 nodos**

---

## MATERIALES NO LINEALES

### Material J2 Plasticity (Von Mises)

El modelo J2Plasticity implementa plasticidad de Von Mises con endurecimiento isótropo:

**Superficie de fluencia:**
```
f = √(3J₂) - σ_y ≤ 0
```

Donde:
- `J₂` = segundo invariante del tensor desviador de esfuerzos
- `σ_y` = esfuerzo de fluencia (variable con endurecimiento)

**Relación esfuerzo-deformación:**
```
σ = K·ε_vol + 2G·e  (dentro de la superficie de fluencia)
σ = σ_trial - 2G·Δλ·n  (en plastificación)
```

Donde:
- `K` = módulo de bulk = E / (3(1-2ν))
- `G` = módulo de corte = E / (2(1+ν))
- `Δλ` = multiplicador plástico
- `n` = normal a la superficie de fluencia

### Parámetros por Capa

#### Capa 1: Arcilla Blanda
```
E = 10 MPa
ν = 0.35
K = 11.1 MPa
G = 3.7 MPa
σ_y = 120 kPa (basado en cohesión de 20 kPa)
H_iso = 0.2 MPa (2% hardening)
```

#### Capa 2: Arena Limosa
```
E = 30 MPa
ν = 0.30
K = 25.0 MPa
G = 11.5 MPa
σ_y = 30 kPa (basado en cohesión de 5 kPa)
H_iso = 0.6 MPa (2% hardening)
```

#### Capa 3: Grava Arenosa
```
E = 80 MPa
ν = 0.25
K = 53.3 MPa
G = 32.0 MPa
σ_y = 50 kPa (material friccionante)
H_iso = 1.6 MPa (2% hardening)
```

**Nota:** El esfuerzo de fluencia se estima como `σ_y ≈ 6c` donde `c` es la cohesión. Para materiales friccionantes sin cohesión, se usa un valor mínimo de 50 kPa.

---

## CONDICIONES DE FRONTERA

### Restricciones en la Base
```
Nodos con z = z_base:
  Ux = Uy = Uz = 0 (empotrados)
```

### Restricciones Laterales (Confinamiento)
```
Nodos en x = x_min o x = x_max:
  Ux = 0 (movimiento en X restringido)

Nodos en y = y_min o y = y_max:
  Uy = 0 (movimiento en Y restringido)
```

Estas restricciones simulan el confinamiento lateral del suelo.

---

## ANÁLISIS NO LINEAL

### Algoritmo de Solución

```
┌─────────────────────────────────────┐
│  1. Dividir carga en incrementos    │
│     Δλ = 0.1 (10% por paso)         │
└───────────┬─────────────────────────┘
            │
            ▼
┌─────────────────────────────────────┐
│  2. Para cada incremento:           │
│     - Calcular K_tangente           │
│     - Resolver: K·ΔU = Δλ·P         │
│     - Verificar convergencia        │
└───────────┬─────────────────────────┘
            │
            ▼
┌─────────────────────────────────────┐
│  3. Si no converge:                 │
│     - Cambiar a Modified Newton     │
│     - Reducir incremento (opcional) │
│     - Reintentar                    │
└─────────────────────────────────────┘
```

### Parámetros de Convergencia

| Parámetro | Valor |
|-----------|-------|
| Test | NormDispIncr |
| Tolerancia | 1.0e-6 |
| Max Iteraciones | 50 |
| Incremento de carga | 0.1 (10%) |
| Número de pasos | 10 |

### Estrategia Adaptativa

1. **Primer intento:** Newton-Raphson
   - Más rápido, requiere matriz tangente exacta

2. **Fallback:** Modified Newton
   - Usa matriz inicial, más robusto

3. **Último recurso:** Reducir incremento
   - División de pasos (no implementado en esta versión)

---

## RESULTADOS Y VALIDACIÓN

### Caso de Prueba: Carga Vertical 500 kN

**Cargas Aplicadas:**
- Carga vertical: 500 kN
- Carga horizontal: 50 kN
- Distribuidas en 25 nodos superiores de la zapata

**Resultados Obtenidos:**

| Parámetro | Valor |
|-----------|-------|
| Asentamiento (centro, superficie) | 4.595 mm |
| Asentamiento (promedio, base zapata) | 4.356 mm |
| Desplazamiento horizontal X | 0.067 mm |
| Desplazamiento horizontal Y | 0.050 mm |
| Pasos convergidos | 10/10 (100%) |

**Análisis de Resultados:**

1. **Asentamiento (4.6 mm vs 29 mm del modelo simplificado):**
   - El modelo 3D da menor asentamiento debido a:
     * Confinamiento lateral del suelo (restricciones en bordes)
     * Distribución 3D de esfuerzos (Bulbo de presiones de Boussinesq)
     * Mayor volumen de suelo involucrado
   - El valor de 4.6 mm es más realista para este sistema confinado

2. **Desplazamientos Horizontales (< 0.1 mm):**
   - Muy pequeños debido al confinamiento lateral
   - Consistente con comportamiento esperado

3. **Convergencia:**
   - 100% de convergencia demuestra estabilidad numérica
   - Algoritmo Newton-Raphson efectivo para este nivel de no linealidad

### Comparación de Modelos

| Aspecto | Modelo Simplificado | Modelo 3D Lineal | **Modelo 3D No Lineal** |
|---------|---------------------|------------------|------------------------|
| Tipo | Resortes 1D | Elementos 3D | Elementos 3D |
| Material suelo | Elástico lineal | Elástico lineal | **J2 Plasticity** |
| Conectividad | N/A | ❌ Incorrecta | ✅ **Correcta** |
| Confinamiento | No | Sí | Sí |
| Análisis | Lineal | Lineal | **No lineal** |
| Asentamiento (500 kN) | 29.0 mm | >100 m (error) | **4.6 mm** |
| Tiempo de cómputo | < 1 s | ~ 5 s | **~ 10 s** |
| Aplicabilidad | Diseño preliminar | ❌ Buggy | ✅ **Diseño detallado** |

---

## USO DEL MODELO

### Ejecución Básica

```bash
python3 opensees_zapata_3d_nolineal.py
```

### Con Configuración Personalizada

```bash
python3 opensees_zapata_3d_nolineal.py --config mi_config.json
```

### Modificar Parámetros

Editar `config_zapata.json`:

```json
{
  "materiales": {
    "concreto_zapata": {
      "E": 2.5e10,
      "nu": 0.2
    }
  },
  "suelo_estratificado": {
    "capas": [
      {
        "nombre": "Arcilla blanda",
        "E": 1.0e7,
        "cohesion": 20000,
        "friccion_grados": 15
      }
    ]
  }
}
```

---

## LIMITACIONES Y CONSIDERACIONES

### Limitaciones Actuales

1. **Modelo Constitutivo:**
   - J2Plasticity no considera efecto del confinamiento (Drucker-Prager sería mejor)
   - No incluye ablandamiento (softening)
   - No considera comportamiento cíclico

2. **Geometría:**
   - Zapata cuadrada solamente
   - No incluye pedestal en esta versión
   - Mallado fijo (no adaptativo)

3. **Análisis:**
   - Solo cargas estáticas
   - No considera consolidación
   - No incluye cargas dinámicas o sísmicas

### Mejoras Futuras Sugeridas

1. **Material:**
   - Implementar Drucker-Prager para suelos cohesivo-friccionantes
   - Añadir PressureDependMultiYield para licuefacción
   - Incluir criterio de Mohr-Coulomb

2. **Geometría:**
   - Añadir pedestal
   - Implementar zapatas rectangulares
   - Refinamiento automático de malla

3. **Análisis:**
   - Análisis de consolidación
   - Análisis sísmico (time history)
   - Análisis de push-over

---

## REFERENCIAS TÉCNICAS

1. **OpenSees Documentation**
   - J2Plasticity Material: https://opensees.github.io/OpenSeesDocumentation/user/manual/material/ndMaterials/J2Plasticity.html
   - Brick Elements: https://opensees.github.io/OpenSeesDocumentation/user/manual/model/elements/brick.html

2. **Teoría de Plasticidad**
   - Simo, J.C. and Hughes, T.J.R. (1998). *Computational Inelasticity*. Springer.
   - Chen, W.F. and Mizuno, E. (1990). *Nonlinear Analysis in Soil Mechanics*. Elsevier.

3. **Geotecnia**
   - Potts, D.M. and Zdravković, L. (1999). *Finite Element Analysis in Geotechnical Engineering*. Thomas Telford.
   - Brinkgreve, R.B.J. et al. (2010). *PLAXIS Manual*. Delft University of Technology.

---

## APÉNDICE: ECUACIONES FUNDAMENTALES

### Equilibrio

```
∇·σ + ρg = 0
```

### Relaciones Constitutivas (J2 Plasticity)

**Descomposición de deformaciones:**
```
ε = εᵉ + εᵖ
```

**Parte elástica:**
```
σ = C : εᵉ
```

Donde C es el tensor de rigidez elástica.

**Condición de fluencia:**
```
f(σ, α) = √(3J₂(s)) - (σ_y + K_iso·α) ≤ 0
```

Donde:
- s = desviador de esfuerzos
- α = parámetro de endurecimiento
- K_iso = módulo de endurecimiento

**Regla de flujo:**
```
dεᵖ = dλ · ∂f/∂σ
```

**Condiciones de Kuhn-Tucker:**
```
dλ ≥ 0
f ≤ 0
dλ · f = 0
```

---

**FIN DEL DOCUMENTO**
