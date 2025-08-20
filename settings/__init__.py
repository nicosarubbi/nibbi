from os import getenv
from .default import *


LOCAL = 'local'
QA = 'qa'
PRODUCTION = 'production'

ENV = getenv('ENVIRONMENT', LOCAL)


if ENV == LOCAL:
    from .local import *
elif ENV == QA:
    from .qa import *
elif ENV == PRODUCTION:
    from .production import *
else:
    from .default import *
