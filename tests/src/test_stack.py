import aws_cdk as core
import aws_cdk.assertions as assertions

from src.stack import MainStack


def test_cdk_stack():
    app = core.App()
    stack = MainStack(app, "app")
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties("AWS::ApiGateway::RestApi", {"Name": "api_gateway"})
    template.has_resource_properties("AWS::ApiGateway::ApiKey", {"Name": "api_key", "Enabled": True})
    template.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "api"})
    template.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "{proxy+}"})

    tables = template.find_resources("AWS::DynamoDB::Table", {})
    assert any(name.startswith('items') for name in tables)

    functions = template.find_resources("AWS::Lambda::Function", {})
    assert any(name.startswith('api') for name in functions)
