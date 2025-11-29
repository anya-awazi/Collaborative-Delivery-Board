import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


import random
import bcrypt
import grpc
from concurrent import futures

import cloudsecurity_pb2
import cloudsecurity_pb2_grpc

otp_store = {}  # store OTP in memory

class UserService(cloudsecurity_pb2_grpc.UserServiceServicer):

    def Login(self, request, context):
        username = request.username
        password = request.password

        # Load credentials
        with open("server/credentials", "r") as f:
            for line in f:
                u, email, pwd_hash = line.strip().split(",")
                if u == username:
                    if bcrypt.checkpw(password.encode(), pwd_hash.encode()):
                        # Generate OTP
                        otp = str(random.randint(100000, 999999))
                        otp_store[username] = otp
                        print(f"[SERVER] OTP for {username}: {otp}")
                        return cloudsecurity_pb2.LoginReply(status="OTP_SENT")

        return cloudsecurity_pb2.LoginReply(status="UNAUTHORIZED")

    def VerifyOTP(self, request, context):
        username = request.username
        otp = request.otp

        if username in otp_store and otp_store[username] == otp:
            del otp_store[username]
            return cloudsecurity_pb2.VerifyReply(status="OTP_VALID")

        return cloudsecurity_pb2.VerifyReply(status="OTP_INVALID")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    cloudsecurity_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port("[::]:51234")
    print("Server running on port 51234...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
