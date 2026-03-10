<p align="center">
  <img src="assets/banner.png" alt="Project banner" width="100%">
</p>

<h1 align="center">ROS2 Autonomous Docker</h1>

<p align="center">
  Autonomous robotics and embedded experimentation with ROS 2, motor control, and AI-based sensor calibration.
</p>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#repository-structure">Repository Structure</a> •
  <a href="#main-components">Main Components</a> •
  <a href="#getting-started">Getting Started</a> •
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## Overview

This repository contains the development environment, ROS 2 workspace, and calibration-related components for an autonomous robotics project.

The project integrates:

- ROS 2 nodes for motor control and communication
- Docker-based environment setup
- AI-based calibration experiments for ultrasonic sensor data
- Supporting scripts, datasets, and testing utilities

## Repository Structure

```text
.
├── model_ai_calibration/
├── ros2_ws/
│   └── ros2_ws/
│       └── src/
│           └── motor_controller/
├── assets/
├── README.md
└── CONTRIBUTING.md
