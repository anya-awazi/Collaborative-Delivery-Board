# create_user.py
import bcrypt
import sys

# Usage: python create_user.py username email password
if len(sys.argv) < 4:
    print("Usage: create_user.py username email password")
    sys.exit(1)

username = sys.argv[1]
email = sys.argv[2]
password = sys.argv[3]

pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
line = f"{username},{email},{pw_hash}\n"
with open("credentials", "a", encoding="utf-8") as f:
    f.write(line)

print("User added:", username)
