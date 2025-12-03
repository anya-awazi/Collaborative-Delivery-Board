import sqlite3

DB = "storage.db"

def create_tables():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        otp TEXT,
        used_space INTEGER DEFAULT 0,
        total_space INTEGER DEFAULT 2147483648, -- 2GB
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT,
        size INTEGER,
        node_locations TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    print("Database initialized successfully.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
