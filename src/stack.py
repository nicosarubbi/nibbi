from cdk_toolkit.constructs import BaseStack, Layer, DynamoTable, Api, Lambda

import settings
from shared import models


class MainStack(BaseStack):
    VERSION = settings.VERSION
    SERVICE_NAME = settings.SERVICE_NAME
    ENVIRONMENT = settings.ENV
    LOGGER_LEVEL = settings.LOGGER_LEVEL
    AWS_ACCOUNT_ID = settings.AWS_ACCOUNT_ID
    AWS_REGION = settings.AWS_REGION

    def __init__(self, scope, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id,  **kwargs)

        # define layers here
        common_layer = Layer(self, "common", "Lambda Common Dependencies")
        
        # define dynamo tables here
        items = DynamoTable.from_model(self, models.Item)
        
        # define lambdas here
        api_v1 = Lambda(self, 'api_v1', layers=[common_layer], tables=[items])

        # define API here
        api = Api(self, settings.API_NAME, api_key=settings.API_KEY_NAME, usage_plan=settings.API_USAGE_PLAN_NAME)
        api.url(api_v1, url='/v1/{proxy+}', method='ANY', api_key_required=False)
