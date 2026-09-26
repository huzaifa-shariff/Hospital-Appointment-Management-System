# Hospital Appointment Management System

A responsive hospital administration website for managing patient registration, clinicians, departments, schedules, appointments, payments and clinical records. Built as an academic BCA project using Flask, SQLite and Jinja templates.

## Features

- Dashboard with live database counts, today's schedule, upcoming appointments and department activity.
- Patient and doctor profiles with create, edit, view and guarded delete actions.
- Department directory and recurring doctor schedules.
- Appointment booking with department-dependent doctor selection and AJAX-generated available slots.
- Server-side doctor, department, schedule and duplicate-slot validation backed by a SQLite unique index.
- Appointment search and filtering, status updates and printable details.
- Manual payment capture, prescriptions, linked medical notes, patient history and CSV appointment export.
- Period-based appointment, doctor, department and revenue reports.
- Responsive Bootstrap 5 interface with reusable status badges and friendly empty states.

## Technologies

Python 3 · Flask · SQLite · HTML5 · CSS3 · Bootstrap 5 · JavaScript · Font Awesome · Jinja2

## Installation and run

```bash
python -m venv venv
```

Windows: `venv\Scripts\activate`  
Linux/macOS: `source venv/bin/activate`

```bash
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/). The SQLite database and fictional demonstration data are created automatically on first run. No login is configured.

## Database

`database.db` contains `patients`, `doctors`, `departments`, `doctor_schedules`, `appointments`, `payments`, `prescriptions` and `medical_records`. Foreign key enforcement is enabled per connection. Appointment slots are unique per doctor/date/time unless a previous booking is cancelled.

## Main routes

| Area | Routes |
| --- | --- |
| Dashboard | `/` |
| Patients | `/patients`, `/patients/add`, `/patients/view/<id>`, `/patients/edit/<id>` |
| Doctors | `/doctors`, `/doctors/add`, `/doctors/view/<id>`, `/doctors/edit/<id>` |
| Departments | `/departments`, `/departments/add` |
| Schedules | `/schedules`, `/schedules/add` |
| Appointments | `/appointments`, `/appointments/book`, `/appointments/view/<id>` |
| Billing / records | `/payments`, `/prescriptions`, `/medical-records` |
| Reports | `/reports`, `/reports/appointments.csv` |
| JSON APIs | `/api/doctors/<department_id>`, `/api/available-slots/<doctor_id>/<YYYY-MM-DD>`, `/api/patient/<patient_id>` |

## Project structure

```text
app.py                  Flask routes, validation, database initialization and demo data
database.db             Created automatically at runtime
requirements.txt        Flask dependency
static/css/style.css    Responsive hospital administration theme
static/js/script.js     Dynamic booking, confirmations and interface behavior
templates/              Jinja pages and shared layout
```

## Screenshots

Run the application locally and capture the dashboard and appointment workflow for project documentation.

## Future enhancements

Authentication and role permissions, appointment reminders, PDF exports, patient portal and payment gateway integration.

## Learning outcomes

This project demonstrates Flask routing, Jinja inheritance, relational schema design, parameterized SQL, CRUD patterns, backend validation, JSON APIs, fetch-based interactions, report aggregation and responsive web design.
