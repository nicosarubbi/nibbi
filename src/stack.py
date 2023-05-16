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


class BaseStack(Stack):
    RUNTIME = None

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

    def add_layer(self, name, path, description) -> aws_lambda.LayerVersion:
        layer = aws_lambda.LayerVersion(
            self, name,
            code=aws_lambda.Code.from_asset(path),
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

        super().__init__(scope, f'DynamoTable-{name}')
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
        super().__init__(scope, f"Api-{name}")
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

    def add(self, lambda_name: str, url: str, method: str, api_key_required: bool = False,
            timeout: int = 60, source: str = None, **kwargs):

        function = Lambda(self.scope, lambda_name, timeout, source, **kwargs)
        resource = self.get_resource(url)
        integration = apigw.LambdaIntegration(function.alias)
        resource.add_method(method, integration, api_key_required=api_key_required)
        return function


class Lambda(Construct):
    def __init__(self, scope: BaseStack, lambda_name: str, 
                 timeout: int = 60, source: str = None, **kwargs):

        super().__init__(scope, f'Lambda-{lambda_name}')
        kwargs.update(scope.env_variables)
        kwargs['LAMBDA_NAME'] = lambda_name
        source = source or 'main.handler'

        self._lambda = aws_lambda.Function(scope, lambda_name,
            runtime=scope.RUNTIME,
            code=aws_lambda.Code.from_asset(f"src/{lambda_name}"),
            layers=scope.lambda_layers,
            handler=f"{lambda_name}.{source}",
            timeout=Duration.seconds(timeout),
            environment=kwargs,
            tracing=aws_lambda.Tracing.ACTIVE,
        )

        # TODO: add canary
        self.alias = self._lambda

        # give permission to write tables
        for table in scope.dynamo_tables:
            table.table.grant_read_write_data(self._lambda)


class MainStack(BaseStack):
    RUNTIME = aws_lambda.Runtime.PYTHON_3_10

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id,  **kwargs)

        self.add_layer("common-layer", "src/common", "Lambda Common Dependencies (requirements.txt)")
        self.add_layer("shared-layer", "src/shared", "Lambda Shared Dependencies")

        table_items = DynamoTable(self, 'items',
            partition_key='id', partition_key_type=ddb.AttributeType.STRING,
            sort_key='name', sort_key_type=ddb.AttributeType.STRING,
        )
        table_items.add_secondary_index('name-index',
            partition_key='name', partition_key_type=ddb.AttributeType.STRING,
        )
        
        api = Api(self, settings.API_NAME, settings.API_KEY_NAME, settings.API_USAGE_PLAN_NAME)

        api.add('api_v1', url='/v1/{proxy+}', method='ANY', api_key_required=False)
