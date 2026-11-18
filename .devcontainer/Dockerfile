# Use official Python 3.12 slim image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /workspaces/internet_health_monitor

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    make \
    wget \
    iputils-ping \
    traceroute \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install basic dev tools only
RUN pip install --upgrade pip setuptools wheel

# Set default Python path for tooling
ENV PYTHONPATH=/workspaces/internet_health_monitor
