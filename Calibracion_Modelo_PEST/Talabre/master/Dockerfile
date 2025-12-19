FROM ubuntu:20.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary packages
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-dev && \
    apt-get install -y git iputils-ping && \
    apt-get install -y --fix-missing && \
    apt-get install -y wget unzip
# Add i386 architecture for Wine compatibility
RUN dpkg --add-architecture i386
RUN apt-get update && apt-get install -y wine wine32 wine64 libwine libwine:i386 fonts-wine
RUN apt-get install -y unzip curl && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && ./aws/install
RUN apt-get clean

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the source code
COPY app/ .

# Command to run the application
#CMD ["/bin/bash", "/app/entrypoint.sh"]