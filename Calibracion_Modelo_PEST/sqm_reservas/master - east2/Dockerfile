FROM ubuntu:20.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV WINEARCH=win64
ENV WINEPREFIX=/root/.wine
ENV DISPLAY=:0

RUN apt-get update &&   \
    apt-get install -y python3 python3-pip python3-dev &&   \
    apt-get install -y git iputils-ping &&   \
    apt-get install -y --fix-missing &&  \
    apt-get install -y wget unzip 

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

RUN echo '#!/bin/bash\nexec python3 "$@"' > /usr/local/bin/python311   \
    && chmod +x /usr/local/bin/python311 

RUN mkdir -p /root/.wine/drive_c/python311   \
    && ln -s /usr/local/bin/python311 /root/.wine/drive_c/python311/python.exe

RUN pip3 install --no-cache-dir -r requirements.txt

COPY app/ .

#CMD ["/bin/bash" "/app/entrypoint.sh"]   