# =======================================================================
# Imagen de calibracion PEST - Modelo CMDIC Rajos
# Ubuntu 24.04 LTS + Wine (requerido por las utilidades de post-proceso de
# PEST: plproc.exe, usgbud2smp1.exe, usgmod2smp.exe) + Python3 + AWS CLI.
# MODFLOW-USG (mfusgt270), pest_hp y agent_hp son binarios Linux nativos.
#
# El modelo (archivos .pst/.tpl/.ins/MODFLOW/binarios, ~4.5 GB) se coloca en
# app/modelo/ ANTES de construir. No se versiona en git (ver .gitignore).
# =======================================================================
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV WINEARCH=win64
ENV WINEPREFIX=/root/.wine
ENV DISPLAY=:0

# Dependencias base + Wine 64-bit + Xvfb (display virtual para Wine headless)
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip \
        wine wine64 wine32:i386 \
        xvfb \
        iputils-ping \
        curl unzip ca-certificates \
        libgfortran5 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Inicializar Wine (headless con Xvfb) - critico para que plproc.exe arranque
RUN mkdir -p /root/.wine && \
    xvfb-run -a -s "-screen 0 1024x768x24" wineboot -i && sleep 2 && \
    xvfb-run -a -s "-screen 0 1024x768x24" wineboot -e && \
    [ -f /root/.wine/system.reg ] || { echo "ERROR: Wine init fallo"; exit 1; }

# AWS CLI v2 (para subir resultados a S3)
RUN curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip && \
    unzip -q awscliv2.zip && ./aws/install && rm -rf awscliv2.zip aws

WORKDIR /app

# requirements del modelo (p.ej. pandas para los scripts de penalizacion)
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Entrypoints (master / agente / autonomo)
COPY app/entrypoint_master.sh app/entrypoint_agent.sh app/entrypoint_autonomo.sh /app/

# El modelo completo (binarios + datos). Debe existir antes del build.
COPY app/modelo/ /app/modelo/

# Permisos de ejecucion para los binarios Linux y scripts del modelo
RUN chmod +x /app/*.sh && \
    chmod +x /app/modelo/pest_hp /app/modelo/agent_hp /app/modelo/mfusgt270 /app/modelo/pest 2>/dev/null || true && \
    find /app/modelo -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true