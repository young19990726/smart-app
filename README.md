# SMART-ECG App Deployment Guide

## Project Overview

The SMART-ECG App is a medical application designed to analyze ECG data in FHIR format. It consists of:

1. **Backend**: A FastAPI application that processes FHIR-formatted ECG data, extracts ECG waveforms, and connects to an AI service for ECG analysis.
2. **Frontend**: A Streamlit application that provides a user interface for uploading FHIR files and displaying the processed ECG waveforms.

## System Requirements

- Python 3.8+
- pip (Python package manager)
- Git (for version control)
- Adequate storage for ECG data files

## Deployment Steps

### 1. Clone the Repository

```bash
git clone <repository_url>
cd smart-app
```

### 2. Set Up Environment Variables

Create a `.env` file in the backend root directory with the following content:

```
# FastAPI Settings
SERVICE_DEBUG=True
FASTAPI_PORT=8000
WORKER_COUNT=5

# Authentication
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
USERNAME=your_admin_username
HASHED_PASSWORD=your_hashed_password

# Database Settings (if using a database)
DB_USER=db_username
DB_PASSWORD=db_password
DB_HOSTNAME=localhost
DB_PORT=5432
DB_NAME=smart_app_db

# FHIR Validation (if needed)
client_id=your_fhir_client_id
client_secret=your_fhir_client_secret
```

Note: To generate a hashed password for the `HASHED_PASSWORD` field, you can use the following Python code:

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed_password = pwd_context.hash("your_plain_password")
print(hashed_password)
```

### 3. Create Directory Structure

Ensure the following directories exist for file storage:

```bash
mkdir -p backend/file/json
mkdir -p backend/file/image
```

### 4. Backend Setup

#### Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

If a requirements.txt file doesn't exist, create one with the following content:

```
fastapi==0.104.1
uvicorn==0.24.0
python-dotenv==1.0.0
pydantic==2.4.2
starlette==0.27.0
matplotlib==3.8.2
numpy==1.26.2
scipy==1.11.4
requests==2.31.0
python-multipart==0.0.6
passlib==1.7.4
python-jose==3.3.0
bcrypt==4.0.1
```

#### Start the Backend Server

```bash
cd backend
python main.py
```

The FastAPI backend will start on http://127.0.0.1:8000 by default.

### 5. Frontend Setup

#### Install Dependencies

```bash
cd frontend
pip install -r requirements.txt
```

If a requirements.txt file doesn't exist, create one with the following content:

```
streamlit==1.29.0
requests==2.31.0
pillow==10.1.0
```

#### Start the Frontend Application

```bash
cd frontend
streamlit run app.py
```

The Streamlit frontend will start on http://localhost:8501 by default.

### 6. Testing the Application

1. Access the frontend at http://localhost:8501
2. Log in with the username and password set in the `.env` file
3. Upload a FHIR-formatted ECG JSON file
4. Click "Submit" to process the file
5. View the ECG waveform and results

## Application Architecture Details

### Backend Components

- **FastAPI Framework**: Provides REST API endpoints for file processing
- **OAuth2 Authentication**: Secures API endpoints
- **ECG Data Processing**: Extracts and transforms ECG data from FHIR format
- **AI Integration**: Connects to an external AI service for ECG analysis

### Frontend Components

- **Streamlit UI**: User-friendly interface for file uploads and result display
- **Authentication Flow**: Secures application access
- **File Upload**: Handles file submission to the backend
- **Result Visualization**: Displays ECG waveforms and AI analysis results

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/SMART-ECG/token` | POST | Obtains authentication token |
| `/api/v1/SMART-ECG` | POST | Uploads and processes FHIR ECG data |
| `/api/v1/SMART-ECG/users/me/` | GET | Gets current user information |

## Error Handling and Troubleshooting

### Common Issues

1. **Authentication Failures**: Verify the username and password in the `.env` file
2. **File Processing Errors**: Ensure uploaded files are valid FHIR-formatted JSON files
3. **Backend Connection Issues**: Check that the backend server is running on the correct port
4. **Missing Directories**: Confirm that the required file directories have been created

### Logging

The application uses both standard and custom loggers:

- **uvicorn.error**: Logs standard FastAPI/Uvicorn messages
- **custom.error**: Logs application-specific errors

Check these logs for troubleshooting information.

---

For any additional assistance or questions, please contact the development team.
