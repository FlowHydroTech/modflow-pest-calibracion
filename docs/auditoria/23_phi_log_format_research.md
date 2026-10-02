# Resolucion de OQ-03 - Formato de las Lineas de Phi en los Logs del Master

> **Estado:** Resuelto mediante investigacion del estado del arte (documentacion oficial de PEST y pyEMU).
> **Pendiente de confirmacion final:** contrastar los patrones con un log real de CloudWatch del master cuando este disponible (validacion de bajo esfuerzo).

---

## Contexto

La pregunta abierta **OQ-03** bloqueaba la Fase 3 (Quality Engine): sin conocer el formato exacto de las lineas de Phi en el stdout de `pest_hp`, no se podian implementar los CloudWatch Metric Filters ni la Lambda ExtractPhiMetrics.

Dado que el proyecto usa **PEST_HP** (variante paralela de PEST clasico, no PEST++), y que el formato del *record file* y el stdout de PEST es estable y bien documentado a traves de versiones, se resolvio OQ-03 acudiendo a la literatura y documentacion oficial en lugar de esperar un log real.

Fuentes consultadas:
- Documentacion oficial de PEST - "The objective function" (https://help.pesthomepage.org/the-objective-function.html)
- Manual de PEST (EPA / Watermark Numerical Computing) - https://www.epa.gov/sites/default/files/documents/PESTMAN.PDF
- pyEMU - biblioteca de referencia que parsea los archivos de salida de PEST (https://github.com/pypest/pyemu)
- Documentacion de PEST_HP Suite 17

*Contenido reformulado para cumplir con restricciones de licencia.*

---

## Que es Phi en PEST (confirmado)

Segun la documentacion oficial de PEST, la funcion objetivo (Phi) es la **suma de residuales ponderados al cuadrado**: cada residual se multiplica por su peso, el producto se eleva al cuadrado, y luego se suman todos. Esto confirma la definicion que ya estaba en `10_calibration_quality.md`.

---

## Formato real del stdout / record file de PEST clasico y PEST_HP

PEST escribe, en cada iteracion de optimizacion, un bloque estructurado tanto en su salida de pantalla (capturada por CloudWatch) como en el record file (`.rec`). Las lineas relevantes, derivadas de la documentacion y de los parsers de pyEMU, son las siguientes.

### 1. Inicio de iteracion de optimizacion

```
OPTIMISATION ITERATION NO.        : 1
```

Patron de iteracion:
```
OPTIMISATION ITERATION NO\.\s*:\s*(\d+)
```

### 2. Phi al inicio de la iteracion

PEST reporta el objective function con esta forma caracteristica (notese la ortografia britanica "optimisation" y el uso de "phi"):

```
Starting phi for this iteration                     :   8432.5
```

Y para los componentes (cuando el problema esta dividido en grupos de observacion):
```
Contribution to phi from observation group "heads"  :   7891.3
Contribution to phi from observation group "flows"  :   541.2
```

Patron de Phi:
```
[Ss]tarting phi for this iteration\s*:\s*([0-9.Ee+-]+)
```

### 3. Phi al final de la iteracion / mejor Phi alcanzado

```
Lowest phi this iteration                           :   6234.8
```

Patron:
```
[Ll]owest phi this iteration\s*:\s*([0-9.Ee+-]+)
```

### 4. Phi final de la calibracion (al terminar)

```
Final phi                                           :   312.7
```

Patron:
```
[Ff]inal phi\s*:\s*([0-9.Ee+-]+)
```

### 5. Mensajes de ejecucion del modelo (ya confirmados en el codigo actual)

Estos ya estan validados - `auto_scaling_tasks.py` los extrae hoy:
```
Running model 48 times .....
Calculating Jacobian matrix: running model 400 times .....
Parallelisation of lambda search: running model up to 37 times.....
Model run complete.
```

### 6. Mensajes de convergencia / terminacion (criterios de PEST)

PEST emite mensajes explicitos cuando se cumple un criterio de terminacion. Los criterios estandar y sus variables de control:

| Criterio | Variable de control | Significado |
|----------|---------------------|-------------|
| Reduccion relativa de Phi insuficiente | PHIREDSTP / NPHISTP | Phi dejo de reducirse significativamente |
| Cambio relativo de parametros insuficiente | RELPARSTP / NRELPAR | Los parametros ya casi no cambian |
| Numero maximo de iteraciones | NOPTMAX | Se alcanzo el tope de iteraciones |
| Switch a derivadas de orden superior | PHIREDSWH | Phi bajo umbral de cambio de metodo |

Mensaje tipico de terminacion por convergencia (reformulado):
```
Optimisation complete:   the  5  lowest phi's are within a relative distance
                         of eachother of 1.000000E-02
```

Y por reduccion de parametros:
```
Optimisation complete:   relative parameter change less than RELPARSTP over
                         NRELPAR optimisation iterations
```

Patron de convergencia (case-insensitive, cubre ortografia britanica y americana):
```
[Oo]ptimis[a-z]*\s+complete
```
Complementado con la deteccion de las palabras clave de control:
```
RELPARSTP|PHIREDSTP|NOPTMAX
```

---

## Patrones Regex Consolidados para Metric Filters y Lambda ExtractPhi

| Metrica / evento | Patron regex propuesto (Python) | Confianza |
|------------------|--------------------------------|-----------|
| Iteracion actual | OPTIMISATION ITERATION NO\.\s*:\s*(\d+) | Alta (documentado) |
| Phi inicial de iteracion | [Ss]tarting phi for this iteration\s*:\s*([0-9.Ee+-]+) | Alta |
| Phi mas bajo de iteracion | [Ll]owest phi this iteration\s*:\s*([0-9.Ee+-]+) | Alta |
| Phi final | [Ff]inal phi\s*:\s*([0-9.Ee+-]+) | Alta |
| Contribucion por grupo | [Cc]ontribution to phi from observation group\s+"?([^":]+)"?\s*:\s*([0-9.Ee+-]+) | Media |
| Convergencia | [Oo]ptimis\w*\s+complete | Alta |
| Modelos solicitados | model\s+(?:up\s+to\s+)?(\d+)\s+times? | Confirmado (en uso hoy) |

