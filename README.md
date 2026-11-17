# HCM Lite – AI-Assisted Human Capital Management System

HCM Lite is an AI-assisted Human Capital Management (HCM) system designed to simplify and streamline organizational HR operations. It provides a centralized platform for managing employees, attendance, departments, designations, leave requests, payroll, and organizational activities.

The system also integrates an AI Assistant powered by the Groq API to help users retrieve HR-related information using natural-language questions while respecting role-based data access.

## Key Features

### 1. Authentication & Role-Based Access Control
- Secure user authentication using JWT.
- Role-based access for Admin, HR, and Employee.
- Protected API endpoints.
- Employee-specific data access.

### 2. Employee Management
- Create, view, update, and manage employee records.
- Manage employee information and employment details.
- Create and manage employee login accounts.
- Face enrollment for attendance identification.

### 3. Organization Management
- Department management.
- Designation management.
- Centralized organizational structure.

### 4. Attendance Management
- Employee attendance records.
- Attendance tracking and status management.
- Face-based attendance functionality.

### 5. Leave Management
- Submit and manage leave requests.
- Track pending, approved, and rejected requests.
- Role-based leave management.

### 6. Payroll Management
- Manage employee payroll records.
- Track payroll status.
- View payroll information according to user permissions.

### 7. AI Assistant
- Natural-language HR queries.
- AI-powered responses using the Groq API.
- Access to authorized employee, attendance, leave, and payroll context.
- Role-aware responses for Admin, HR, and Employee.
- Context-based answers to reduce unsupported information.

### 8. Audit Logs
- Record important organizational activities.
- Track the user who performed an action.
- Store action types, target information, and timestamps.
- Admin-only audit log access.
- Paginated audit log retrieval.

## Technology Stack

### Frontend
- React.js
- Vite
- JavaScript
- HTML5
- CSS3
- Axios
- Recharts
- Face recognition libraries

### Backend
- Python
- FastAPI
- Pydantic
- MongoDB
- Motor / PyMongo (depending on the configured database implementation)
- JWT Authentication
- Groq API
- OpenAI Python SDK

### Database
- MongoDB

### Deployment
- Vercel – Frontend hosting
- Render – Backend hosting
- MongoDB Atlas – Cloud database hosting

## Project Structure

```text
HCM-Lite/
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── utils/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── employees.py
│   │   │       ├── attendance.py
│   │   │       ├── leave.py
│   │   │       ├── payroll.py
│   │   │       ├── audit.py
│   │   │       └── ai_assistant.py
│   │   │
│   │   ├── core/
│   │   ├── services/
│   │   │   ├── ai_assistant.py
│   │   │   └── grok_services.py
│   │   │
│   │   └── main.py
│   │
│   ├── requirements.txt
│   └── .env.example
│
└── README.md
```

*Note: This is a representative structure. Your actual repository may contain additional modules and files.*

## Installation and Setup

### Prerequisites

Install the following before running the project:

- Python 3.11+
- Node.js and npm
- MongoDB
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/Junaid-Ahmed-Khan/HCM-LITE-PROJECT
cd HCM-Lite
```

### 2. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv env
```

Activate the environment.

Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the backend directory and configure the required environment variables according to `app/core/config.py`.

Example configuration (adjust names to match your settings):

```env
MONGODB_URL=your_mongodb_connection_string
SECRET_KEY=your_jwt_secret
GROQ_API_KEY=your_groq_api_key
GROQ_BASE_URL=your_groq_base_url
GROQ_MODEL=your_groq_model
```

Start the FastAPI server:

```bash
python -m uvicorn app.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### 3. Frontend Setup

Open another terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create a `.env` file in the frontend directory:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Start the development server:

```bash
npm run dev
```

The frontend will be available at the URL displayed by Vite, usually:

```text
http://localhost:5173
```

## API Overview

The backend exposes RESTful API endpoints for different modules.

| Module | Endpoint | Method |
|---|---|---|
| AI Assistant | `/api/v1/ai/ask` | POST |
| Audit Logs | `/api/v1/audit-logs` | GET |
| Authentication | `/api/v1/auth` | Depends on route |
| Employees | `/api/v1/employees` | Depends on route |
| Attendance | `/api/v1/attendance` | Depends on route |
| Leave | `/api/v1/leave` | Depends on route |
| Payroll | `/api/v1/payroll` | Depends on route |

For complete endpoint details, visit the FastAPI Swagger documentation at `/docs`.

## AI Assistant Workflow

The AI Assistant processes HR-related questions through the following workflow:

1. The user submits a natural-language question through the frontend.
2. The frontend sends the question to the FastAPI backend.
3. The backend authenticates the user and checks their role.
4. The backend retrieves the authorized HR context from MongoDB.
5. The AI Assistant service prepares a context-based prompt.
6. The Groq API generates a response.
7. The backend returns the answer to the frontend.

The assistant uses different data access scopes for Admin/HR and Employee accounts.

## Security

- JWT-based authentication.
- Role-based authorization.
- Backend-side access control.
- Employee-specific data restrictions.
- Protected AI Assistant endpoint.
- Admin-only Audit Logs endpoint.
- Environment variables for sensitive configuration.

Never commit `.env` files, database credentials, JWT secrets, or AI provider API keys to GitHub.

## Deployment

The application can be deployed using the following architecture:

| Component | Platform |
|---|---|
| React + Vite frontend | Vercel |
| FastAPI backend | Render |
| MongoDB database | MongoDB Atlas |

For production deployment:
1. Host the MongoDB database on MongoDB Atlas.
2. Deploy the FastAPI backend on Render.
3. Configure production environment variables.
4. Deploy the React frontend on Vercel.
5. Configure the frontend API URL and backend CORS origins.
6. Test authentication and all application modules.

## Future Improvements

- Advanced AI tool calling for authorized HR operations.
- More detailed HR analytics and reporting.
- Advanced attendance insights.
- Improved AI conversation history.
- Enhanced dashboard visualizations.
- Automated notifications and reminders.

## Contributors

**HCM Lite Development Team**

Developed as an AI-assisted Human Capital Management project for the Saylani Hackathon.

---

**HCM Lite – Simplifying Human Resource Management with AI.**
