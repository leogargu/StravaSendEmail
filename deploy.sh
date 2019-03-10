#!/bin/bash
zip lambda_function.zip lambda_function.py html_body.txt text_body.txt
aws lambda update-function-code --function-name StravaSendEmail --zip-file fileb://lambda_function.zip --region eu-west-2
