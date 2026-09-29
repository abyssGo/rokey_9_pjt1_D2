from setuptools import find_packages, setup

package_name = 'cobot_api'

setup(
    name=package_name,
    version='3.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Team D2',
    maintainer_email='hwang-injae@users.noreply.github.com',
    description='PreWash-Cell 기능 함수 약속(ID·코드·반환 타입·함수 서명)',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={'console_scripts': []},
)
