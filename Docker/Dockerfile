# ================================
# Base oficial de ROS 2 Humble (Jammy)
# ================================
FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# ================================
# 1. Paquetes Base del Sistema y Dependencias UI/DRM
# Agrupado para crear una sola capa y reducir el tamaño de la imagen
# ================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git wget curl pkg-config lsb-release \
    ca-certificates software-properties-common nano \
    libjpeg-dev libpng-dev libtiff-dev libopenexr-dev libgtk-3-dev \
    libusb-1.0-0-dev v4l-utils libv4l-dev libomp-dev libgpiod-dev \
    libopencv-dev libgnutls28-dev openssl libudev-dev libgtest-dev \
    qtbase5-dev libqt5core5a libqt5gui5 libqt5widgets5 qttools5-dev-tools \
    libtiff5-dev libevent-dev libdrm-dev libcap-dev libfmt-dev \
    libatlas-base-dev \
    python3-pip python3-dev python3-numpy python3-libgpiod python3-rpi.gpio \
    python3-colcon-common-extensions python3-rosdep python3-vcstool \
    python3-jinja2 python3-ply python3-yaml \
    && rm -rf /var/lib/apt/lists/*

# ================================
# 2. Dependencias comunes de ROS 2
# ================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-vision-opencv \
    ros-humble-rclcpp \
    ros-humble-rclpy \
    ros-humble-sensor-msgs \
    ros-humble-geometry-msgs \
    ros-humble-nav-msgs \
    && rm -rf /var/lib/apt/lists/*

# ================================
# 3. Motores modernos de compilación Python
# ================================
RUN apt-get update && apt-get remove -y meson || true && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install --no-cache-dir --upgrade pip meson ninja pybind11 && \
    pip3 install --no-cache-dir --prefer-binary python-prctl

# ================================
# 4. Stack de Machine Learning y GPIO (Python)
# ================================
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio opencv-python numpy scipy matplotlib \
    ultralytics tensorflow joblib RPi.GPIO pigpio

# ================================
# 5. scikit-learn y dependencias ancladas
# ================================
RUN pip3 install --no-cache-dir --prefer-binary \
    "scikit-learn==1.7.2" \
    "threadpoolctl==3.6.0" \
    "joblib==1.5.3"

# ================================
# 6. Compilar libcamera nativo
# (Se elimina el código fuente tras la instalación para ahorrar espacio)
# ================================
WORKDIR /opt
RUN git clone https://github.com/raspberrypi/libcamera.git && \
    cd libcamera && \
    /usr/local/bin/meson setup build -Dpipelines=rpi/vc4,rpi/pisp -Dprefix=/usr && \
    /usr/local/bin/ninja -C build install && \
    ldconfig && \
    cd /opt && rm -rf libcamera

# ================================
# 7. Instalar Picamera2
# (Se elimina el código fuente tras la instalación)
# ================================
WORKDIR /opt
RUN git clone --depth 1 https://github.com/raspberrypi/picamera2.git && \
    cd picamera2 && \
    pip3 install --no-cache-dir . && \
    cd /opt && rm -rf picamera2

# ================================
# 8. Parche para evadir error KMS
# ================================
RUN python3 -c 'import os, site; paths = site.getsitepackages(); target = next((p for p in paths if "dist-packages" in p or "site-packages" in p), None); \
    raise RuntimeError("No se encontro ruta de site-packages/dist-packages") if target is None else None; \
    file_path = os.path.join(target, "kms.py"); \
    f = open(file_path, "w", encoding="utf-8"); \
    f.write("from unittest.mock import MagicMock\nimport sys\nsys.modules[__name__] = MagicMock()\n"); \
    f.close(); \
    print(f"Parche kms.py escrito en: {file_path}")'

# ================================
# 9. IFM3D SDK
# (Se elimina el código fuente tras la instalación)
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
    ldconfig && \
    cd /opt && rm -rf ifm3d

# ================================
# 10. Workspace ROS y Configuración
# ================================
WORKDIR /ros2_ws
RUN mkdir -p src

# Inicializar rosdep (opcional, pero recomendable)
RUN rosdep init || true && rosdep update || true

# ================================
# Entrypoint
# ================================
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]