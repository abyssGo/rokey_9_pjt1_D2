from setuptools import find_packages, setup

package_name = 'f1_handling'

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
    maintainer='Team D2',
    maintainer_email='hwang-injae@users.noreply.github.com',
    description='F1 파지·이송·적재 함수 모듈(pick · place · move_to · tool · rack_place)',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={'console_scripts': []},
)
