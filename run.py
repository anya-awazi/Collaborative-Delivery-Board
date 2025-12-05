#!/usr/bin/env python
"""
KlausSafe - Quick Start Script
Run this file to start the KlausSafe application
"""
from app import app, init_db, sync_node_storage_from_db

if __name__ == '__main__':
    print("=" * 50)
    print("KlausSafe - Secure Cloud Storage")
    print("=" * 50)
    print("\nInitializing database...")
    init_db()
    print("Database initialized successfully!")
    print("\nSyncing node storage from existing files...")
    sync_node_storage_from_db()
    print("Node storage synchronized!")
    print("\nStarting server on Windows...")
    print("Access the application at: http://localhost:5000")
    print("(Running locally on your Windows machine - not in a VM)")
    print("\nDefault admin credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 50)
    print()
    # Run on localhost (Windows local machine) - accessible only from this computer
    # Change to '0.0.0.0' if you want to access from other devices on your network
    app.run(debug=True, host='127.0.0.1', port=5000)

