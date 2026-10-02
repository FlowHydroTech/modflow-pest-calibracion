# Calibracion CMDIC Rajos

Proyecto de calibracion PEST del modelo hidrogeologico CMDIC Rajos (MODFLOW-USG).

## Que colocar en app/modelo/

Antes de construir la imagen, descomprimir el modelo (pest_ensi_v13) y copiar
TODO su contenido dentro de `app/modelo/`:

- Control PEST: `CMDIC_Rajos.pst` (el que ejecuta el master)
- Templates e instrucciones: `*.tpl`, `*.ins`
- Modelo MODFLOW-USG: `CMDIC_Rajos_SS.nam`, `.dis`, `.bas`, `.lpf`, `.ghb`, `.drn`, `.rch`, etc.
- Binarios Linux nativos: `pest_hp`, `agent_hp`, `mfusgt270`
- Utilidades Windows (via Wine): `plproc.exe`, `usgbud2smp1.exe`, `usgmod2smp.exe`, etc.
- Scripts de corrida: `model.sh` (lo invoca el .pst), `ensibatch.sh`
- Scripts Python de penalizacion: `ghb_penalty_SS.py`

El modelo NO se versiona en git (es ~4.5 GB). Ver `.gitignore`.

## Caracteristicas del modelo (para dimensionamiento)

- Parametros: 15.116 | Observaciones: 243 | NOPTMAX: 20
- Comando del modelo: `./model.sh` (usa Wine para plproc + utilidades PEST)
- Tamano: ~4.5 GB

## Como se usa

Ver la guia completa paso a paso en `docs/GUIA_PASO_A_PASO.md`.