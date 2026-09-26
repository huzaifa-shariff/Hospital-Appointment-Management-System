"""Hospital Appointment Management System - Flask + SQLite."""
from datetime import date, datetime, timedelta
import csv
import io
import math
import os
import sqlite3
from flask import Flask, abort, flash, jsonify, make_response, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hospital-demo-change-me')
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')
STATUSES = ['Scheduled', 'Confirmed', 'Completed', 'Cancelled', 'No Show', 'Rescheduled']
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

def db():
    conn = sqlite3.connect(DB_PATH, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

class ClosingConnection(sqlite3.Connection):
    """Commit/rollback and close when used with a with statement."""
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()

def rows(sql, args=()):
    with db() as con:
        return con.execute(sql, args).fetchall()

def one(sql, args=()):
    with db() as con:
        return con.execute(sql, args).fetchone()

def next_code(table, column, prefix):
    last = one(f'SELECT {column} FROM {table} ORDER BY {column} DESC LIMIT 1')
    n = int(last[0][len(prefix):]) + 1 if last else 1
    return f'{prefix}{n:03d}'

def valid_iso_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False

def valid_email(value):
    """Accept blank optional email addresses and reject malformed values."""
    if not value:
        return True
    return '@' in value and '.' in value.rsplit('@', 1)[-1] and ' ' not in value

def init_db():
    schema = '''
    CREATE TABLE IF NOT EXISTS departments(department_id INTEGER PRIMARY KEY, department_name TEXT UNIQUE NOT NULL, description TEXT DEFAULT '', location TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Active');
    CREATE TABLE IF NOT EXISTS patients(patient_id INTEGER PRIMARY KEY, patient_code TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, date_of_birth TEXT, gender TEXT, blood_group TEXT, phone TEXT NOT NULL, email TEXT, address TEXT, emergency_contact_name TEXT, emergency_contact_phone TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS doctors(doctor_id INTEGER PRIMARY KEY, doctor_code TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, specialization TEXT, department_id INTEGER NOT NULL REFERENCES departments ON DELETE RESTRICT, qualification TEXT, phone TEXT, email TEXT, consultation_fee REAL NOT NULL DEFAULT 0 CHECK(consultation_fee>=0), experience_years INTEGER DEFAULT 0, room_number TEXT, available_days TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Active', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS doctor_schedules(schedule_id INTEGER PRIMARY KEY, doctor_id INTEGER NOT NULL REFERENCES doctors ON DELETE CASCADE, day_of_week TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, slot_duration INTEGER NOT NULL DEFAULT 30, status TEXT NOT NULL DEFAULT 'Active', UNIQUE(doctor_id,day_of_week,start_time));
    CREATE TABLE IF NOT EXISTS appointments(appointment_id INTEGER PRIMARY KEY, appointment_code TEXT UNIQUE NOT NULL, patient_id INTEGER NOT NULL REFERENCES patients ON DELETE RESTRICT, doctor_id INTEGER NOT NULL REFERENCES doctors ON DELETE RESTRICT, department_id INTEGER NOT NULL REFERENCES departments ON DELETE RESTRICT, appointment_date TEXT NOT NULL, appointment_time TEXT NOT NULL, reason TEXT, symptoms TEXT, status TEXT NOT NULL DEFAULT 'Scheduled', notes TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE UNIQUE INDEX IF NOT EXISTS unique_active_slot ON appointments(doctor_id,appointment_date,appointment_time) WHERE status NOT IN ('Cancelled');
    CREATE TABLE IF NOT EXISTS payments(payment_id INTEGER PRIMARY KEY, appointment_id INTEGER NOT NULL REFERENCES appointments ON DELETE CASCADE, patient_id INTEGER NOT NULL REFERENCES patients ON DELETE RESTRICT, payment_date TEXT NOT NULL, amount REAL NOT NULL CHECK(amount>0), payment_mode TEXT NOT NULL, transaction_reference TEXT, payment_status TEXT NOT NULL DEFAULT 'Paid');
    CREATE TABLE IF NOT EXISTS prescriptions(prescription_id INTEGER PRIMARY KEY, appointment_id INTEGER NOT NULL REFERENCES appointments ON DELETE CASCADE, patient_id INTEGER NOT NULL REFERENCES patients ON DELETE RESTRICT, doctor_id INTEGER NOT NULL REFERENCES doctors ON DELETE RESTRICT, diagnosis TEXT NOT NULL, medicines TEXT, dosage TEXT, duration TEXT, instructions TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS medical_records(record_id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients ON DELETE CASCADE, appointment_id INTEGER REFERENCES appointments ON DELETE SET NULL, doctor_id INTEGER REFERENCES doctors ON DELETE SET NULL, diagnosis TEXT, symptoms TEXT, treatment TEXT, medical_notes TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    '''
    with db() as con:
        con.executescript(schema)
        if con.execute('SELECT COUNT(*) FROM departments').fetchone()[0] == 0:
            depts = ['Cardiology','Orthopedics','Dermatology','Neurology','Pediatrics','General Medicine','ENT','Dental']
            con.executemany('INSERT INTO departments(department_name,description,location) VALUES(?,?,?)', [(d, f'{d} clinical services', f'{i+1}th Floor') for i,d in enumerate(depts)])
        if con.execute('SELECT COUNT(*) FROM patients').fetchone()[0] == 0:
            patients = [('Aarav Sharma','1996-04-12','Male','O+','9876501001'),('Maya Patel','1988-09-21','Female','A+','9876501002'),('Kabir Khan','2001-02-17','Male','B+','9876501003'),('Ananya Iyer','1993-12-05','Female','AB+','9876501004'),('Rohan Das','1979-07-30','Male','O-','9876501005'),('Sara Thomas','1999-01-14','Female','B-','9876501006'),('Vikram Rao','1984-06-09','Male','A-','9876501007'),('Diya Nair','2004-08-23','Female','O+','9876501008'),('Imran Ali','1971-11-11','Male','AB-','9876501009'),('Meera Joshi','1990-03-03','Female','A+','9876501010'),('Arjun Menon','1998-05-19','Male','B+','9876501011'),('Fatima Sheikh','1986-10-28','Female','O+','9876501012'),('Dev Kapoor','1968-02-02','Male','A+','9876501013'),('Nisha Roy','1995-07-16','Female','AB+','9876501014'),('Sameer Gupta','2002-04-24','Male','O-','9876501015')]
            for i,p in enumerate(patients,1): con.execute('INSERT INTO patients(patient_code,full_name,date_of_birth,gender,blood_group,phone,email,address) VALUES(?,?,?,?,?,?,?,?)',(f'PAT{i:03d}',*p[:5],f'patient{i}@example.test','Bengaluru, India'))
        if con.execute('SELECT COUNT(*) FROM doctors').fetchone()[0] == 0:
            depts = con.execute('SELECT department_id FROM departments ORDER BY department_id').fetchall()
            docs = [('Aditi Rao','Cardiologist','MBBS, MD'),('Rahul Menon','Orthopedic Surgeon','MBBS, MS'),('Neha Verma','Dermatologist','MBBS, DVD'),('Sanjay Kulkarni','Neurologist','MBBS, DM'),('Priya Nair','Pediatrician','MBBS, DCH'),('Omar Siddiqui','Physician','MBBS, MD'),('Kavita Shah','ENT Specialist','MBBS, MS'),('Arvind Bhat','Dental Surgeon','BDS, MDS')]
            for i,(name,spec,qual) in enumerate(docs,1):
                dep=depts[i-1][0]
                con.execute('INSERT INTO doctors(doctor_code,full_name,specialization,department_id,qualification,phone,email,consultation_fee,experience_years,room_number,available_days) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(f'DOC{i:03d}',f'Dr. {name}',spec,dep,qual,f'0805550{i:04d}',f'doctor{i}@hospital.test',500+i*50,4+i,f'{100+i}', 'Monday,Tuesday,Wednesday,Thursday,Friday'))
                for day in ['Monday','Tuesday','Wednesday','Thursday','Friday']:
                    con.execute('INSERT INTO doctor_schedules(doctor_id,day_of_week,start_time,end_time,slot_duration) VALUES(?,?,?,?,?)',(i,day,'09:00','13:00',30))
        if con.execute('SELECT COUNT(*) FROM appointments').fetchone()[0] == 0:
            doctors=con.execute('SELECT doctor_id,department_id FROM doctors').fetchall()
            now=date.today()
            for i in range(20):
                d=now+timedelta(days=(i%13)-5)
                doc=doctors[i%len(doctors)]
                stat=['Completed','Confirmed','Scheduled','Cancelled','No Show'][i%5]
                con.execute('INSERT INTO appointments(appointment_code,patient_id,doctor_id,department_id,appointment_date,appointment_time,reason,status) VALUES(?,?,?,?,?,?,?,?)',(f'APT{i+1:03d}',i%15+1,doc['doctor_id'],doc['department_id'],d.isoformat(),f'{9+(i%7)//2:02d}:{(i%2)*30:02d}','General consultation',stat))

@app.context_processor
def global_context(): return {'today':date.today().isoformat(), 'statuses':STATUSES, 'days':DAYS}


@app.route('/')
def dashboard():
    today=date.today().isoformat()
    stats={'patients':one('SELECT COUNT(*) FROM patients')[0], 'doctors':one("SELECT COUNT(*) FROM doctors WHERE status='Active'")[0], 'departments':one("SELECT COUNT(*) FROM departments WHERE status='Active'")[0], 'today':one("SELECT COUNT(*) FROM appointments WHERE appointment_date=? AND status!='Cancelled'",(today,))[0], 'upcoming':one("SELECT COUNT(*) FROM appointments WHERE appointment_date>=? AND status IN ('Scheduled','Confirmed')",(today,))[0], 'completed':one("SELECT COUNT(*) FROM appointments WHERE status='Completed'")[0], 'cancelled':one("SELECT COUNT(*) FROM appointments WHERE status='Cancelled'")[0], 'pending':one("SELECT COUNT(*) FROM appointments WHERE status IN ('Scheduled','Confirmed')")[0], 'revenue':one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE payment_status='Paid'")[0]}
    appts=rows('''SELECT a.*,p.full_name patient,d.full_name doctor,dep.department_name FROM appointments a JOIN patients p USING(patient_id) JOIN doctors d USING(doctor_id) JOIN departments dep USING(department_id) WHERE a.appointment_date=? AND a.status!='Cancelled' ORDER BY a.appointment_time LIMIT 8''',(today,))
    upcoming=rows("SELECT a.*,p.full_name patient,d.full_name doctor,dep.department_name FROM appointments a JOIN patients p USING(patient_id) JOIN doctors d USING(doctor_id) JOIN departments dep USING(department_id) WHERE a.appointment_date>=? AND a.status IN ('Scheduled','Confirmed') ORDER BY a.appointment_date,a.appointment_time LIMIT 6",(today,))
    depstats=rows('SELECT dep.department_name,COUNT(a.appointment_id) total FROM departments dep LEFT JOIN appointments a USING(department_id) GROUP BY dep.department_id ORDER BY total DESC LIMIT 6')
    activity=rows('''
        WITH activity AS (
            SELECT 'patient' kind,full_name title,'Patient registration' detail,created_at occurred_at FROM patients
            UNION ALL SELECT 'appointment',a.appointment_code,'Appointment booked · '||p.full_name,a.created_at FROM appointments a JOIN patients p USING(patient_id)
            UNION ALL SELECT 'payment',a.appointment_code,'Payment recorded · ₹'||printf('%.2f',pay.amount),pay.payment_date||' 23:59:59' FROM payments pay JOIN appointments a USING(appointment_id)
            UNION ALL SELECT 'completed',a.appointment_code,'Visit completed · '||p.full_name,a.updated_at FROM appointments a JOIN patients p USING(patient_id) WHERE a.status='Completed'
        ), ranked AS (
            SELECT activity.*,ROW_NUMBER() OVER(PARTITION BY kind ORDER BY occurred_at DESC,title) AS kind_rank FROM activity
        )
        SELECT kind,title,detail,occurred_at FROM ranked WHERE kind_rank<=2
        ORDER BY occurred_at DESC,CASE kind WHEN 'payment' THEN 1 WHEN 'completed' THEN 2 WHEN 'appointment' THEN 3 ELSE 4 END LIMIT 8''')
    return render_template('index.html',stats=stats,appointments=appts,upcoming=upcoming,depstats=depstats,activity=activity)

@app.route('/patients')
def patients():
    q=request.args.get('q','').strip(); gender=request.args.get('gender',''); blood=request.args.get('blood','')
    sql='SELECT * FROM patients WHERE 1=1'; args=[]
    if q: sql+=' AND (full_name LIKE ? OR phone LIKE ? OR patient_code LIKE ?)'; args += [f'%{q}%']*3
    if gender: sql+=' AND gender=?'; args.append(gender)
    if blood: sql+=' AND blood_group=?'; args.append(blood)
    return render_template('patients.html', patients=rows(sql+' ORDER BY patient_id DESC',args), q=q, gender=gender,blood=blood)

@app.route('/patients/add',methods=['GET','POST'])
def add_patient():
    if request.method=='POST':
        f=request.form; name=f.get('full_name','').strip(); phone=f.get('phone','').strip(); dob=f.get('date_of_birth','')
        if not name or not phone: flash('Patient name and phone are required.','danger')
        elif dob and not valid_iso_date(dob): flash('Enter a valid date of birth.','danger')
        elif dob and dob>date.today().isoformat(): flash('Date of birth cannot be in the future.','danger')
        elif not valid_email(f.get('email','').strip()): flash('Enter a valid email address.','danger')
        else:
            with db() as con: con.execute('INSERT INTO patients(patient_code,full_name,date_of_birth,gender,blood_group,phone,email,address,emergency_contact_name,emergency_contact_phone) VALUES(?,?,?,?,?,?,?,?,?,?)',(next_code('patients','patient_code','PAT'),name,dob,f.get('gender'),f.get('blood_group'),phone,f.get('email'),f.get('address'),f.get('emergency_contact_name'),f.get('emergency_contact_phone')))
            flash('Patient registered successfully.','success'); return redirect(url_for('patients'))
    return render_template('add_patient.html', patient={})

@app.route('/patients/edit/<int:id>',methods=['GET','POST'])
def edit_patient(id):
    p=one('SELECT * FROM patients WHERE patient_id=?',(id,));
    if not p: abort(404)
    if request.method=='POST':
        f=request.form
        dob=f.get('date_of_birth','')
        if not f.get('full_name','').strip() or not f.get('phone','').strip(): flash('Name and phone are required.','danger')
        elif dob and (not valid_iso_date(dob) or dob>date.today().isoformat()): flash('Enter a valid date of birth that is not in the future.','danger')
        elif not valid_email(f.get('email','').strip()): flash('Enter a valid email address.','danger')
        else:
            with db() as con: con.execute('UPDATE patients SET full_name=?,date_of_birth=?,gender=?,blood_group=?,phone=?,email=?,address=?,emergency_contact_name=?,emergency_contact_phone=? WHERE patient_id=?',(f['full_name'].strip(),f.get('date_of_birth'),f.get('gender'),f.get('blood_group'),f.get('phone'),f.get('email'),f.get('address'),f.get('emergency_contact_name'),f.get('emergency_contact_phone'),id))
            flash('Patient details updated.','success'); return redirect(url_for('patient_view',id=id))
    return render_template('add_patient.html',patient=p,editing=True)

@app.route('/patients/view/<int:id>')
def patient_view(id):
    p=one('SELECT * FROM patients WHERE patient_id=?',(id,));
    if not p: abort(404)
    appts=rows('SELECT a.*,d.full_name doctor,dep.department_name FROM appointments a JOIN doctors d USING(doctor_id) JOIN departments dep USING(department_id) WHERE patient_id=? ORDER BY appointment_date DESC,appointment_time DESC',(id,))
    pays=rows('SELECT pay.*,a.appointment_code FROM payments pay JOIN appointments a USING(appointment_id) WHERE pay.patient_id=? ORDER BY payment_date DESC',(id,))
    rx=rows('SELECT pr.*,d.full_name doctor FROM prescriptions pr JOIN doctors d USING(doctor_id) WHERE pr.patient_id=? ORDER BY pr.created_at DESC',(id,))
    records=rows('SELECT m.*,d.full_name doctor FROM medical_records m LEFT JOIN doctors d USING(doctor_id) WHERE m.patient_id=? ORDER BY m.created_at DESC',(id,))
    return render_template('patient_details.html',patient=p,appointments=appts,payments=pays,prescriptions=rx,records=records)

@app.post('/patients/delete/<int:id>')
def delete_patient(id):
    try:
        with db() as con: con.execute('DELETE FROM patients WHERE patient_id=?',(id,))
        flash('Patient deleted.','success')
    except sqlite3.IntegrityError: flash('Patient has linked appointments and cannot be deleted.','warning')
    return redirect(url_for('patients'))

@app.route('/departments')
def departments():
    q=request.args.get('q','').strip()
    return render_template('departments.html',departments=rows('''SELECT d.*,COUNT(DISTINCT doc.doctor_id) doctors,COUNT(DISTINCT a.appointment_id) appointments FROM departments d LEFT JOIN doctors doc USING(department_id) LEFT JOIN appointments a USING(department_id) WHERE d.department_name LIKE ? GROUP BY d.department_id ORDER BY d.department_name''',(f'%{q}%',)),q=q)

@app.route('/departments/view/<int:id>')
def department_view(id):
    department=one('SELECT * FROM departments WHERE department_id=?',(id,))
    if not department: abort(404)
    doctors_list=rows('SELECT * FROM doctors WHERE department_id=? ORDER BY full_name',(id,))
    appointment_list=rows('SELECT a.*,p.full_name patient,d.full_name doctor FROM appointments a JOIN patients p USING(patient_id) JOIN doctors d USING(doctor_id) WHERE a.department_id=? ORDER BY a.appointment_date DESC,a.appointment_time DESC LIMIT 12',(id,))
    return render_template('department_details.html',department=department,doctors=doctors_list,appointments=appointment_list)

@app.route('/departments/add',methods=['GET','POST'])
def add_department():
    if request.method=='POST':
        f=request.form
        try:
            name=f.get('department_name','').strip()
            if not name:
                flash('Department name is required.','danger')
                return render_template('department_form.html',department={})
            with db() as con: con.execute('INSERT INTO departments(department_name,description,location) VALUES(?,?,?)',(name,f.get('description'),f.get('location')))
            flash('Department added.','success'); return redirect(url_for('departments'))
        except sqlite3.IntegrityError: flash('That department already exists.','danger')
    return render_template('department_form.html',department={})

@app.route('/departments/edit/<int:id>',methods=['GET','POST'])
def edit_department(id):
    d=one('SELECT * FROM departments WHERE department_id=?',(id,));
    if not d: abort(404)
    if request.method=='POST':
        f=request.form
        name=f.get('department_name','').strip()
        if not name or f.get('status','Active') not in ['Active','Inactive']:
            flash('Department name is required.','danger')
            return render_template('department_form.html',department=d,editing=True)
        try:
            with db() as con: con.execute('UPDATE departments SET department_name=?,description=?,location=?,status=? WHERE department_id=?',(name,f.get('description'),f.get('location'),f.get('status','Active'),id))
            flash('Department updated.','success'); return redirect(url_for('departments'))
        except sqlite3.IntegrityError: flash('That department name already exists.','danger')
    return render_template('department_form.html',department=d,editing=True)

@app.post('/departments/delete/<int:id>')
def delete_department(id):
    try:
        with db() as con: con.execute('DELETE FROM departments WHERE department_id=?',(id,))
        flash('Department deleted.','success')
    except sqlite3.IntegrityError: flash('Department has doctors or appointments and cannot be deleted.','warning')
    return redirect(url_for('departments'))

@app.route('/doctors')
def doctors():
    q=request.args.get('q','').strip(); dep=request.args.get('department','')
    sql='SELECT doc.*,d.department_name FROM doctors doc JOIN departments d USING(department_id) WHERE (doc.full_name LIKE ? OR doc.specialization LIKE ? OR doc.doctor_code LIKE ?)'; args=[f'%{q}%']*3
    if dep: sql+=' AND doc.department_id=?'; args.append(dep)
    return render_template('doctors.html',doctors=rows(sql+' ORDER BY doc.full_name',args),departments=rows('SELECT * FROM departments ORDER BY department_name'),q=q,department=dep)

def doctor_form(id=None):
    doc=one('SELECT * FROM doctors WHERE doctor_id=?',(id,)) if id else {}
    if id and not doc: abort(404)
    deps=rows("SELECT * FROM departments WHERE status='Active' ORDER BY department_name")
    if request.method=='POST':
        f=request.form
        try: fee=float(f.get('consultation_fee',0)); exp=int(f.get('experience_years',0))
        except ValueError: fee=-1; exp=0
        dep=one("SELECT department_id FROM departments WHERE department_id=? AND status='Active'",(f.get('department_id'),)) if f.get('department_id','').isdigit() else None
        if not f.get('full_name','').strip() or not dep or not math.isfinite(fee) or fee<0 or exp<0 or not valid_email(f.get('email','').strip()) or f.get('status','Active') not in ['Active','Inactive','On Leave']: flash('Enter a name, active department, valid email, and valid non-negative fee, experience and status.','danger')
        else:
            values=(f.get('full_name'),f.get('specialization'),f.get('department_id'),f.get('qualification'),f.get('phone'),f.get('email'),fee,exp,f.get('room_number'),','.join(f.getlist('available_days')),f.get('status','Active'))
            with db() as con:
                if id: con.execute('UPDATE doctors SET full_name=?,specialization=?,department_id=?,qualification=?,phone=?,email=?,consultation_fee=?,experience_years=?,room_number=?,available_days=?,status=? WHERE doctor_id=?',(*values,id))
                else: con.execute('INSERT INTO doctors(doctor_code,full_name,specialization,department_id,qualification,phone,email,consultation_fee,experience_years,room_number,available_days,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(next_code('doctors','doctor_code','DOC'),*values))
            flash('Doctor details saved.','success'); return redirect(url_for('doctors'))
    return render_template('doctor_form.html',doctor=doc,departments=deps,editing=bool(id))

@app.route('/doctors/add',methods=['GET','POST'])
def add_doctor(): return doctor_form()
@app.route('/doctors/edit/<int:id>',methods=['GET','POST'])
def edit_doctor(id): return doctor_form(id)
@app.route('/doctors/view/<int:id>')
def doctor_view(id):
    d=one('SELECT doc.*,dep.department_name FROM doctors doc JOIN departments dep USING(department_id) WHERE doctor_id=?',(id,));
    if not d: abort(404)
    return render_template('doctor_details.html',doctor=d,schedules=rows('SELECT * FROM doctor_schedules WHERE doctor_id=? ORDER BY CASE day_of_week WHEN "Monday" THEN 1 WHEN "Tuesday" THEN 2 WHEN "Wednesday" THEN 3 WHEN "Thursday" THEN 4 WHEN "Friday" THEN 5 WHEN "Saturday" THEN 6 ELSE 7 END',(id,)),appointments=rows('SELECT a.*,p.full_name patient FROM appointments a JOIN patients p USING(patient_id) WHERE doctor_id=? ORDER BY appointment_date DESC LIMIT 10',(id,)))
@app.post('/doctors/delete/<int:id>')
def delete_doctor(id):
    try:
        with db() as con: con.execute('DELETE FROM doctors WHERE doctor_id=?',(id,))
        flash('Doctor deleted.','success')
    except sqlite3.IntegrityError: flash('Doctor has linked appointments and cannot be deleted.','warning')
    return redirect(url_for('doctors'))

@app.route('/schedules')
def schedules(): return render_template('schedules.html',schedules=rows('SELECT s.*,d.full_name doctor,dep.department_name FROM doctor_schedules s JOIN doctors d USING(doctor_id) JOIN departments dep USING(department_id) ORDER BY d.full_name,s.day_of_week'),doctors=rows("SELECT * FROM doctors WHERE status='Active' ORDER BY full_name"))
@app.route('/schedules/add',methods=['GET','POST'])
def add_schedule():
    if request.method=='POST':
        f=request.form
        try: duration=int(f.get('slot_duration',30))
        except ValueError: duration=0
        doctor_id=f.get('doctor_id',''); schedule_day=f.get('day_of_week',''); start_time=f.get('start_time',''); end_time=f.get('end_time','')
        try:
            start_parsed=datetime.strptime(start_time,'%H:%M'); end_parsed=datetime.strptime(end_time,'%H:%M')
            valid_times=end_parsed>start_parsed
        except ValueError:
            valid_times=False
        active_doctor=one("SELECT doctor_id FROM doctors WHERE doctor_id=? AND status='Active'",(doctor_id,)) if doctor_id.isdigit() else None
        if not active_doctor or schedule_day not in DAYS or not valid_times or duration<5 or duration>240: flash('Choose an active doctor, valid day and time range, and slot duration from 5 to 240 minutes.','danger')
        else:
            try:
                with db() as con: con.execute('INSERT INTO doctor_schedules(doctor_id,day_of_week,start_time,end_time,slot_duration) VALUES(?,?,?,?,?)',(doctor_id,schedule_day,start_time,end_time,duration))
                flash('Doctor schedule added.','success'); return redirect(url_for('schedules'))
            except sqlite3.IntegrityError: flash('A schedule already exists for this doctor and day/start time.','danger')
    return render_template('schedule_form.html',doctors=rows("SELECT * FROM doctors WHERE status='Active' ORDER BY full_name"))
@app.post('/schedules/delete/<int:id>')
def delete_schedule(id):
    with db() as con: con.execute('DELETE FROM doctor_schedules WHERE schedule_id=?',(id,))
    flash('Schedule removed.','success'); return redirect(url_for('schedules'))

def valid_slot(doctor_id, day, time, ignore_id=None):
    try:
        appointment_day = date.fromisoformat(day)
        chosen = datetime.strptime(time, '%H:%M')
    except (TypeError, ValueError):
        return False, 'Enter a valid appointment date and time.'
    if appointment_day < date.today():
        return False, 'Appointment date cannot be in the past.'
    d=one("SELECT * FROM doctors WHERE doctor_id=? AND status='Active'",(doctor_id,))
    if not d: return False,'Selected doctor is unavailable.'
    schedule=one("SELECT * FROM doctor_schedules WHERE doctor_id=? AND day_of_week=? AND status='Active' AND start_time<=? AND end_time>? ORDER BY start_time LIMIT 1",(doctor_id,DAYS[date.fromisoformat(day).weekday()],time,time))
    if not schedule: return False,'Doctor is not scheduled at the selected time.'
    start=datetime.strptime(schedule['start_time'],'%H:%M'); end=datetime.strptime(schedule['end_time'],'%H:%M'); step=schedule['slot_duration']
    if int((chosen-start).total_seconds()//60)%step or chosen+timedelta(minutes=step)>end: return False,'Selected time is not an available appointment slot.'
    sql="SELECT appointment_id FROM appointments WHERE doctor_id=? AND appointment_date=? AND appointment_time=? AND status!='Cancelled'"; args=[doctor_id,day,time]
    if ignore_id: sql+=' AND appointment_id!=?'; args.append(ignore_id)
    if one(sql,args): return False,'This appointment slot is already booked. Please select another time.'
    return True,''

@app.route('/appointments')
def appointments():
    filters={k:request.args.get(k,'') for k in ['q','date_from','date_to','doctor','department','status']}
    sql='''SELECT a.*,p.full_name patient,p.phone patient_phone,d.full_name doctor,dep.department_name FROM appointments a JOIN patients p USING(patient_id) JOIN doctors d USING(doctor_id) JOIN departments dep USING(department_id) WHERE 1=1'''; args=[]
    if filters['q']: sql+=' AND (a.appointment_code LIKE ? OR p.full_name LIKE ? OR p.phone LIKE ? OR d.full_name LIKE ? OR dep.department_name LIKE ?)'; args += [f"%{filters['q']}%"]*5
    for key,col in [('date_from','a.appointment_date>='),('date_to','a.appointment_date<='),('doctor','a.doctor_id='),('department','a.department_id='),('status','a.status=')]:
        if filters[key]: sql+=' AND '+col+'?'; args.append(filters[key])
    data=rows(sql+' ORDER BY a.appointment_date DESC,a.appointment_time DESC',args)
    return render_template('appointments.html',appointments=data,filters=filters,doctors=rows('SELECT * FROM doctors ORDER BY full_name'),departments=rows('SELECT * FROM departments ORDER BY department_name'))

@app.route('/appointments/book',methods=['GET','POST'])
def book_appointment():
    if request.method=='POST':
        f=request.form
        try: patient_id=int(f['patient_id']); doctor_id=int(f['doctor_id']); dep_id=int(f['department_id']); day=date.fromisoformat(f['appointment_date']).isoformat(); tm=f['appointment_time']
        except (ValueError,KeyError): flash('Please complete all required booking fields.','danger'); return redirect(url_for('book_appointment'))
        if not one('SELECT patient_id FROM patients WHERE patient_id=?',(patient_id,)): flash('Invalid patient selected.','danger')
        elif not one("SELECT department_id FROM departments WHERE department_id=? AND status='Active'",(dep_id,)): flash('Invalid or inactive department selected.','danger')
        elif not one('SELECT doctor_id FROM doctors WHERE doctor_id=? AND department_id=?',(doctor_id,dep_id)): flash('Doctor does not belong to the selected department.','danger')
        else:
            ok,msg=valid_slot(doctor_id,day,tm)
            if not ok: flash(msg,'danger')
            else:
                try:
                    with db() as con: con.execute('INSERT INTO appointments(appointment_code,patient_id,doctor_id,department_id,appointment_date,appointment_time,reason,symptoms,notes) VALUES(?,?,?,?,?,?,?,?,?)',(next_code('appointments','appointment_code','APT'),patient_id,doctor_id,dep_id,day,tm,f.get('reason'),f.get('symptoms'),f.get('notes')))
                    flash('Appointment booked successfully.','success'); return redirect(url_for('appointments'))
                except sqlite3.IntegrityError: flash('This appointment slot is already booked. Please select another time.','danger')
    return render_template('book_appointment.html',patients=rows('SELECT * FROM patients ORDER BY full_name'),departments=rows("SELECT * FROM departments WHERE status='Active' ORDER BY department_name"))

@app.route('/appointments/view/<int:id>')
def appointment_view(id):
    a=one('''SELECT a.*,p.full_name patient,p.phone patient_phone,p.patient_code,d.full_name doctor,d.phone doctor_phone,dep.department_name,docfee.consultation_fee FROM appointments a JOIN patients p USING(patient_id) JOIN doctors d USING(doctor_id) JOIN departments dep USING(department_id) JOIN doctors docfee USING(doctor_id) WHERE appointment_id=?''',(id,))
    if not a: abort(404)
    return render_template('appointment_details.html',appointment=a,payments=rows('SELECT * FROM payments WHERE appointment_id=?',(id,)),prescriptions=rows('SELECT * FROM prescriptions WHERE appointment_id=?',(id,)))
@app.route('/appointments/edit/<int:id>',methods=['GET','POST'])
def edit_appointment(id):
    a=one('SELECT * FROM appointments WHERE appointment_id=?',(id,));
    if not a: abort(404)
    if request.method=='POST':
        f=request.form
        try: day=date.fromisoformat(f['appointment_date']).isoformat(); tm=f['appointment_time']; doc=int(f['doctor_id']); dep=int(f['department_id'])
        except (ValueError,KeyError): flash('Invalid appointment details.','danger'); return redirect(url_for('edit_appointment',id=id))
        if f.get('status') not in STATUSES: flash('Select a valid appointment status.','danger')
        elif not one("SELECT department_id FROM departments WHERE department_id=? AND status='Active'",(dep,)): flash('Selected department is inactive.','danger')
        elif not one("SELECT doctor_id FROM doctors WHERE doctor_id=? AND department_id=? AND status='Active'",(doc,dep)): flash('Doctor is inactive or does not belong to selected department.','danger')
        else:
            ok,msg=valid_slot(doc,day,tm,id)
            if not ok: flash(msg,'danger')
            else:
                with db() as con: con.execute("UPDATE appointments SET doctor_id=?,department_id=?,appointment_date=?,appointment_time=?,reason=?,symptoms=?,notes=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE appointment_id=?",(doc,dep,day,tm,f.get('reason'),f.get('symptoms'),f.get('notes'),f.get('status'),id))
                flash('Appointment updated.','success'); return redirect(url_for('appointment_view',id=id))
    return render_template('edit_appointment.html',appointment=a,patients=rows('SELECT * FROM patients ORDER BY full_name'),departments=rows('SELECT * FROM departments ORDER BY department_name'),doctors=rows('SELECT * FROM doctors ORDER BY full_name'))
@app.post('/appointments/status/<int:id>/<status>')
def appointment_status(id,status):
    if status not in STATUSES: abort(400)
    with db() as con: con.execute('UPDATE appointments SET status=?,updated_at=CURRENT_TIMESTAMP WHERE appointment_id=?',(status,id))
    flash(f'Appointment marked {status.lower()}.','success'); return redirect(url_for('appointment_view',id=id))
@app.post('/appointments/cancel/<int:id>')
def cancel_appointment(id): return appointment_status(id,'Cancelled')
@app.post('/appointments/complete/<int:id>')
def complete_appointment(id): return appointment_status(id,'Completed')

@app.get('/api/doctors/<int:department_id>')
def api_doctors(department_id): return jsonify(success=True,doctors=[dict(id=d['doctor_id'],name=d['full_name'],specialization=d['specialization'],fee=d['consultation_fee']) for d in rows("SELECT doctor_id,full_name,specialization,consultation_fee FROM doctors WHERE department_id=? AND status='Active' ORDER BY full_name",(department_id,))])
@app.get('/api/available-slots/<int:doctor_id>/<day>')
def api_slots(doctor_id,day):
    try: parsed=date.fromisoformat(day)
    except ValueError: return jsonify(success=False,slots=[],message='Invalid date.'),400
    sched=rows("SELECT * FROM doctor_schedules WHERE doctor_id=? AND day_of_week=? AND status='Active' ORDER BY start_time",(doctor_id,DAYS[parsed.weekday()]))
    booked={a['appointment_time'] for a in rows("SELECT appointment_time FROM appointments WHERE doctor_id=? AND appointment_date=? AND status!='Cancelled'",(doctor_id,day))}
    slots=[]
    for s in sched:
        start=datetime.strptime(s['start_time'],'%H:%M'); end=datetime.strptime(s['end_time'],'%H:%M'); cur=start
        while cur+timedelta(minutes=s['slot_duration'])<=end:
            t=cur.strftime('%H:%M'); slots.append({'time':t,'available':t not in booked}); cur+=timedelta(minutes=s['slot_duration'])
    return jsonify(success=True,slots=slots)
@app.get('/api/patient/<int:patient_id>')
def api_patient(patient_id):
    p=one('SELECT patient_id,patient_code,full_name,phone,email FROM patients WHERE patient_id=?',(patient_id,))
    return (jsonify(success=True,patient=dict(p)) if p else (jsonify(success=False,message='Patient not found.'),404))
@app.get('/api/appointments/today')
def api_today(): return jsonify(success=True,appointments=[dict(a) for a in rows('SELECT appointment_code,appointment_time,status FROM appointments WHERE appointment_date=? ORDER BY appointment_time',(date.today().isoformat(),))])

@app.route('/payments')
def payments(): return render_template('payments.html',payments=rows('SELECT p.*,a.appointment_code,pt.full_name patient,d.full_name doctor FROM payments p JOIN appointments a USING(appointment_id) JOIN patients pt ON p.patient_id=pt.patient_id JOIN doctors d USING(doctor_id) ORDER BY payment_date DESC,payment_id DESC'))
@app.route('/payments/view/<int:id>')
def payment_view(id):
    payment=one('SELECT pay.*,a.appointment_code,a.appointment_date,a.appointment_time,pt.full_name patient,pt.patient_code,d.full_name doctor,dep.department_name FROM payments pay JOIN appointments a USING(appointment_id) JOIN patients pt ON pay.patient_id=pt.patient_id JOIN doctors d USING(doctor_id) JOIN departments dep USING(department_id) WHERE payment_id=?',(id,))
    if not payment: abort(404)
    return render_template('payment_receipt.html',payment=payment)
@app.route('/payments/add',methods=['GET','POST'])
def add_payment():
    if request.method=='POST':
        f=request.form
        try: amt=float(f.get('amount','0')); aid=int(f.get('appointment_id','0'))
        except (ValueError,TypeError): amt=0; aid=0
        a=one('SELECT * FROM appointments WHERE appointment_id=?',(aid,))
        if not a: flash('Select a valid appointment.','danger')
        elif not math.isfinite(amt) or amt<=0: flash('Payment amount must be greater than zero.','danger')
        elif f.get('payment_mode') not in ['Cash','UPI','Card','Bank Transfer']: flash('Select a valid payment mode.','danger')
        elif f.get('payment_status') not in ['Paid','Pending','Refunded']: flash('Select a valid payment status.','danger')
        elif not valid_iso_date(f.get('payment_date') or date.today().isoformat()): flash('Enter a valid payment date.','danger')
        else:
            with db() as con: con.execute('INSERT INTO payments(appointment_id,patient_id,payment_date,amount,payment_mode,transaction_reference,payment_status) VALUES(?,?,?,?,?,?,?)',(aid,a['patient_id'],f.get('payment_date') or date.today().isoformat(),amt,f['payment_mode'],f.get('transaction_reference'),f.get('payment_status','Paid')))
            flash('Payment recorded successfully.','success'); return redirect(url_for('payments'))
    return render_template('add_payment.html',appointments=rows('SELECT a.*,p.full_name patient,d.full_name doctor,d.consultation_fee FROM appointments a JOIN patients p USING(patient_id) JOIN doctors d USING(doctor_id) ORDER BY appointment_date DESC'))
@app.post('/payments/delete/<int:id>')
def delete_payment(id):
    with db() as con: con.execute('DELETE FROM payments WHERE payment_id=?',(id,))
    flash('Payment record removed.','success'); return redirect(url_for('payments'))

@app.route('/prescriptions')
def prescriptions(): return render_template('prescriptions.html',prescriptions=rows('SELECT pr.*,a.appointment_code,d.full_name doctor,p.full_name patient FROM prescriptions pr JOIN appointments a USING(appointment_id) JOIN doctors d USING(doctor_id) JOIN patients p USING(patient_id) ORDER BY pr.created_at DESC'))
@app.route('/prescriptions/add',methods=['GET','POST'])
def add_prescription():
    if request.method=='POST':
        f=request.form; a=one('SELECT * FROM appointments WHERE appointment_id=?',(f.get('appointment_id'),))
        if not a: flash('Select a valid appointment.','danger')
        elif not f.get('diagnosis','').strip(): flash('Diagnosis is required.','danger')
        else:
            with db() as con:
                con.execute('INSERT INTO prescriptions(appointment_id,patient_id,doctor_id,diagnosis,medicines,dosage,duration,instructions) VALUES(?,?,?,?,?,?,?,?)',(a['appointment_id'],a['patient_id'],a['doctor_id'],f['diagnosis'],f.get('medicines'),f.get('dosage'),f.get('duration'),f.get('instructions')))
                con.execute('INSERT INTO medical_records(patient_id,appointment_id,doctor_id,diagnosis,symptoms,treatment,medical_notes) VALUES(?,?,?,?,?,?,?)',(a['patient_id'],a['appointment_id'],a['doctor_id'],f['diagnosis'],a['symptoms'],f.get('medicines'),f.get('instructions')))
                con.execute("UPDATE appointments SET status='Completed',updated_at=CURRENT_TIMESTAMP WHERE appointment_id=?",(a['appointment_id'],))
            flash('Prescription and medical record saved. Appointment completed.','success'); return redirect(url_for('prescriptions'))
    return render_template('add_prescription.html',appointments=rows('SELECT a.*,p.full_name patient,d.full_name doctor FROM appointments a JOIN patients p USING(patient_id) JOIN doctors d USING(doctor_id) ORDER BY appointment_date DESC'))
@app.route('/prescriptions/view/<int:id>')
def prescription_view(id):
    p=one('SELECT pr.*,a.appointment_code,a.appointment_date,a.appointment_time,pt.full_name patient,pt.patient_code,d.full_name doctor,dep.department_name FROM prescriptions pr JOIN appointments a USING(appointment_id) JOIN patients pt USING(patient_id) JOIN doctors d USING(doctor_id) JOIN departments dep USING(department_id) WHERE prescription_id=?',(id,))
    if not p: abort(404)
    return render_template('prescription_details.html',prescription=p)
@app.post('/prescriptions/delete/<int:id>')
def delete_prescription(id):
    with db() as con: con.execute('DELETE FROM prescriptions WHERE prescription_id=?',(id,))
    flash('Prescription removed.','success'); return redirect(url_for('prescriptions'))
@app.route('/medical-records')
def medical_records(): return render_template('medical_records.html',records=rows('SELECT m.*,p.full_name patient,p.patient_code,d.full_name doctor FROM medical_records m JOIN patients p USING(patient_id) LEFT JOIN doctors d USING(doctor_id) ORDER BY m.created_at DESC'))

@app.route('/reports')
def reports():
    period=request.args.get('period','month'); today=date.today()
    if period=='today': start=today.isoformat()
    elif period=='week': start=(today-timedelta(days=today.weekday())).isoformat()
    elif period=='custom': start=request.args.get('date_from') or today.isoformat()
    else: start=today.replace(day=1).isoformat()
    end=request.args.get('date_to') if period=='custom' else today.isoformat()
    if period=='custom':
        if not valid_iso_date(start) or not valid_iso_date(end or '') or start>end:
            flash('Choose a valid custom date range.','warning')
            start=end=today.isoformat()
    aps=rows('SELECT status,COUNT(*) n FROM appointments WHERE appointment_date BETWEEN ? AND ? GROUP BY status',(start,end))
    apstats={s:0 for s in STATUSES}; apstats.update({r['status']:r['n'] for r in aps})
    doctors_report=rows('SELECT d.full_name doctor,dep.department_name,COUNT(a.appointment_id) total,SUM(CASE WHEN a.status="Completed" THEN 1 ELSE 0 END) completed,SUM(CASE WHEN a.status="Cancelled" THEN 1 ELSE 0 END) cancelled FROM doctors d JOIN departments dep USING(department_id) LEFT JOIN appointments a ON a.doctor_id=d.doctor_id AND a.appointment_date BETWEEN ? AND ? GROUP BY d.doctor_id ORDER BY total DESC',(start,end))
    dept_report=rows('SELECT dep.department_name,COUNT(DISTINCT d.doctor_id) doctors,COUNT(a.appointment_id) appointments FROM departments dep LEFT JOIN doctors d USING(department_id) LEFT JOIN appointments a ON a.department_id=dep.department_id AND a.appointment_date BETWEEN ? AND ? GROUP BY dep.department_id ORDER BY appointments DESC',(start,end))
    revenue=one("SELECT COALESCE(SUM(CASE WHEN payment_status='Paid' THEN amount ELSE 0 END),0) paid,COALESCE(SUM(CASE WHEN payment_status='Pending' THEN amount ELSE 0 END),0) pending,COALESCE(SUM(CASE WHEN payment_status='Refunded' THEN amount ELSE 0 END),0) refunded FROM payments WHERE payment_date BETWEEN ? AND ?",(start,end))
    return render_template('reports.html',period=period,start=start,end=end,apstats=apstats,doctors_report=doctors_report,dept_report=dept_report,revenue=revenue,total=sum(apstats.values()))
@app.get('/reports/appointments')
def appointment_report(): return reports()
@app.get('/reports/revenue')
def revenue_report(): return reports()
@app.get('/reports/appointments.csv')
def export_appointments():
    data=rows('SELECT a.appointment_code,a.appointment_date,a.appointment_time,p.full_name patient,d.full_name doctor,dep.department_name,a.status,a.reason FROM appointments a JOIN patients p USING(patient_id) JOIN doctors d USING(doctor_id) JOIN departments dep USING(department_id) ORDER BY appointment_date DESC')
    output=io.StringIO(); writer=csv.writer(output); writer.writerow(['Appointment','Date','Time','Patient','Doctor','Department','Status','Reason'])
    for r in data: writer.writerow(list(r))
    response=make_response(output.getvalue()); response.headers['Content-Type']='text/csv'; response.headers['Content-Disposition']='attachment; filename=appointment-report.csv'; return response

@app.errorhandler(404)
def not_found(error): return render_template('404.html'),404
@app.errorhandler(500)
def server_error(error): return render_template('500.html'),500

init_db()
if __name__=='__main__': app.run(debug=False,host='127.0.0.1',port=5000)
