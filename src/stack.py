from decimal import Decimal
from os import path

from aws_cdk import (
    aws_apigateway,
    aws_dynamodb,
    aws_lambda,
    Duration,
    Environment,
    Stack,
)
from constructs import Construct
from pydantic import BaseModel

import settings
from shared.db import DDB
from shared import models


class MainStack(Stack):
    RUNTIME = aws_lambda.Runtime.PYTHON_3_10
    LAYERS_PATH = "./layers"
    SOURCE_PATH = "./src"
    VERSION = settings.VERSION
    SERVICE_NAME = settings.SERVICE_NAME
    ENVIRONMENT = settings.ENV
    LOGGER_LEVEL = settings.LOGGER_LEVEL
    AWS_ACCOUNT_ID = settings.AWS_ACCOUNT_ID
    AWS_REGION = settings.AWS_REGION

    def __init__(self, scope, construct_id: str, **kwargs) -> None:
        if self.AWS_ACCOUNT_ID and self.AWS_REGION:
            kwargs['env'] = Environment(self.AWS_ACCOUNT_ID, self.AWS_REGION)
        super().__init__(scope, construct_id,  **kwargs)

        # define layers here
        common_layer = aws_lambda.LayerVersion(
            self, f"common-layer",
            code=aws_lambda.Code.from_asset(path.normpath(path.join(self.LAYERS_PATH, 'common'))),
            compatible_runtimes=[self.RUNTIME],
            description='Common Layer dependencies',
        )
        
        # define dynamo tables here
        items = DynamoTable.from_model(self, models.Item)
        
        # define lambdas here
        api = Lambda(self, 'api', layers=[common_layer], tables=[items])

        # define API Gateway here
        gateway = ApiGateway(self, 'api_gateway', api_key='api_key', usage_plan='api_usage_plan')
        gateway.url(api, url='/api/{proxy+}', method='ANY', api_key_required=False)


##############
# Constructs #
##############

class DynamoTable(Construct):
    def __init__(self, scope: MainStack, name: str, 
                 partition_key: str, partition_key_type: aws_dynamodb.AttributeType = aws_dynamodb.AttributeType.STRING, 
                 sort_key: str = None, sort_key_type: aws_dynamodb.AttributeType = aws_dynamodb.AttributeType.STRING,
                 billing_mode=aws_dynamodb.BillingMode.PAY_PER_REQUEST,
                 stream=aws_dynamodb.StreamViewType.NEW_IMAGE,
                 **kwargs,
                 ):

        super().__init__(scope, f'#{name}')
        partition_key = {'name': partition_key, 'type': partition_key_type}
        sort_key = {'name': sort_key, 'type': sort_key_type} if sort_key else None

        self.name = name
        self.env_variable_name = f"TABLE_{name}"
        self.table = aws_dynamodb.Table(scope, name, partition_key=partition_key, sort_key=sort_key,
                               billing_mode=billing_mode, stream=stream, **kwargs)
        self.table_name = self.table.table_name

    def add_secondary_index(self, name, 
                            partition_key: str, partition_key_type: aws_dynamodb.AttributeType = aws_dynamodb.AttributeType.STRING, 
                            sort_key: str = None, sort_key_type: aws_dynamodb.AttributeType = aws_dynamodb.AttributeType.STRING):

        partition_key = {'name': partition_key, 'type': partition_key_type}
        sort_key = {'name': sort_key, 'type': sort_key_type} if sort_key else None
        self.table.add_global_secondary_index(partition_key=partition_key, sort_key=sort_key, index_name=name)

    @staticmethod 
    def _field_type(model: type[BaseModel], field_name) -> aws_dynamodb.AttributeType:
        t = model.__fields__[field_name].type_
        if isinstance(t, type) and issubclass(t, str):
            return aws_dynamodb.AttributeType.STRING
        if isinstance(t, type) and any(issubclass(t, type_) for type_ in [int, float, Decimal]):
            return aws_dynamodb.AttributeType.NUMBER
        raise TypeError(f'DynamoDB Index field `{field_name}` should be either string or numeric')

    @classmethod
    def from_model(cls, scope: MainStack, model: type[BaseModel], **kwargs) -> 'DynamoTable':
        meta = DDB.meta(model)
        schema = {'name': meta.name}
        secondary_indexes = []
        for name, index in meta.indexes.items():
            index_schema = {
                'partition_key': index.partition_key,
                'partition_key_type': cls._field_type(model, index.partition_key),
            }
            if index.sort_key:
                index_schema.update(sort_key=index.sort_key, sort_key_type=cls._field_type(model, index.sort_key))
            if name is None:
                schema.update(index_schema)
            else:
                index_schema['name'] = name
                secondary_indexes.append(index_schema)

        table = cls(scope, **schema, **kwargs)
        for index in secondary_indexes:
            table.add_secondary_index(**index)
        return table


class Lambda(Construct):
    def __init__(self, scope: MainStack, name: str,
                 layers: list[aws_lambda.LayerVersion], tables: list[DynamoTable],
                 timeout: int = 30, env_variables=None):

        super().__init__(scope, f'#{name}')
        tables = tables or []
        layers = layers or []

        env = dict(
            ENVIRONMENT=scope.ENVIRONMENT,
            VERSION=scope.VERSION,
            LOGGER_LEVEL=scope.LOGGER_LEVEL,
            SERVICE_NAME=scope.SERVICE_NAME,
            LAMBDA_NAME=name,
        )
        env.update({table.env_variable_name: table.table_name for table in tables})
        if env_variables:
            env.update(env_variables)

        self._lambda = aws_lambda.Function(scope, name,
            runtime=scope.RUNTIME,
            code=aws_lambda.Code.from_asset(path.normpath(path.join(scope.SOURCE_PATH, name))),
            layers=layers,
            handler='handler',
            timeout=Duration.seconds(timeout),
            environment=env,
            tracing=aws_lambda.Tracing.ACTIVE,
        )

        # TODO: add canary
        self.alias = self._lambda

        # give permission to write tables
        for table in tables:
            table.table.grant_read_write_data(self._lambda)


class ApiGateway(Construct):
    def __init__(self, scope: Stack, name: str, api_key: str = None, usage_plan: str = None):
        super().__init__(scope, f"#{name}")
        self.scope = scope
        self.rest_api = aws_apigateway.RestApi(self, name)
        self.api_key = None
        self.usage_plan = None
        self.root = {'': self.rest_api.root}

        if api_key and usage_plan:
            self.api_key = self.rest_api.add_api_key(api_key, api_key_name=api_key)
            self.usage_plan = self.rest_api.add_usage_plan(usage_plan, name=usage_plan)
            self.usage_plan.add_api_key(self.api_key)
            self.usage_plan.add_api_stage(stage=self.rest_api.deployment_stage)

    def _get_resource(self, url, resources=None) -> aws_apigateway.Resource:
        resources = resources or self.root
        if url in resources:
            return resources[url]
        if not url:
            raise KeyError(f'resource root missing: {resources}')
        breadcrumb = url.split('/')
        sub_path = '/'.join(breadcrumb[:-1])
        end_path = breadcrumb[-1]
        sub_resource = self._get_resource(sub_path, resources)
        resources[url] = sub_resource.add_resource(end_path)
        return resources[url]

    def url(self, function: Lambda, url: str, method: str, api_key_required: bool = False):
        resource = self._get_resource(url)
        integration = aws_apigateway.LambdaIntegration(function.alias)
        resource.add_method(method, integration, api_key_required=api_key_required)
