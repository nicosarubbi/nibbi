from os import path

from aws_cdk import Environment
from aws_cdk.aws_dynamodb import AttributeType
from aws_cdk.aws_lambda import Runtime

from cdk_toolkit.constructs import BaseStack, DynamoTable, Api
from src import settings


class MainStack(BaseStack):
    RUNTIME = Runtime.PYTHON_3_10
    SOURCE_PATH = path.dirname(__file__)
    ENVIRONMENT=settings.ENV
    VERSION=settings.VERSION
    LOGGER_LEVEL=settings.LOGGER_LEVEL
    SERVICE_NAME=settings.SERVICE_NAME

    def __init__(self, scope, construct_id: str, **kwargs) -> None:
        if settings.AWS_ACCOUNT_ID:
            kwargs['env'] = Environment(settings.AWS_ACCOUNT_ID, settings.AWS_REGION)

        super().__init__(scope, construct_id,  **kwargs)

        self.add_layer("common", "Lambda Common Dependencies")

        # TODO: read tables from model
        table_items = DynamoTable(self, 'items',
            partition_key='id', partition_key_type=AttributeType.STRING,
            sort_key='name', sort_key_type=AttributeType.STRING,
        )
        table_items.add_secondary_index('name-index',
            partition_key='name', partition_key_type=AttributeType.STRING,
        )
        
        api = Api(self, settings.API_NAME,
                  api_key=settings.API_KEY_NAME,
                  usage_plan=settings.API_USAGE_PLAN_NAME)

        api.add_lambda('api_v1', url='/v1/{proxy+}', method='ANY', api_key_required=False)
