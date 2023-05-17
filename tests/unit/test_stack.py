import aws_cdk as core
import aws_cdk.assertions as assertions

from src.stack import MainStack


# example tests. To run these tests, uncomment this file along with the example
# resource in nibbi/nibbi_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = MainStack(app, "app")
    template = assertions.Template.from_stack(stack)
    print(template)
#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })

