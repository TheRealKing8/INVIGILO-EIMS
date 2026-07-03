# 🛡️ Invigilo – Smart Examination Invigilation Management System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.13-blue?style=for-the-badge&logo=python)
![Django](https://img.shields.io/badge/Django-5.x-green?style=for-the-badge&logo=django)
![Next.js](https://img.shields.io/badge/Next.js-15-black?style=for-the-badge&logo=next.js)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue?style=for-the-badge&logo=typescript)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?style=for-the-badge&logo=postgresql)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-4.x-38B2AC?style=for-the-badge&logo=tailwindcss)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

### **A Modern Enterprise Examination Invigilation Management System**

*Automating examination scheduling, intelligent invigilator allocation, room management, attendance tracking, reporting, and analytics for higher learning institutions.*

---

**Author:** Thee Prince Isaac's Juma

</div>

---

# 📖 Table of Contents

- Overview
- Problem Statement
- Objectives
- Key Features
- System Modules
- User Roles
- Technology Stack
- System Architecture
- Project Structure
- Smart Allocation Engine
- Database Design
- API Architecture
- Security Features
- Reports
- Analytics Dashboard
- Screenshots
- Installation
- Environment Variables
- Running the Project
- Testing
- Deployment
- Roadmap
- Future Enhancements
- Contributing
- License
- Author

---

# 📌 Overview

**Invigilo** is a modern web-based **Examination Invigilation Management System (EIMS)** designed to automate examination administration in universities, colleges, and educational institutions.

The system streamlines examination planning by intelligently allocating invigilators, managing examination venues, tracking attendance, recording incidents, generating reports, and providing administrators with real-time analytics.

Invigilo eliminates manual scheduling conflicts while ensuring fairness, transparency, accountability, and operational efficiency.

---

# 🚨 Problem Statement

Educational institutions often experience challenges such as:

- Manual invigilator allocation
- Scheduling conflicts
- Double-booked examination rooms
- Unequal workload distribution
- Poor attendance monitoring
- Manual report generation
- Difficulty tracking examination incidents
- Lack of centralized examination management

Invigilo addresses these challenges through intelligent automation and centralized management.

---

# 🎯 Objectives

- Automate examination scheduling.
- Allocate invigilators fairly.
- Prevent scheduling conflicts.
- Improve examination transparency.
- Digitize attendance management.
- Generate comprehensive examination reports.
- Improve institutional efficiency.
- Provide administrators with real-time analytics.

---

# ✨ Key Features

## Authentication

- Secure Login
- JWT Authentication
- Refresh Tokens
- Forgot Password
- Reset Password
- Email Verification
- Role-Based Access Control (RBAC)

---

## User Management

- Administrators
- Examination Officers
- Invigilators
- Heads of Department
- Faculty Deans

---

## Academic Management

- Faculties
- Departments
- Academic Programmes
- Courses
- Units

---

## Examination Management

- Examination Periods
- Examination Timetables
- Examination Sessions
- Examination Rooms
- Room Capacity Management

---

## Smart Invigilator Allocation

Automatically assigns invigilators based on:

- Availability
- Workload
- Room Capacity
- Examination Time
- Department Preference
- Maximum Daily Allocation
- Conflict Detection

---

## Attendance Management

- Invigilator Check-in
- Check-out
- QR Code Attendance (Optional)
- Attendance Reports

---

## Incident Reporting

Record:

- Cheating Cases
- Medical Emergencies
- Late Arrivals
- Missing Scripts
- Student Misconduct
- Examination Disruptions

---

## Notifications

- Email Notifications
- Dashboard Alerts
- Assignment Reminders
- Schedule Updates

---

## Reports

Generate:

- Daily Reports
- Examination Reports
- Attendance Reports
- Invigilator Workload Reports
- Room Utilization Reports
- Incident Reports

Export:

- PDF
- Excel
- CSV

---

## Analytics Dashboard

Interactive dashboard displaying:

- Today's Examinations
- Invigilators on Duty
- Attendance Summary
- Room Utilization
- Examination Statistics
- Faculty Performance
- Department Statistics

---

# 👥 User Roles

| Role | Responsibilities |
|------|-------------------|
| Administrator | Full system control |
| Examination Officer | Manage examinations |
| Invigilator | View assignments and submit reports |
| Head of Department | Monitor departmental examinations |
| Faculty Dean | Faculty-level oversight |

---

# 🏗️ Technology Stack

## Backend

- Python 3.13
- Django
- Django REST Framework
- SimpleJWT
- Celery
- Redis
- Django Filters
- Pillow
- ReportLab
- OpenPyXL

---

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- Shadcn UI
- React Query
- Axios
- React Hook Form
- Zod
- Framer Motion

---

## Database

- PostgreSQL

---

## DevOps

- Docker
- Docker Compose
- GitHub Actions
- Nginx

---

# 🏛️ System Architecture

```
                    Users
                      │
        ┌─────────────┼─────────────┐
        │             │             │
 Administrator   Examination Officer   Invigilator
        │             │             │
        └─────────────┼─────────────┘
                      │
              Django REST API
                      │
      ┌───────────────┼────────────────┐
      │               │                │
 Authentication   Business Logic   Allocation Engine
      │               │                │
      └───────────────┼────────────────┘
                      │
                 PostgreSQL
                      │
         Reports • Notifications • Analytics
```

---

# 📂 Project Structure

```
Invigilo/
│
├── backend/
│
├── frontend/
│
├── database/
│
├── docs/
│
├── docker/
│
├── .github/
│   └── workflows/
│
├── README.md
├── LICENSE
├── docker-compose.yml
└── .gitignore
```

---

# 🧠 Smart Allocation Engine

The heart of Invigilo.

The allocation engine automatically assigns invigilators while ensuring:

- No timetable conflicts
- No room conflicts
- Fair workload distribution
- Availability checks
- Maximum daily assignments
- Department preference
- Room capacity consideration

### Allocation Rules

| Room Capacity | Invigilators |
|--------------|--------------|
| 1–50 | 1 |
| 51–100 | 2 |
| 101–150 | 3 |
| 151+ | 4 |

---

# 🗄️ Database Entities

- Users
- Roles
- Permissions
- Faculties
- Departments
- Programmes
- Courses
- Units
- Students
- Invigilators
- Exam Periods
- Exam Sessions
- Exam Rooms
- Room Allocations
- Invigilator Assignments
- Attendance
- Incident Reports
- Notifications
- Audit Logs

---

# 🔌 REST API

RESTful APIs built with Django REST Framework.

Features include:

- JWT Authentication
- Filtering
- Pagination
- Search
- Ordering
- OpenAPI Documentation
- Validation
- Versioning

---

# 🔒 Security

- JWT Authentication
- Password Hashing
- CSRF Protection
- CORS
- Input Validation
- Audit Logs
- Role-Based Authorization
- Permission Checks

---

# 📊 Reports

Generate professional reports including:

- Attendance Reports
- Examination Reports
- Room Utilization
- Invigilator Allocation
- Daily Activity
- Faculty Reports
- Department Reports
- Incident Reports

Export formats:

- PDF
- Excel
- CSV

---

# 📈 Dashboard

Real-time dashboard displaying:

- Total Examinations
- Today's Invigilators
- Attendance Percentage
- Room Occupancy
- Examination Schedule
- Notifications
- Incident Statistics

---

# 🚀 Installation

Clone the repository.

```bash
git clone https://github.com/TheRealKing8/Examination-Invigilation-Management-System.git
```

Navigate into the project.

```bash
cd Examination-Invigilation-Management-System
```

---

# ⚙️ Backend Setup

Create a virtual environment.

```bash
python -m venv venv
```

Activate it.

Windows

```bash
venv\Scripts\activate
```

Linux/macOS

```bash
source venv/bin/activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

---

# 🌐 Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

---

# 🗃️ Database

Create PostgreSQL database.

Configure:

```
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=
```

Run migrations.

```bash
python manage.py migrate
```

---

# ▶️ Start Backend

```bash
python manage.py runserver
```

---

# 🧪 Testing

Run tests.

```bash
pytest
```

---

# 🐳 Docker

Build containers.

```bash
docker-compose up --build
```

---

# 📅 Roadmap

## Phase 1

- Project Planning
- SRS
- ERD
- Architecture

## Phase 2

- Authentication
- Users
- Roles

## Phase 3

- Academic Management

## Phase 4

- Examination Scheduling

## Phase 5

- Smart Allocation Engine

## Phase 6

- Attendance

## Phase 7

- Incident Reporting

## Phase 8

- Reports

## Phase 9

- Analytics Dashboard

## Phase 10

- Deployment

---

# 🔮 Future Enhancements

- AI-powered invigilator allocation
- Machine learning workload prediction
- Mobile application
- QR Code attendance
- Facial recognition attendance
- SMS notifications
- Calendar synchronization
- Microsoft Teams integration
- Google Workspace integration
- Multi-campus support

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to GitHub
5. Open a Pull Request

---

# 📄 License

This project is licensed under the MIT License.

---

# 👨‍💻 Author

### Isaac Juma

**Computer Science Student | Full-Stack Software Developer | Software Engineer**

GitHub: https://github.com/TheRealKing8

---

<div align="center">

### ⭐ If you find this project useful, please consider giving it a star!

**Invigilo — Smart Examination Invigilation Management System**

*Building smarter, fairer, and more efficient examination management.*

</div>
