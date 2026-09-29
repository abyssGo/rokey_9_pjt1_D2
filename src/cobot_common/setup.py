from glob import glob

from setuptools import find_packages, setup

package_name = 'cobot_common'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Team Prewash',
    maintainer_email='hwang-injae@users.noreply.github.com',
    description='PreWash-Cell 공용 로봇 함수 모음(두산 API 초기화 · 설정 로더 · 이동 · 힘 · 무게)',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={'console_scripts': []},
)
