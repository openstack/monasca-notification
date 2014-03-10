from setuptools import setup, find_packages

setup(
    name="Monitoring Notification Engine",
    version="0.1",
    packages=find_packages(exclude=['tests']),
    entry_points={
        'console_scripts': [
            'notification_engine = main'
        ],
    },
    test_suite='nose.collector', requires=['kafka', 'kazoo']
)
