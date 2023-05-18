import aws_cdk as core
import aws_cdk.assertions as assertions

from src.stack import MainStack


def test_sqs_queue_created():
    app = core.App()
    stack = MainStack(app, "app")
    template = assertions.Template.from_stack(stack)

    template.has_resource_properties("AWS::ApiGateway::RestApi", {"Name": "api"})
    template.has_resource_properties("AWS::ApiGateway::ApiKey", {"Name": "api_key", "Enabled": True})
    template.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "v1"})
    template.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "{proxy+}"})
    template.has_resource_properties("AWS::Lambda::Function", {'Handler': 'handler', 'Runtime': 'python3.10'})
    template.has_resource_properties("AWS::DynamoDB::Table", {})
