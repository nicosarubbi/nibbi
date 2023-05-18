from os import path
from aws_cdk import (
    aws_apigateway as apigw,
    aws_dynamodb as ddb,
    aws_lambda,
    Duration,
    Stack,
)
from constructs import Construct


class BaseStack(Stack):
    RUNTIME = aws_lambda.Runtime.PYTHON_3_10
    SOURCE_PATH = "/src"
    VERSION='0.0.0'
    LOGGER_LEVEL='INFO'
    SERVICE_NAME='App'
    ENVIRONMENT=''

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id,  **kwargs)
        self.lambda_layers = []
        self.dynamo_tables = []
        self.env_variables = dict(
            ENVIRONMENT=self.ENVIRONMENT,
            VERSION=self.VERSION,
            LOGGER_LEVEL=self.LOGGER_LEVEL,
            SERVICE_NAME=self.SERVICE_NAME,
        )
        self.api = None

    def add_layer(self, name, description) -> aws_lambda.LayerVersion:
        layer = aws_lambda.LayerVersion(
            self, f"{name}-layer",
            code=aws_lambda.Code.from_asset(path.normpath(path.join(self.SOURCE_PATH, name))),
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

    def add_lambda(self, name: str, url: str, method: str,
                   api_key_required: bool = False, timeout: int = 30, env_variables=None):

        function = Lambda(self.scope, name, timeout, env_variables)
        resource = self._get_resource(url)
        integration = apigw.LambdaIntegration(function.alias)
        resource.add_method(method, integration, api_key_required=api_key_required)
        return function


class Lambda(Construct):
    def __init__(self, scope: BaseStack, name: str, timeout: int = 60, env_variables=None):

        super().__init__(scope, f'#{name}')
        env = {}
        env.update(scope.env_variables)
        if env_variables:
            env.update(env_variables)

        self._lambda = aws_lambda.Function(scope, name,
            runtime=scope.RUNTIME,
            code=aws_lambda.Code.from_asset(path.normpath(path.join(scope.SOURCE_PATH, name))),
            layers=scope.lambda_layers,
            handler='handler',
            timeout=Duration.seconds(timeout),
            environment=env,
            tracing=aws_lambda.Tracing.ACTIVE,
        )

        # TODO: add canary
        self.alias = self._lambda

        # give permission to write tables
        for table in scope.dynamo_tables:
            table.table.grant_read_write_data(self._lambda)
