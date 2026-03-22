from setuptools import setup

package_name = "motor_controller"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Moises_Aguillon_Cesar_Nuñes_Alejandro_Estrada",
    maintainer_email="maguillon21@alumnos.uaq.mx",
    description="ROS 2 package for teleoperation and motor control of a 1:14 autonomous vehicle prototype.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "teleop_motor = motor_controller.teleop_motor_node:main",
            "pruebarayo = motor_controller.pruebarayo:main",
            "rayows = motor_controller.rayows:main"
        ],
    },
)