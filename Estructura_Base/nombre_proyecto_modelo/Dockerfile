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

WORKDIR /app/USGT_V_2-7-0_Source_Code

RUN apt-get install -y gfortran make

RUN sed -i 's/ -fno-automatic//g' build_usgt_linux.sh Makefile.usgt-linux

RUN chmod +x  /app/USGT_V_2-7-0_Source_Code/build_usgt_linux.sh

RUN ./build_usgt_linux.sh

RUN cp /app/USGT_V_2-7-0_Source_Code/bin/mfusgt270 /app/modelo/mfusgt270

WORKDIR /app

RUN chmod +x  /app/*.sh /app/modelo/*.sh /app/modelo/pest /app/modelo/pest_hp /app/modelo/agent_hp /app/modelo/mfusgt270

#CMD ["/bin/bash" "/app/entrypoint.sh"]   