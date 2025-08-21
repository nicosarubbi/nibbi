from setuptools import setup

setup(
    name='common',
    version='0.1.0',
    packages=('common',),

    install_requires=[
        'boto3==1.40',
        'pydantic==2.11',
        'pydantic-settings==2.11'
    ],
    extras_require={
        'all': [
            'setuptools',
            'wheel',
            'aws-cdk-lib==2.212.0',
            'constructs>=10.0.0,<11.0.0',
            'pytest==8.4.1',
            'parameterized==0.9.0',
            'moto==5.1',
        ],
    },
)
