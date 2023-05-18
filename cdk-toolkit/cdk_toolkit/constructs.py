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
from src import settings


def abs_path(path, name):
    return path.normpath(path.join(path, name))


class BaseStack(Stack):
    RUNTIME = aws_lambda.Runtime.PYTHON_3_10
    SOURCE_PATH = "/src"

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        if settings.AWS_ACCOUNT_ID:
            kwargs['env'] = Environment(settings.AWS_ACCOUNT_ID, settings.AWS_REGION)

        super().__init__(scope, construct_id,  **kwargs)
        self.lambda_layers = []
        self.dynamo_tables = []
        self.env_variables = dict(
            ENVIRONMENT=settings.ENV,
            VERSION=settings.VERSION,
            LOGGER_LEVEL=settings.LOGGER_LEVEL,
            PROJECT_NAME=settings.SERVICE_NAME,
            LAMBDA_NAME='',
        )
        self.env_variables.update(settings.LAMBDA_ENV)
        self.api = None

    def add_layer(self, name, description) -> aws_lambda.LayerVersion:
        layer = aws_lambda.LayerVersion(
            self, f"{name}-layer",
            code=aws_lambda.Code.from_asset(abs_path(self.SOURCE_PATH, name)),
            compatible_runtimes=[self.RUNTIME],
            description=description,
        )
        self.lambda_layers.append(layer)
        return layer


class DynamoTable(Construct):
    def __init__(self, scope: 'BaseStack', name: str, 
                 partition_key: str, partition_key_type: ddb.AttributeType = ddb.AttributeType.STRING, 
                 sort_key: str = None, sort_key_type: ddb.AttributeType = ddb.AttributeType.STRING,
                 env_variable_name: str = None):

        super().__init__(scope, f'#{name}')
        partition_key = {'name': partition_key, 'type': partition_key_type}
        sort_key = {'name': sort_key, 'type': sort_key_type} if sort_key else None

        self.table = ddb.Table(scope, name, partition_key=partition_key, sort_key=sort_key,
                               billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
                               stream=ddb.StreamViewType.NEW_IMAGE)

        self.name = name
        self.scope = scope
        self.scope.dynamo_tables.append(self)

        env_variable_name = env_variable_name or f"TABLE_{name}"
        self.scope.env_variables[env_variable_name] = self.table.table_name

    def add_secondary_index(self, name, 
                            partition_key: str, partition_key_type: ddb.AttributeType = ddb.AttributeType.STRING, 
                            sort_key: str = None, sort_key_type: ddb.AttributeType = ddb.AttributeType.STRING):

        partition_key = {'name': partition_key, 'type': partition_key_type}
        sort_key = {'name': sort_key, 'type': sort_key_type} if sort_key else None
        self.table.add_global_secondary_index(partition_key=partition_key, sort_key=sort_key, index_name=name)


class Api(Construct):
    def __init__(self, scope: BaseStack, name: str, api_key: str = None, usage_plan: str = None):
        super().__init__(scope, f"#{name}")
        self.scope = scope
        self.api = apigw.RestApi(self, name)
        self.api_key = None
        self.usage_plan = None
        self.root = {'': self.api.root}

        if api_key and usage_plan:
            self.api_key = self.api.add_api_key(api_key, api_key_name=api_key)
            self.usage_plan = self.api.add_usage_plan(usage_plan, name=usage_plan)
            self.usage_plan.add_api_key(self.api_key)
            self.usage_plan.add_api_stage(stage=self.api.deployment_stage)

    def get_resource(self, url, resources=None) -> apigw.Resource:
        resources = resources or self.root
        if url in resources:
            return resources[url]
        if not url:
            raise KeyError(f'resource root missing: {resources}')
        breadcrumb = url.split('/')
        sub_path = '/'.join(breadcrumb[:-1])
        end_path = breadcrumb[-1]
        sub_resource = self.get_resource(sub_path, resources)
        resources[url] = sub_resource.add_resource(end_path)
        return resources[url]

    def add(self, name: str, url: str, method: str, api_key_required: bool = False,
            timeout: int = 60, source: str = None, **kwargs):

        function = Lambda(self.scope, name, timeout, source, **kwargs)
        resource = self.get_resource(url)
        integration = apigw.LambdaIntegration(function.alias)
        resource.add_method(method, integration, api_key_required=api_key_required)
        return function


class Lambda(Construct):
    def __init__(self, scope: BaseStack, name: str,
                 timeout: int = 60, source: str = None, **kwargs):

        super().__init__(scope, f'#{name}')
        kwargs.update(scope.env_variables)
        kwargs['LAMBDA_NAME'] = name
        source = source or 'main.handler'

        self._lambda = aws_lambda.Function(scope, name,
            runtime=scope.RUNTIME,
            code=aws_lambda.Code.from_asset(abs_path(self.SOURCE_PATH, name)),
            layers=scope.lambda_layers,
            handler=source,
            timeout=Duration.seconds(timeout),
            environment=kwargs,
            tracing=aws_lambda.Tracing.ACTIVE,
        )

        # TODO: add canary
        self.alias = self._lambda

        # give permission to write tables
        for table in scope.dynamo_tables:
            table.table.grant_read_write_data(self._lambda)
