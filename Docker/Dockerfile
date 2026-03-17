# ================================
# Base oficial de ROS 2 Humble
# ================================
FROM ros:humble-ros-base-jammy

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
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
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
    libgpiod-dev \
    python3-libgpiod \
    && rm -rf /var/lib/apt/lists/*

# ================================
# ROS dependencies comunes
# ================================
RUN apt-get update && apt-get install -y \
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
# OpenCV del sistema
# ================================
RUN apt-get update && apt-get install -y \
    libopencv-dev \
    && rm -rf /var/lib/apt/lists/*

# ================================
# Dependencias extra para libcamera / picamera2 / DRM
# ================================
RUN apt-get update && apt-get install -y \
    python3-jinja2 \
    python3-ply \
    python3-yaml \
    libgnutls28-dev \
    openssl \
    libudev-dev \
    libgtest-dev \
    qtbase5-dev \
    libqt5core5a \
    libqt5gui5 \
    libqt5widgets5 \
    qttools5-dev-tools \
    libtiff5-dev \
    libevent-dev \
    libdrm-dev \
    libcap-dev \
    libfmt-dev \
    libatlas-base-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ================================
# Motores modernos de compilacion Python
# ================================
RUN apt-get update && apt-get remove -y meson || true && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --upgrade \
    meson \
    ninja \
    pybind11

RUN pip3 install --no-cache-dir --prefer-binary \
    python-prctl

# ================================
# Python ML stack
# ================================
RUN pip3 install --no-cache-dir \
    torch \
    torchvision \
    torchaudio \
    opencv-python \
    numpy \
    scipy \
    matplotlib \
    ultralytics \
    tensorflow \
    joblib

# ================================
# scikit-learn y dependencias
# ================================
RUN pip3 install --no-cache-dir --prefer-binary \
    "scikit-learn==1.7.2" \
    "threadpoolctl==3.6.0" \
    "joblib==1.5.3"

# ================================
# GPIO Raspberry Pi
# ================================
RUN apt-get update && apt-get install -y \
    python3-rpi.gpio \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
    RPi.GPIO \
    pigpio

# ================================
# Compilar libcamera nativo
# ================================
WORKDIR /opt
RUN rm -rf libcamera && \
    git clone https://github.com/raspberrypi/libcamera.git && \
    cd libcamera && \
    /usr/local/bin/meson setup build -Dpipelines=rpi/vc4,rpi/pisp -Dprefix=/usr && \
    /usr/local/bin/ninja -C build install && \
    ldconfig

# ================================
# Instalar Picamera2
# ================================
WORKDIR /opt
RUN rm -rf picamera2 && \
    git clone --depth 1 https://github.com/raspberrypi/picamera2.git && \
    cd picamera2 && \
    pip3 install --no-cache-dir .

# ================================
# Parche para kms.py
# ================================
RUN python3 - <<'PY' \
import os, site; \
paths = site.getsitepackages(); \
target = None; \
for p in paths: \
    if "dist-packages" in p or "site-packages" in p: \
        target = p; \
        break; \
if target is None: \
    raise RuntimeError("No se encontro ruta de site-packages/dist-packages") \
file_path = os.path.join(target, "kms.py"); \
with open(file_path, "w", encoding="utf-8") as f: \
    f.write("from unittest.mock import MagicMock\\nimport sys\\nsys.modules[__name__] = MagicMock()\\n") \
print(f"Parche kms.py escrito en: {file_path}") \
PY

# ================================
# IFM3D SDK
# ================================
WORKDIR /opt
RUN rm -rf ifm3d && \
    git clone https://github.com/ifm/ifm3d.git && \
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
# Inicializar rosdep (opcional, pero recomendable)
# ================================
RUN rosdep init || true
RUN rosdep update || true

# ================================
# Entrypoint
# ================================
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]