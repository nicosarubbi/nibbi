from os import path
from aws_cdk import (
    aws_apigateway as apigw,
    aws_dynamodb as ddb,
    aws_lambda,
    Duration,
    Environment,
    Stack,
)
from constructs import Construct
from pydantic import BaseModel
from . import mock_db


class BaseStack(Stack):
    RUNTIME = aws_lambda.Runtime.PYTHON_3_10
    LAYERS_PATH = "./layers"
    SOURCE_PATH = "./src"
    LOGGER_LEVEL = 'INFO'
    VERSION = '0.0.0'
    SERVICE_NAME = 'App'
    ENVIRONMENT = 'TEST'
    AWS_ACCOUNT_ID = None
    AWS_REGION = None

    def __init__(self, scope, construct_id: str, **kwargs) -> None:
        if self.AWS_ACCOUNT_ID and self.AWS_REGION:
            kwargs['env'] = Environment(self.AWS_ACCOUNT_ID, self.AWS_REGION)
        super().__init__(scope, construct_id,  **kwargs)


class Layer(Construct):
    def __init__(self, scope: BaseStack, name: str, description: str):
        super().__init__(scope, f'#{name}-layer')
        self.layer_version = aws_lambda.LayerVersion(
            scope, f"{name}-layer",
            code=aws_lambda.Code.from_asset(path.normpath(path.join(scope.LAYERS_PATH, name))),
            compatible_runtimes=[scope.RUNTIME],
            description=description or f'Lambda Layer dependencies: {name.title()}',
        )


class DynamoTable(Construct):
    def __init__(self, scope: BaseStack, name: str, 
                 partition_key: str, partition_key_type: ddb.AttributeType = ddb.AttributeType.STRING, 
                 sort_key: str = None, sort_key_type: ddb.AttributeType = ddb.AttributeType.STRING):

        super().__init__(scope, f'#{name}')
        partition_key = {'name': partition_key, 'type': partition_key_type}
        sort_key = {'name': sort_key, 'type': sort_key_type} if sort_key else None

        self.name = name
        self.env_variable_name = f"TABLE_{name}"
        self.table = ddb.Table(scope, name, partition_key=partition_key, sort_key=sort_key,
                               billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
                               stream=ddb.StreamViewType.NEW_IMAGE)
        self.table_name = self.table.table_name

    def add_secondary_index(self, name, 
                            partition_key: str, partition_key_type: ddb.AttributeType = ddb.AttributeType.STRING, 
                            sort_key: str = None, sort_key_type: ddb.AttributeType = ddb.AttributeType.STRING):

        partition_key = {'name': partition_key, 'type': partition_key_type}
        sort_key = {'name': sort_key, 'type': sort_key_type} if sort_key else None
        self.table.add_global_secondary_index(partition_key=partition_key, sort_key=sort_key, index_name=name)

    @classmethod
    def from_model(cls, scope, model: type[BaseModel]):
        schema, secondary_indexes = mock_db.table_schema(model)
        table = cls(scope, **schema)
        for index in secondary_indexes:
            table.add_secondary_index(**index)
        return table


class Lambda(Construct):
    def __init__(self, scope: BaseStack, name: str,
                 layers: list[Layer], tables: list[DynamoTable],
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
        env.update({table.env_variable_name: table.name for table in tables})
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


class Api(Construct):
    def __init__(self, scope: BaseStack, name: str, api_key: str = None, usage_plan: str = None):
        super().__init__(scope, f"#{name}")
        self.scope = scope
        self.rest_api = apigw.RestApi(self, name)
        self.api_key = None
        self.usage_plan = None
        self.root = {'': self.rest_api.root}

        if api_key and usage_plan:
            self.api_key = self.rest_api.add_api_key(api_key, api_key_name=api_key)
            self.usage_plan = self.rest_api.add_usage_plan(usage_plan, name=usage_plan)
            self.usage_plan.add_api_key(self.api_key)
            self.usage_plan.add_api_stage(stage=self.rest_api.deployment_stage)

    def _get_resource(self, url, resources=None) -> apigw.Resource:
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
        integration = apigw.LambdaIntegration(function.alias)
        resource.add_method(method, integration, api_key_required=api_key_required)
