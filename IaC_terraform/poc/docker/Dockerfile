# Imagen dummy para la POC: valida el circuito end-to-end SIN Wine.
# Simula pest_hp/agent_hp con un script que emite logs en el formato real de
# PEST_HP (iteraciones, Phi decreciente, convergencia).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 curl unzip ca-certificates iputils-ping && \
    curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip && \
    unzip -q awscliv2.zip && ./aws/install && rm -rf awscliv2.zip aws && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/ /app/
RUN chmod +x /app/*.sh /app/pest_hp /app/agent_hp

# El comando lo define el Job Definition (entrypoint_master.sh / entrypoint_agent.sh)