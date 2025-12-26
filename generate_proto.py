#!/usr/bin/env python3

import os
import sys
from grpc_tools import protoc

def generate_proto_code():
    """Generate Python code from proto files."""
    # Create output directory if it doesn't exist
    proto_dir = os.path.join(os.path.dirname(__file__), 'protos')
    output_dir = os.path.join(os.path.dirname(__file__), 'generated')
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate Python code from proto
    proto_file = os.path.join(proto_dir, 'cloudsim.proto')
    protoc.main([
        'grpc_tools.protoc',
        f'--proto_path={proto_dir}',
        f'--python_out={output_dir}',
        f'--grpc_python_out={output_dir}',
        os.path.basename(proto_file)
    ])
    
    # Create __init__.py if it doesn't exist
    init_file = os.path.join(output_dir, '__init__.py')
    if not os.path.exists(init_file):
        open(init_file, 'a').close()
    
    print(f"Generated gRPC code in {output_dir}")

if __name__ == '__main__':
    generate_proto_code()
