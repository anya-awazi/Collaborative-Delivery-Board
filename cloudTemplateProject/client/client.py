import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import grpc
import sys
import cloudsecurity_pb2
import cloudsecurity_pb2_grpc

def run(username, password):
    channel = grpc.insecure_channel("localhost:51234")
    stub = cloudsecurity_pb2_grpc.UserServiceStub(channel)

    # Step 1: Login
    reply = stub.login(
        cloudsecurity_pb2.Request(login=username, password=password)

    )

    print("Server response:", reply.status)

    if reply.status != "OTP_SENT":
        return

    otp = input("Enter OTP: ")

    # Step 2: Verify OTP
    verify = stub.VerifyOTP(
        cloudsecurity_pb2.VerifyRequest(username=username, otp=otp)
    )

    print("Verification result:", verify.status)

if __name__ == "__main__":
    username = sys.argv[1]
    password = sys.argv[2]
    run(username, password)
