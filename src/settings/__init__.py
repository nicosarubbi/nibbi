from os import getenv
from src.settings.base import *

ENV = getenv('ENVIRONMENT', 'development')


if ENV == 'SANDBOX':
    from src.settings.sandbox import *
elif ENV == 'DEV':
    from src.settings.development import *
