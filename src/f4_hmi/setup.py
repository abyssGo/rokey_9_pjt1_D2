from glob import glob

from setuptools import find_packages, setup

package_name = 'f4_hmi'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    package_data={package_name: ['static/*']},
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/scenarios', glob('scenarios/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='황인재',
    maintainer_email='hwang-injae@users.noreply.github.com',
    description='F4 시스템 모니터(웹 HMI) — hmi_bridge · fake_state_pub',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={'console_scripts': [
        'hmi_bridge = f4_hmi.hmi_bridge:main',
        'fake_state_pub = f4_hmi.fake_state_pub:main',
        'hmi_db = f4_hmi.dbtool:main',
    ]},
)
