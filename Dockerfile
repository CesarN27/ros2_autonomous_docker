# ================================
# Base: ROS 2 Humble en Ubuntu 22.04 (ARM64 compatible)
# ================================
FROM arm64v8/ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# ================================
# Paquetes base del sistema
# ================================
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    pkg-config \
    lsb-release \
    ca-certificates \
    software-properties-common \
    python3-pip \
    python3-dev \
    python3-numpy \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libopenexr-dev \
    libgtk-3-dev \
    libusb-1.0-0-dev \
    v4l-utils \
    libv4l-dev \
    libomp-dev \
    nano \
    && rm -rf /var/lib/apt/lists/*

# ================================
# ROS dependencies comunes
# ================================
RUN apt-get update && apt-get install -y \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-vision-opencv \
    ros-humble-rclcpp \
    ros-humble-sensor-msgs \
    ros-humble-geometry-msgs \
    ros-humble-nav-msgs \
    && rm -rf /var/lib/apt/lists/*

# ================================
# OpenCV (usa el del sistema)
# ================================
RUN apt-get update && apt-get install -y \
    libopencv-dev \
    && rm -rf /var/lib/apt/lists/*

# ================================
# Python ML stack (YOLO)
# ================================
RUN pip3 install --no-cache-dir \
    torch \
    torchvision \
    torchaudio \
    opencv-python \
    numpy \
    scipy \
    matplotlib \
    ultralytics

# ================================
# libgpiod (GPIO moderno)
# ================================
RUN apt-get update && apt-get install -y \
    gpiod \
    python3-libgpiod \
    && rm -rf /var/lib/apt/lists/*

# ================================
# GPIO Raspberry Pi (CRÍTICO)
# ================================
# RPi.GPIO desde apt (sí existe)
RUN apt-get update && apt-get install -y \
    python3-rpi.gpio \
    && rm -rf /var/lib/apt/lists/*

# pigpio SOLO por pip (NO por apt)
RUN pip3 install --no-cache-dir \
    RPi.GPIO \
    pigpio

# ================================
# IFM3D SDK (desde source, ARM)
# ================================
WORKDIR /opt
RUN git clone https://github.com/ifm/ifm3d.git && \
    cd ifm3d && \
    mkdir build && cd build && \
    cmake .. \
      -DBUILD_MODULE_FRAMEGRABBER=ON \
      -DBUILD_MODULE_IMAGE=ON \
      -DBUILD_MODULE_TOOLS=ON \
      -DBUILD_SHARED_LIBS=ON && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# ================================
# Workspace ROS
# ================================
WORKDIR /ros2_ws
RUN mkdir -p src

# ================================
# Entrypoint
# ================================
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
