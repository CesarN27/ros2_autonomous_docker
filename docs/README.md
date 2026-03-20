# Technical Documentation

This document describes the technical structure, deployment rationale, hardware configuration, ROS 2 nodes, and validation scope of the **ROS2-Based Autonomous Vehicle Prototype** repository.

The project is focused on the development of a **1:16 scale autonomous vehicle prototype** based on **ROS 2**, **Docker**, **Raspberry Pi 5**, and an initial **AI-assisted calibration workflow** for ultrasonic sensing. The repository serves as a development and validation platform for a multisensory embedded system intended to support future perception and autonomous decision-making stages.

---

## Contents
- [1. Environment Setup](#1-environment-setup)
- [2. Hardware Setup](#2-hardware-setup)
- [3. Wiring](#3-wiring)
- [4. ROS Nodes](#4-ros-nodes)
- [5. Calibration Pipeline](#5-calibration-pipeline)
- [6. Validation](#6-validation)
- [7. Known Limitations](#7-known-limitations)
- [8. Bill of Materials](#8-bill-of-materials)

---

## 1. Environment Setup

### 1.1 Purpose of the environment

This project uses a Docker-based environment to provide a reproducible development and execution space for **ROS 2 Humble** and the required Python dependencies on **Raspberry Pi 5**, without replacing the host operating system.

This decision was made to simplify:
- dependency installation,
- workspace portability,
- environment reproducibility,
- hardware-oriented testing on the target embedded platform.

### 1.2 Host requirements

Before running the project, make sure the following are available:

- Raspberry Pi 5: Operative System: Raspberry OS Debian GNU/Linux 13.3 (trixie), Kernel: 6.12.62+rpt-rpi2712
- Hardware connected and powered correctly
- Local clone of this repository
- Access to `/dev` and GPIO interfaces enabled through Docker runtime flags
- Docker installed and running

> **Note:** This repository is intended to run on a Raspberry Pi 5 with hardware access enabled. Features such as GPIO control, camera streaming, and sensor interfacing are hardware-dependent and may not work correctly on a standard desktop environment.

### 1.3 Clone the repository

```bash
git clone https://github.com/CesarN27/ros2_autonomous_docker.git
cd ros2_autonomous_docker
```

### 1.4 Build the Docker image

```bash
docker build -t ros2-autonomous-gpio -f Docker/Dockerfile .
```

### 1.5 Run the container

```bash
docker run -it --rm --privileged \
  --network host \
  -v $(pwd)/ros2_ws:/ros2_ws \
  -v $(pwd)/model_ai_calibration:/ros2_ws/src/sensor_ai \
  -v /dev:/dev \
  -v /run/udev:/run/udev:ro \
  ros2-autonomous-gpio
```

### 1.6 Build the ROS 2 workspace

```bash
cd /ros2_ws
rm -rf install build log
colcon build
source install/setup.bash
```

### Run executable nodes

Example:

```bash
ros2 run motor_controller teleop_motor
```

Other executables available in the package:

```bash
ros2 run motor_controller pruebarayo
ros2 run motor_controller rayows
```

### 1.8 Deployment rationale

Although ROS 2 is commonly debugged using multiple terminal sessions during development, this prototype was progressively consolidated into integrated runtime scripts to simplify deployment and reduce orchestration complexity on the embedded platform.

This was especially useful because the same system needs to coordinate:

- ROS 2 communication,
- GPIO motor actuation,
- ultrasonic safety logic,
- WebSocket-based remote commands,
- MJPEG video streaming,
- and future camera / perception extensions.

## 2. Hardware Setup

### 2.1 Embebbed platform

The prototype is built around a Raspberry Pi 5, used as the main embedded processing unit (ECU). In the context of this repository, the Raspberry Pi acts as the central node for:

- ROS 2 execution,
- motor control,
- GPIO interaction,
- sensor data acquisition,
- camera streaming,
- and integration with AI-based calibration components.

### 2.2 Main hardware components

The current repository and README describe the following hardware stack:

- Raspberry Pi 5 as the main ECU / embedded controller
- HC-SR04 ultrasonic sensor for frontal obstacle distance acquisition
- Pi Camera Module 3 for visual data acquisition and MJPEG streaming
- IFM O3D303 ToF sensor as a planned integration target
- H-bridge motor driver for traction and steering actuation
- DC motors for motion
- Voltage divider for safe ultrasonic echo integration to Raspberry Pi GPIO

### 2.3 Functional architecture

At a system level, the prototype is designed around the following flow:

1. Teleoperation (via movile application or via keybord conected directly on the ECU) or higher-level commands generate motion references.
2. ROS 2 nodes transform those references into low-level motor actions.
3. The ultrasonic subsystem monitors frontal distance.
4. If a static frontal condition is detected while the vehicle is moving forward, an emergency stop break is actived.
5. If a frontal condition in movement is detected while the vehicle is moving forward, an emergency manager of motors power supply is actived.
6. The motor controller reacts to /cmd_vel and /emergency_stop.
7. The video subsystem provides a live MJPEG stream for remote observation.
8. The AI calibration area supports data-driven improvement of ultrasonic distance estimation.

### 2.4 Operating modes

The repository currently reflects at least these operating modes:

- Manual keyboard teleoperation through ROS 2
- Safety-assisted operation using ultrasonic braking logic
- Mobile / WebSocket teleoperation in the rayows flow
- Calibration-oriented sensing experiments using CSV datasets and trained models

## 3. Wiring

### 3.1 General note

This section documents the GPIO mappings currently visible in the repository source code. Because the project contains more than one executable flow, the exact motor pin mapping differs between scripts.

For that reason, this section should be treated as a technical reference draft, and the final version should reflect the wiring that your team decides to keep as the canonical hardware configuration.

| Pin Raspberry |   GPIO   | Specification |  Module  | Function |
| ------------- | -------: | ------------- | -------- | -------- |
|       4       | 5V power |      Vcc      |  HC-SR04 |    Vcc   |
|       9       |  Ground  |     Ground    |  HC-SR04 |    Gnd   |
|       36      |  GPIO 16 |    GPIO 16    |  HC-SR04 |    Trig  |
|       38      |  GPIO 20 |    PCM_DIN    |  HC-SR04 |    Echo  |
|       40      |  GPIO 21 |    PCM_DOUT   |  HC-SR04 |    Gnd   |
|       12      |  GPIO 18 |    PCM_CLK    |   L298N  |    ENA   |
|       14      |  Ground  |     Ground    |   L298N  |    Gnd   |
|       16      |  GPIO 23 |    GPIO 23    |   L298N  |    IN1   |
|       18      |  GPIO 24 |    GPIO 24    |   L298N  |    IN2   |
|       29      |  GPIO 5  |    GPIO 5     |   L298N  |    IN3   |
|       31      |  GPIO 6  |    GPIO 6     |   L298N  |    IN4   |
|       33      |  GPIO 13 |     PWM1      |   L298N  |    ENB   |

**Wiring for H-Bridge L298N to base**:

| Function | Notes                     |
| -------- | ------------------------: |
| OUTPUT A | Front motors of cart base |
| OUTPUT B | Rear motors of cart base  |
| Vcc      | Cart base power supply    |
| Gnd      | Cart base ground          |


### 3.2 Voltage divider note

Because the HC-SR04 echo output can exceed safe logic levels for Raspberry Pi GPIO input, a voltage divider must be used between the sensor ECHO pin and the Raspberry Pi input pin.

Suggested asset reference: **"../assets/wiring.png"**

## 4. ROS Nodes

### 4.1 Main package

The main ROS 2 package in this repository is:

```bash
motor_controller
```

The package metadata and setup configuration expose the following executable nodes:

- teleop_motor
- pruebarayo
- rayows

### 4.2 Topic-level design

The control architecture revolves around two core topics:

| Topic             | Type                      | Purpose                    |
| ----------------- | ------------------------- | -------------------------- |
| `/cmd_vel`        | `geometry_msgs/msg/Twist` | Motion command input       |
| `/emergency_stop` | `std_msgs/msg/Bool`       | Safety brake / stop signal |


### 4.3 teleop_motor

**Purpose**

Basic ROS 2 teleoperation flow using keyboard input over terminal / SSH.

**Internal roles**

This executable combines:

- a publisher node that reads keyboard input,
- and a motor controller node that subscribes to /cmd_vel.

**Behavior**

- W / S controls forward and reverse motion
- A / D controls steering
- combined actions such as WA, WD, SA, SD are supported conceptually through the velocity command logic
- Q exits the program

**Main interfaces**

| Node role         | Publishes  | Subscribes |
| ----------------- | ---------- | ---------- |
| `TeleopPublisher` | `/cmd_vel` | —          |
| `MotorController` | —          | `/cmd_vel` |


**Recommended usage**

Use this executable for:

 - initial motor validation,
 - GPIO behavior checks,
 - simple manual motion tests,
 - SSH-based bench testing.

### 4.4 pruebarayo

**Purpose**

Integrated ROS 2 executable for:

- motion control,
- emergency stop handling,
- ultrasonic safety,
- and AI-assisted ultrasonic calibration during runtime.

**Internal roles**

This executable includes at least:

- MotorController
- TeleopPublisher
- SafetyUltrasonicNode

**Behavior**

- publishes motion commands to /cmd_vel
- monitors /cmd_vel to determine whether forward motion is active
- reads ultrasonic distance
- applies AI-based correction using model and scaler assets
- publishes /emergency_stop when obstacle distance falls below the configured danger threshold

**Current safety threshold**

```bash
DISTANCIA_PELIGRO = 15.0 cm
```

**Main interfaces**

| Node role              | Publishes         | Subscribes                    |
| ---------------------- | ----------------- | ----------------------------- |
| `TeleopPublisher`      | `/cmd_vel`        | `/emergency_stop`             |
| `MotorController`      | —                 | `/cmd_vel`, `/emergency_stop` |
| `SafetyUltrasonicNode` | `/emergency_stop` | `/cmd_vel`                    |

**AI integration**

This executable loads:

- modelo_calibracion_patched.h5
- scaler.pkl

These assets are used to improve raw ultrasonic distance estimation before making safety decisions.

**Recommended usage**

Use this executable for:

- safety logic validation,
- ultrasonic calibration experiments,
- emergency braking tests,
- combined sensing + control runs.

### 4.5 rayows

**Purpose**

Integrated runtime for:

- motor control,
- ultrasonic safety,
- WebSocket command input,
- and MJPEG video streaming.

**Internal roles**

The visible implementation includes:

- a motor control node subscribed to /cmd_vel and /emergency_stop
- an ultrasonic safety node that publishes /emergency_stop
- a WebSocket interface for external commands
- an MJPEG HTTP server for live camera streaming

**Current WebSocket configuration**

| Setting   |     Value |
| --------- | --------: |
| Host      | `0.0.0.0` |
| Port      |    `8765` |
| Move rate |   `20 Hz` |


**Current video configuration**

| Setting         |       Value |
| --------------- | ----------: |
| Stream endpoint |   `/stream` |
| HTTP port       |      `8080` |
| FPS             |        `15` |
| Resolution      | `640 x 480` |
| JPEG quality    |        `70` |


**Accepted WebSocket commands**

The implementation documents support for commands such as:

- {"command": "MOVE", "x": ..., "y": ...}
- {"command": "EMERGENCY_STOP"}
- {"command": "RESUME"}
- {"command": "STOP"}

**Main interfaces**

| Component             | Interface                       |
| --------------------- | ------------------------------- |
| Motion command bridge | `/cmd_vel`                      |
| Safety command        | `/emergency_stop`               |
| WebSocket server      | `ws://<robot-ip>:8765/`         |
| MJPEG stream          | `http://<robot-ip>:8080/stream` |


**Recommended usage**

Use this executable for:

- mobile / remote teleoperation,
- integrated motor + safety tests,
- live video observation,
- early UI-driven control experiments.

## 5. Calibration Pipeline

### 5.1 Objective

The calibration workflow is intended to improve ultrasonic measurement quality by collecting raw sensor data, generating datasets, training a model, and using the resulting model for corrected inference during runtime.

### 5.2 Repository calibration area

The repository organizes calibration-related work under:

```bash
model_ai_calibration/
├── proyecto_calibracion/
└── rayo_mc/
```

### 5.3 Dataset and experimentation flow

Based on the repository structure described in the main README, the calibration area includes:

- raw / processed CSV datasets,
- model training scripts,
- model testing scripts,
- real-time inference tests,
- exported trained models,
- and a scaler object for feature normalization.

### 5.4 Intended workflow

A practical interpretation of the current pipeline is:

1. Acquire raw ultrasonic sensor measurements.
2. Store data into CSV files for later analysis.
3. Build calibration datasets using controlled distance references.
4. Train a neural-network-based model for corrected distance estimation.
5. Export the trained model in .keras and .h5 formats.
6. Export the scaler used in preprocessing.
7. Load the model and scaler inside runtime safety nodes.
8. Use corrected distance estimates to improve emergency stop behavior.

### 5.5 Runtime AI usage in current scripts

The repository currently reflects two slightly different stages of AI integration:

- In pruebarayo.py, the ultrasonic safety flow actively uses model-based corrected distance for decision-making.
- In rayows.py, model and scaler paths are still declared for compatibility and future evolution, but the visible implementation notes that AI is not currently used inside the safety loop.

This distinction is important and should be documented clearly to avoid overstating the maturity of the AI runtime integration.

### 5.6 Data documentation

When you have time, add the following information here:

dataset acquisition conditions,
measurement range in centimeters,
number of samples,
sensor frequency target,
ambient conditions,
train/validation/test split,
features used by the model,
chosen loss function and optimizer,
inference latency on Raspberry Pi 5.

## 6. Validation

### 6.1 Current validation scope

The repository already reflects these validation areas:

- software and hardware connection validation,
- HC-SR04 raw distance acquisition tests,
- dataset generation,
- AI-based correction model training,
- initial real-time inference tests,
- teleoperation and motor actuation validation,
- calibration repeatability tests,
- distance correction validation against real measured values.

### 6.2 Validation philosophy

This project should be documented as an engineering prototype, not as a finished autonomous platform. For that reason, validation should be presented in progressive layers:

- electrical and GPIO validation,
- motor actuation validation,
- teleoperation validation,
- sensor acquisition validation,
- safety logic validation,
- AI-assisted correction validation,
- integrated runtime testing.

### 6.3 Validation table

Use the following table once your measurements are ready:

| Metric                       | Raw sensor | Calibrated / corrected | Notes                             |
| ---------------------------- | ---------: | ---------------------: | --------------------------------- |
| Mean Absolute Error (cm)     |     [TODO] |                 [TODO] | Compare against real distance     |
| Maximum Absolute Error (cm)  |     [TODO] |                 [TODO] | Worst-case error                  |
| Standard Deviation (cm)      |     [TODO] |                 [TODO] | Stability measure                 |
| Sampling Frequency (Hz)      |     [TODO] |                 [TODO] | Measured on Raspberry Pi 5        |
| Inference Latency (ms)       |          — |                 [TODO] | Runtime model latency             |
| Emergency Stop Distance (cm) |     [TODO] |                 [TODO] | Should align with threshold logic |


### 6.4 Functional test table

| Test                                           | Status | Notes |
| ---------------------------------------------- | ------ | ----- |
| Docker image builds successfully               | [TODO] |       |
| ROS 2 workspace builds successfully            | [TODO] |       |
| `teleop_motor` publishes `/cmd_vel`            | [TODO] |       |
| Motor controller reacts to `/cmd_vel`          | [TODO] |       |
| Ultrasonic distance can be read on hardware    | [TODO] |       |
| `/emergency_stop` is published below threshold | [TODO] |       |
| Vehicle brakes only during forward motion      | [TODO] |       |
| WebSocket control works in `rayows`            | [TODO] |       |
| MJPEG stream available on port 8080            | [TODO] |       |
| AI-corrected inference works in `pruebarayo`   | [TODO] |       |

### 6.5 Recommended evidence to attach

For stronger portfolio value, include:

one photo of the assembled prototype,

one screenshot of terminal output during ROS execution,

one screenshot of the MJPEG stream,

one graph of raw vs corrected distance,

one short GIF or video of motion + safety stopping behavior.

## 7. Known Limitations

### 7.1 Hardware dependence

This repository depends on access to:

- Raspberry Pi GPIO,
- connected actuators,
- sensor hardware,
- and camera interfaces.

As a result, full functionality is not reproducible on a generic desktop-only environment.

### 7.2 Partial multisensor integration

The project vision includes a multisensory platform, but current validation is still concentrated mainly on:

- motor control,
- teleoperation,
- ultrasonic sensing,
- and ultrasonic calibration.

Camera and ToF integration are still under development.

### 7.3 Incomplete sensor fusion stage

The system architecture anticipates a future fusion stage, but full multisensor fusion is not yet implemented.

### 7.4 Runtime architecture still evolving

The repository contains multiple executable flows for different testing stages:

- keyboard teleoperation,
- AI-assisted ultrasonic safety,
- WebSocket + MJPEG operation.

This is useful during development, but it also means some configuration details such as pin mapping and integration scope still need to be consolidated into a final reference implementation.

### 7.5 Documentation and metrics still in progress

Some sections of the project are already structurally defined in the README, but still need final engineering evidence, including:

- quantitative error metrics,
- stable final wiring diagram,
- consolidated benchmark results,
- and clearer mode-by-mode execution notes.


## 8. Bill of Materials

> Note: Costs should be updated according to your actual purchases or local supplier quotes.

| Item                            |  Quantity | Purpose                              | Approx. Cost | Notes                       |
| ------------------------------- | --------: | ------------------------------------ | -----------: | --------------------------- |
| Raspberry Pi 5                  |         1 | Main embedded controller             |       [TODO] | Main execution platform     |
| MicroSD / storage               |         1 | OS and project storage               |       [TODO] |                             |
| Power supply for Raspberry Pi 5 |         1 | Stable power input                   |       [TODO] |                             |
| HC-SR04 ultrasonic sensor       |         1 | Distance acquisition                 |       [TODO] |                             |
| Pi Camera Module 3              |         1 | Vision streaming / future perception |       [TODO] |                             |
| IFM O3D303 ToF sensor           |         1 | Planned depth sensing                |       [TODO] | Optional / future stage     |
| H-bridge motor driver           |         1 | Motor actuation interface            |       [TODO] |                             |
| DC traction motor               |         1 | Forward / reverse motion             |       [TODO] |                             |
| DC steering motor               |         1 | Steering actuation                   |       [TODO] |                             |
| Voltage divider resistors       |         2 | Safe Echo level adaptation           |       [TODO] |                             |
| Wiring / jumpers / connectors   |  assorted | Electrical integration               |       [TODO] |                             |
| Chassis / 1:16 vehicle platform |         1 | Physical prototype base              |       [TODO] | Porsche 911 GT3 RS platform |
| Ethernet / network accessories  | as needed | Remote setup / connectivity          |       [TODO] |                             |
| Battery / onboard power stage   |    [TODO] | Vehicle-side power                   |       [TODO] | Update with final design    |
