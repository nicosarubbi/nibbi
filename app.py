#!/usr/bin/env python3
import aws_cdk as cdk

from src.stack.main import MainStack


app = cdk.App()
MainStack(app)
app.synth()
