from codecs import open
from os import path

from setuptools import setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='aws_list_all',
    version='0.8.0',
    description='List all your AWS resources, all regions, all services.',
    long_description=long_description,
    url='https://github.com/JohannesEbke/aws_list_all',
    author='Johannes Ebke',
    author_email='johannes@ebke.org',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='aws boto3 listings resources region services',
    packages=['aws_list_all'],
    install_requires=['boto3>=1.16.24', 'app_json_file_cache>=0.2.2'],
    entry_points={
        'console_scripts': [
            'aws_list_all=aws_list_all.__main__:main',
            'aws-list-all=aws_list_all.__main__:main',
        ],
    },
    include_package_data=True,
)
