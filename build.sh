#!/usr/bin/env bash
# Install dependencies
pip install -r requirements.txt

# Compile the .proto file into Python native classes
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. library.proto:
