#!/usr/bin/env python3
import aws_cdk as cdk

from src.stack import MainStack


app = cdk.App()
MainStack(app, "App")

app.synth()
