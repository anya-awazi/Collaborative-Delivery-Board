import os
import sys
import subprocess
from pathlib import Path

def compile_proto():
    # Ensure protos directory exists
    proto_dir = Path("protos")
    if not proto_dir.exists():
        print(f"Error: {proto_dir} directory not found")
        return False
    
    # Create generated directory if it doesn't exist
    generated_dir = Path("generated")
    generated_dir.mkdir(exist_ok=True)
    
    # Find all proto files
    proto_files = list(proto_dir.glob("*.proto"))
    if not proto_files:
        print("No .proto files found in the protos directory")
        return False
    
    # Compile each proto file
    for proto_file in proto_files:
        print(f"Compiling {proto_file}...")
        try:
            # Generate Python gRPC code
            cmd = [
                sys.executable, "-m", "grpc_tools.protoc",
                f"--proto_path={proto_dir}",
                f"--python_out={generated_dir}",
                f"--grpc_python_out={generated_dir}",
                f"--mypy_out={generated_dir}",
                f"--mypy_grpc_out={generated_dir}",
                str(proto_file.name)
            ]
            
            subprocess.run(cmd, check=True, cwd=proto_dir)
            print(f"Successfully compiled {proto_file}")
            
        except subprocess.CalledProcessError as e:
            print(f"Error compiling {proto_file}: {e}")
            return False
    
    # Create __init__.py in generated directory
    (generated_dir / "__init__.py").touch()
    
    # Create a module for the generated code
    (generated_dir / "cloud_storage_pb2.py").touch()
    (generated_dir / "cloud_storage_pb2_grpc.py").touch()
    (generated_dir / "cloud_storage_pb2.pyi").touch()
    (generated_dir / "cloud_storage_pb2_grpc.pyi").touch()
    
    print("\nCompilation complete!")
    print(f"Generated files are in: {generated_dir.absolute()}")
    return True

if __name__ == "__main__":
    if compile_proto():
        print("\nTo use the generated code, add the following to your Python path:")
        print(f"export PYTHONPATH=$PYTHONPATH:{Path('generated').absolute()}")
    else:
        print("\nFailed to compile proto files.")
        sys.exit(1)
