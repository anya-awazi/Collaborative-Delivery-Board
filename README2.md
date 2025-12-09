# KlausSafe - Secure Cloud Storage

KlausSafe is a distributed cloud storage system that simulates Google Drive functionality with redundancy and fault tolerance.

## Features

- 🔐 **User Authentication**: Secure login and signup system
- 📤 **File Upload**: Upload files with progress tracking
- 📥 **File Download**: Download files reconstructed from distributed blocks
- 💾 **Distributed Storage**: Files are chunked and stored across multiple nodes
- 🔄 **Redundancy**: Each block is stored on 2 nodes for fault tolerance
- 📊 **Storage Management**: 5GB storage limit per user with usage tracking
- 👨‍💼 **Admin Portal**: Manage nodes, extend capacities, view network statistics
- 📈 **Real-time Progress**: Upload progress indicators for all file sizes
- 🎨 **Modern UI**: Beautiful, responsive interface with drag-and-drop support

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Access the application:
- Open your browser and go to `http://localhost:5000`

## Default Credentials

- **Admin Account**: 
  - Username: `admin`
  - Password: `admin123`

## Architecture

### Storage System
- Files are divided into 2MB chunks
- Each chunk is stored on 2 different nodes (redundancy factor)
- Chunks are distributed across available nodes in a round-robin fashion
- File metadata stored in SQLite database

### Network Nodes
- Default configuration includes 3 storage nodes
- Nodes can be added/extended through admin portal
- Each node tracks storage capacity, bandwidth, and utilization

## Usage

### User Features
1. **Sign Up**: Create a new account
2. **Login**: Access your storage
3. **Upload Files**: Drag and drop or click to browse
4. **View Files**: See all uploaded files with sizes and dates
5. **Download Files**: Download any uploaded file
6. **Monitor Storage**: Track storage usage and available space

### Admin Features
1. **Add Nodes**: Add new storage nodes to the network
2. **Extend Capacity**: Increase storage capacity of existing nodes
3. **View Statistics**: Monitor network and storage utilization
4. **Manage Network**: View all nodes and their status

## File Structure

```
KlausSafe/
├── app.py                  # Main Flask application
├── storage_virtual_node.py # Node implementation
├── storage_virtual_network.py # Network management
├── templates/              # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── signup.html
│   ├── dashboard.html
│   └── admin.html
├── static/                 # Static files
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
├── data/                   # Stored file blocks
│   └── blocks/
├── uploads/                # Temporary upload directory
└── klaussafe.db           # SQLite database
```

## Security Notes

⚠️ **Important**: This is a demo application. For production use:
- Change the secret key in `app.py`
- Use a production-grade database (PostgreSQL, MySQL)
- Implement proper file validation and virus scanning
- Add rate limiting and CSRF protection
- Use HTTPS for secure connections
- Implement proper backup strategies

## License

This project is provided as-is for educational purposes.



