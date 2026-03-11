from setuptools import setup

package_name = 'motor_controller'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='watergrid',
    description='Motor controller ROS2 node',
    entry_points={
        'console_scripts': [
            'control_test = motor_controller.control_test:main',
            'hola_publisher = motor_controller.hola_publisher:main',
            'hola_subscriber = motor_controller.hola_subscriber:main',
            'teleop_motor = motor_controller.teleop_motor_node:main',
            'pruebarayo = motor_controller.pruebarayo:main',
        ],
    },
)
