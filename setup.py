from setuptools import setup, find_packages

setup(
    name="mon-notification",
    version="0.1",
    packages=find_packages(exclude=['tests']),
    entry_points={
        'console_scripts': [
            'mon-notification = mon_notification.main:main'
        ],
    }
)
