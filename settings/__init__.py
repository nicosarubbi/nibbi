from os import getenv
from .base import *

ENV = getenv('ENVIRONMENT', 'development')


if ENV == 'SANDBOX':
    from .sandbox import *
elif ENV == 'DEV':
    from .development import *
