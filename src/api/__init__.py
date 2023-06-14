from fastapi import FastAPI, APIRouter
from mangum import Mangum

# import resources
from . import items

# setup FastAPI
API_PREFIX = '/api'
app = FastAPI(
    docs_url=f'{API_PREFIX}/docs',
    redoc_url=f'{API_PREFIX}/redoc',
    dopenapi_url=f'{API_PREFIX}/openapi.json',
)
handler = Mangum(app)
router = APIRouter()

# basic endpoint for verifying API status
@app.get(f'{API_PREFIX}/healthcheck')
async def healthcheck():
    return 'ok'

# end setup FastAPI


##########################
# Include Resources here #
##########################
router.include_router(items.router, tags=['items'])

app.include_router(router, prefix=API_PREFIX)