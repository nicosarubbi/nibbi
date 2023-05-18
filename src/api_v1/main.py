from fastapi import FastAPI
from mangum import Mangum
from . import router


API_PREFIX = '/v1'

app = FastAPI(
    docs_url=f'{API_PREFIX}/docs',
    redoc_url=f'{API_PREFIX}/redoc',
    dopenapi_url=f'{API_PREFIX}/openapi.json',
)


@app.get(f'{API_PREFIX}/healthcheck')
async def healthcheck():
    return 'ok'


app.include_router(router.router, prefix=API_PREFIX)

handler = Mangum(app)
