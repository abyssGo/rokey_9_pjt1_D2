from setuptools import find_packages, setup

package_name = 'f2_sense_flow'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Team Prewash',
    maintainer_email='hwang-injae@users.noreply.github.com',
    description='PreWash-Cell F2 무게·털기·헹굼 + flow_node',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'flow_node = f2_sense_flow.flow_node:main',
        ],
    },
)
