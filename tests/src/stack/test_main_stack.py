import aws_cdk as core
import aws_cdk.assertions as assertions

from src.stack.main import MainStack


def test_cdk_stack():
    app = core.App()
    stack = MainStack(app)
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties("AWS::ApiGateway::RestApi", {"Name": "api_gateway"})
    template.has_resource_properties("AWS::ApiGateway::ApiKey", {"Name": "api_key", "Enabled": True})
    template.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "api"})
    template.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "{proxy+}"})

    template.has_resource_properties("AWS::DynamoDB::Table", {"TableName": "app-local-products"})
    template.has_resource_properties("AWS::Lambda::Function", {"FunctionName": "app-local-api"})
