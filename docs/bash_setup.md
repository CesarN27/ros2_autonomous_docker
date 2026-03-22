# Bash Setup Guide

This document describes the custom Bash shell configuration used to simplify development and execution of the project on the target Raspberry Pi environment.

## Purpose

The project uses a customized Bash setup to make the local workflow faster, more consistent, and easier to reproduce during development and testing.

The main goals of this configuration are:

- initialize the local Python environment with `pyenv`
- load user-local environment variables when available
- provide a shortcut command to start the Dockerized ROS 2 environment used by the project

## Scope

The full `~/.bashrc` file on the Raspberry Pi contains many default Bash settings provided by the operating system, such as:

- shell history configuration
- prompt styling and colors
- terminal title formatting
- default aliases for `ls` and `grep`
- Bash completion support

These sections are not specific to this repository.

This guide documents only the **project-specific customization block** added to the end of the shell configuration file.

## Project-Specific Bash Configuration

```bash
. "$HOME/.local/bin/env"
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"
eval "$(pyenv virtualenv-init -)"

alias ros2='docker run -it --rm --privileged \
--network host \
-v ~/ros2_ws:/ros2_ws \
-v "$HOME/pruebas/rayo_mc:/ros2_ws/src/sensor_ai" \
-v /dev:/dev \
-v /run/udev:/run/udev:ro \
ros2-autonomous-gpio'
```

## Configuration Breakdown

### 1. Load local user environment

```bash
. "$HOME/.local/bin/env"
```

This line loads additional user-local environment configuration if that file exists and has been created by the local system setup.

It is useful when the local shell environment depends on user-installed tools or paths managed outside the default system configuration.

### 2. Initialize `pyenv`

```bash
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"
eval "$(pyenv virtualenv-init -)"
```

These lines configure `pyenv` and `pyenv-virtualenv`, allowing Python versions and Python environments to be managed consistently in each shell session.

This is helpful for calibration scripts, training scripts, testing utilities, or other Python-based tooling used during experimentation.

### 3. Define a Docker shortcut for the project runtime

```bash
alias ros2='docker run -it --rm --privileged \
--network host \
-v ~/ros2_ws:/ros2_ws \
-v "$HOME/pruebas/rayo_mc:/ros2_ws/src/sensor_ai" \
-v /dev:/dev \
-v /run/udev:/run/udev:ro \
ros2-autonomous-gpio'
```

This alias defines a shortcut command that launches the project's Docker container with the required hardware access, mounted volumes, and host networking.

Its purpose is to simplify repeated startup of the ROS 2 development and runtime environment on the Raspberry Pi.

## Docker Alias Details

The alias launches the container with the following behavior:

- `-it`: starts an interactive terminal session
- `--rm`: automatically removes the container when it exits
- `--privileged`: grants extended hardware/device access required by the project
- `--network host`: shares the host network for ROS 2 communication and remote interfaces
- `-v ~/ros2_ws:/ros2_ws`: mounts the local ROS 2 workspace into the container
- `-v "$HOME/pruebas/rayo_mc:/ros2_ws/src/sensor_ai"`: mounts the calibration/model directory into the container
- `-v /dev:/dev`: gives the container access to device files
- `-v /run/udev:/run/udev:ro`: exposes udev information in read-only mode
- `ros2-autonomous-gpio`: Docker image used by the project

## Important Note About the Alias

Although the alias is named `ros2`, it does not invoke the native ROS 2 CLI installed on the host system.

Instead, it starts the project's Docker container.

For that reason, the alias should be understood as a project runtime shortcut, not as a replacement for the standard `ros2` command in a regular ROS 2 installation.

## Requirements

Before using this configuration, make sure the following are available:

- Docker is installed and running
- the Docker image `ros2-autonomous-gpio` has already been built
- the local workspace exists at `~/ros2_ws`
- the calibration/model directory exists at `$HOME/pruebas/rayo_mc`
- `pyenv` and `pyenv-virtualenv` are installed if Python environment management is needed

## How to Apply the Configuration

Open the Bash configuration file:

```bash
nano ~/.bashrc
```

Add the project-specific block at the end of the file.

Then reload the shell configuration:

```bash
source ~/.bashrc
```

## Example Usage

After reloading the shell, run:

```bash
ros2
```

This will start the Dockerized project environment using the predefined runtime configuration.

## Reference Snippet

The following is the exact project-specific block currently used in the development shell configuration:

```bash
. "$HOME/.local/bin/env"
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"
eval "$(pyenv virtualenv-init -)"

alias ros2='docker run -it --rm --privileged \
--network host \
-v ~/ros2_ws:/ros2_ws \
-v "$HOME/pruebas/rayo_mc:/ros2_ws/src/sensor_ai" \
-v /dev:/dev \
-v /run/udev:/run/udev:ro \
ros2-autonomous-gpio'
```

## Recommended Future Improvement

For clarity, a future revision could rename the alias from `ros2` to something more explicit, such as:

- `rayo_ros2`
- `ros2_docker`
- `rayo_env`

This would reduce confusion with the standard ROS 2 command-line interface.