# Stage 1: Obtener glibc 2.43+ desde Ubuntu 26.04
FROM ubuntu:26.04 AS glibc_source

# Stage 2: Build principal en Ubuntu 25.04
FROM ubuntu:25.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV WINEARCH=win64
ENV WINEPREFIX=/root/.wine
ENV DISPLAY=:0

RUN apt-get update &&   \
    apt-get install -y python3 python3-pip python3-dev &&   \
    apt-get install -y git iputils-ping &&   \
    apt-get install -y --fix-missing &&  \
    apt-get install -y wget unzip libgfortran5

RUN dpkg --add-architecture i386

# Install Wine with all dependencies
RUN apt-get update && apt-get install -y \
    wine \
    wine32 \
    wine64 \
    libwine \
    libwine:i386 \
    fonts-wine \
    winetricks \
    fonts-dejavu \
    fonts-liberation \
    xvfb \
    unzip \
    wget \
    curl \
    cron

# Initialize Wine - CRITICAL for ECS Fargate
# Use xvfb-run to provide a virtual X display for wineboot
RUN mkdir -p /root/.wine && \
    xvfb-run -a -s "-screen 0 1024x768x24" wineboot -i && \
    sleep 2 && \
    xvfb-run -a -s "-screen 0 1024x768x24" wineboot -e && \
    # Verify initialization was successful
    [ -f /root/.wine/system.reg ] || { echo "ERROR: Wine initialization failed"; exit 1; }
# Install AWS CLI v2
RUN apt-get install -y curl && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && ./aws/install && \
    rm -rf awscliv2.zip aws/ && apt-get clean

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY app/ .

RUN chmod +x  /app/*.sh /app/modelo/*.sh /app/modelo/pest /app/modelo/pest_hp /app/modelo/agent_hp /app/modelo/mfusgt270

# Copiar glibc 2.43 desde Ubuntu 26.04 y parchear mfusgt270
RUN apt-get install -y patchelf
COPY --from=glibc_source /lib/x86_64-linux-gnu/libc.so.6 /opt/glibc-new/
COPY --from=glibc_source /lib/x86_64-linux-gnu/libm.so.6 /opt/glibc-new/
COPY --from=glibc_source /lib/x86_64-linux-gnu/libgcc_s.so.1 /opt/glibc-new/
COPY --from=glibc_source /lib64/ld-linux-x86-64.so.2 /opt/glibc-new/
RUN patchelf --set-interpreter /opt/glibc-new/ld-linux-x86-64.so.2 \
             --set-rpath /opt/glibc-new \
             /app/modelo/mfusgt270

#CMD ["/bin/bash" "/app/entrypoint.sh"]   