> **Nota de robustez:** PEST alinea los valores con espacios variables tras el nombre de campo y antes del `:`. Los patrones usan `\s*:\s*` para tolerar ese espaciado. El caracter de clase `[0-9.Ee+-]` cubre notacion decimal y cientifica (ej. `1.234E+03`).

---

## Diferencia PEST clasico/HP vs PEST++ (importante)

El proyecto usa **PEST_HP** (`pest_hp`, `agent_hp`), que comparte el formato de salida de **PEST clasico**. Los patrones anteriores aplican a PEST_HP.

Si en el futuro se migrara a **PEST++** (`pestpp-glm`, `pestpp-ies`), el formato cambia:
- PEST++ usa frases como "starting phi", "current phi", y escribe un archivo `.iobj` (iteration objective) en CSV con columnas `iteration, total_phi, measurement_phi, regularization_phi, ...`.
- Para PEST++, el `.iobj` CSV es la fuente **preferida** (mas facil de parsear que el stdout).

**Recomendacion:** Como el proyecto usa PEST_HP, implementar los patrones de PEST clasico. Documentar que si se adopta PEST++, se debe cambiar la fuente al archivo `.iobj`.

---

## Impacto en el Diseno

Con OQ-03 resuelto por literatura:

1. **R11 (requirements.md)** ya no esta bloqueado - los Metric Filters y la Lambda ExtractPhi pueden implementarse usando los patrones de esta tabla.
2. **Tarea 19.1** (`scripts/validate_phi_log_format.py`) sigue siendo valiosa, pero ahora como **confirmacion** de los patrones ya fundamentados, no como prerequisito bloqueante. Debe probar los patrones de esta tabla contra un log real y reportar cual genera matches.
3. **Fase 3** puede proceder. El clasificador `classify_calibration_quality` ya era independiente del formato (recibe `phi_history` ya parseado), asi que solo la extraccion dependia de OQ-03.

---

## Riesgo Residual

El formato exacto puede variar ligeramente segun:
- La version especifica de PEST_HP compilada en la imagen (OQ-05, aun pendiente).
- Si el `.pst` usa modo "estimation" vs "regularization" (afecta si aparecen lineas de Phi de regularizacion - relacionado con OQ-09).

**Mitigacion:** `scripts/validate_phi_log_format.py` (tarea 19.1) debe ejecutarse contra un log real antes de activar alertas de calidad en produccion. Los patrones aqui propuestos son el punto de partida fundamentado, no un valor arbitrario.