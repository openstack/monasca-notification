#!/usr/bin/env python

# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import setuptools

setuptools.setup(
    name="monasca-notification",
    version="1.0.1",
    author="Tim Kuhlman",
    author_email="tim.kuhlman@hp.com",
    description="Notification engine used in the monasca monitoring system",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: System :: Monitoring"
    ],
    license="Apache",
    keywords="openstack monitoring email",
    url="https://github.com/stackforge/monasca-notification",
    # possibly preferable to have the OS precompiled mysql version, python-mysqldb package on Ubuntu
    install_requires=["kafka-python>=0.9.0", "kazoo>=1.3", "MySQL-python", "python-statsd>=1.6.3", "PyYAML"],
    packages=setuptools.find_packages(exclude=['tests']),
    entry_points={
        'console_scripts': [
            'monasca-notification = monasca_notification.main:main'
        ],
    },
    scripts=['tools/monasca_notification_offsets.py'],
    test_suite='nose.collector'
)
