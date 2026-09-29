from setuptools import find_packages, setup

package_name = 'f3_wipe'

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
    description='F3 접촉 닦기 함수 모듈(soap · wipe_bowl · wipe_cup)',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={'console_scripts': []},
)
