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

from src.settings import Settings, LOCAL, QA, PRODUCTION


settings = Settings()

PYTHON_RUNTIME = aws_lambda.Runtime.PYTHON_3_12
SOURCE_PATH = "./src"

class MainStack(Stack):
    """ Main Stack for the application, containing all resources """ 

    def __init__(self, scope, **kwargs) -> None:
        if settings.environment != LOCAL:
            kwargs['env'] = Environment(settings.AWS_ACCOUNT_ID, settings.AWS_REGION)
        super().__init__(scope, 'MainStack',  **kwargs)
        
        self.common_layer = aws_lambda.LayerVersion(
            self, f"common-layer",
            layer_version_name=settings.prefix + 'common-layer',
            code=aws_lambda.Code.from_asset(path.normpath("./common_layer")),
            compatible_runtimes=[PYTHON_RUNTIME],
            description=f'{settings.app_name} Common Layer dependencies',
        )

        self.tables = DynamoConstruct(self)
        self.gateway = ApiGatewayConstruct(self)

        # an API to rule them all
        api = Lambda(self, 'api')
        api.grant_read_write_data(self.tables.all())
        self.gateway.url(api, url='/api/{proxy+}', method='ANY')


##############
# Constructs #
##############

class DynamoConstruct(Construct):
    """ DynamoDB Tables construct for the MainStack """

    def __init__(self, scope: MainStack):
        super().__init__(scope, '#DynamoConstruct')

        self.items = aws_dynamodb.Table(self, 'items',
                           table_name=settings.resource_prefix + 'items',
                           partition_key={'name': 'id', 'type': aws_dynamodb.AttributeType.STRING},
                           billing_mode=aws_dynamodb.BillingMode.PAY_PER_REQUEST,
                           stream=aws_dynamodb.StreamViewType.NEW_IMAGE,)
        self.items.add_global_secondary_index(
            index_name='gsi_name',
            partition_key={'name': 'name', 'type': aws_dynamodb.AttributeType.STRING},
            sort_key={'name': 'id', 'type': aws_dynamodb.AttributeType.STRING},
            projection_type=aws_dynamodb.ProjectionType.KEYS_ONLY,
        )
    
    def all(self) -> list[aws_dynamodb.Table]:
        """ Returns a list of DynamoDB tables """
        return [self.items,]


class Lambda(Construct):
    """ Lambda Function construct for the MainStack """
    
    def __init__(self, scope: MainStack, name: str,
                 handler: str = 'main.handler',
                 timeout: int = 30):
        super().__init__(self, f'#Lambda')

        self.function = aws_lambda.Function(self, name,
            function_name=settings.resource_prefix + name,
            runtime=PYTHON_RUNTIME,
            code=aws_lambda.Code.from_asset(path.normpath(path.join("./src", name))),
            layers=[scope.common_layer],
            handler=handler,
            timeout=Duration.seconds(timeout),
            environment=settings.lambda_env_vars(LAMBDA_NAME=name),
            tracing=aws_lambda.Tracing.ACTIVE,
        )

    def grant_read_write_data(self, tables: list[aws_dynamodb.Table]):
        for table in tables:
            table.grant_read_write_data(self.function)


class ApiGatewayConstruct(Construct):
    def __init__(self, scope: Stack):
        super().__init__(scope, f"#ApiGatewayConstruct")
        self.scope = scope
        self.rest_api = aws_apigateway.RestApi(self, 'rest_api',
            rest_api_name=settings.resource_prefix + 'api',)
        self.root = {'': self.rest_api.root}

    def _get_resource(self, url: str, resources: dict) -> aws_apigateway.Resource:
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

    def url(self, lambda_function: Lambda, url: str, method: str):
        resource = self._get_resource(url, self.root)
        resource.add_method(method, aws_apigateway.LambdaIntegration(lambda_function.function))
