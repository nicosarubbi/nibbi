from os import getenv
from .default import *

ENV = getenv('ENVIRONMENT', 'DEV')


if ENV == 'SANDBOX':
    from .sandbox import *
elif ENV == 'DEV':
    from .development import *
