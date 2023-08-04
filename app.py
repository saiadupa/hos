from flask import Flask, request, render_template, flash, redirect, url_for
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
from tenacity import retry, stop_after_delay, wait_fixed

app = Flask(__name__)

app.config['SECRET_KEY'] = 'a1b2c3d4e5f6g7h8'
password = 'S@i@@12345'



app.config['MAIL_SERVER'] = 'your_mail_server'
app.config['MAIL_PORT'] = 587 
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_mail_username'
app.config['MAIL_PASSWORD'] = 'your_mail_password'
app.config['MAIL_DEFAULT_SENDER'] = 'default_sender_email'
app.config['MAIL_MAX_EMAILS'] = None
app.config['MAIL_ASCII_ATTACHMENTS'] = False

mail = Mail(app)


@retry(stop=stop_after_delay(30), wait=wait_fixed(1))
def get_db_connection():
    host = os.environ.get('MYSQL_HOST', 'db')
    user = os.environ.get('MYSQL_USER', 'root')
    password = os.environ.get('MYSQL_PASSWORD', 'S@i@@12345')
    
    connection = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
    )
    cursor = connection.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS mydb")
    connection.commit()

    connection.database = 'mydb'
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS User (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(128) NOT NULL,
            doctor BOOLEAN NOT NULL,
            admin BOOLEAN NOT NULL,
            work VARCHAR(100),
            country VARCHAR(100),
            image VARCHAR(255)
        )
    """)
    connection.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Appointments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL,
            date DATE NOT NULL,
            asked_by_id INT NOT NULL,
            doctor_id INT NOT NULL,
            FOREIGN KEY (asked_by_id) REFERENCES User (id),
            FOREIGN KEY (doctor_id) REFERENCES User (id)
        )
    """)
    connection.commit()

    cursor.close()
    return connection

def execute_query(query, values=None, fetch=False):
    connection = get_db_connection()
    cursor = connection.cursor(buffered=True)
    try:
        if values:
            cursor.execute(query, values)
        else:
            cursor.execute(query)
        connection.commit()
        if fetch:
            return cursor.fetchall()
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        cursor.close()
        connection.close()




def insert_record(table_name, columns, values):
    placeholders = ', '.join(['%s'] * len(values))
    query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
    execute_query(query, values)


def fetch_all_records(table_name, doctor=None):
    query = f"SELECT * FROM {table_name}"
    if doctor is not None:
        query += " WHERE doctor = %s"
        values = (doctor,)
    else:
        values = None
    return execute_query(query, values=values, fetch=True)


class User(UserMixin):
    def __init__(self, id, username, email, password, doctor, admin, work, country, image):
        self.id = id
        self.username = username
        self.email = email
        self.password = password
        self.doctor = doctor
        self.admin = admin
        self.work = work
        self.country = country
        self.image = image

    @property
    def unhashed_password(self):
        raise AttributeError('cannot view unhashed password')

    @unhashed_password.setter
    def unhashed_password(self, unhashed_password):
        self.password = generate_password_hash(unhashed_password)

    def check_password(self, unhashed_password):
        return check_password_hash(self.password, unhashed_password)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'home'


@login_manager.user_loader
def load_user(user_id):
    user_data = fetch_one("SELECT * FROM User WHERE id = %s", (user_id,))
    if user_data:
        return User(**user_data)
    return None


@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('home'))


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/add_appointment', methods=['POST', 'GET'])
@login_required
def add_appointment():
    name = request.form['name']
    email = request.form['email']
    date = request.form['date']
    doctor = request.form['doctor']

    insert_record('Appointments', ['name', 'email', 'date', 'asked_by_id', 'doctor_id'],
                  [name, email, date, current_user.id, doctor])

    flash("Successfully added appointment. Kindly check the appointment at Manage.")
    return redirect(url_for('appointment'))


@app.route('/get_users')
@login_required
def get_users():
    users = fetch_all_records('User')
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=True",
                      (current_user.email, current_user.password))
    
    if not owner:
        flash("The provided login is not an admin!")
        return redirect(url_for('home'))
    else:
        return render_template('users.html', users=users)

@app.route('/get_signin')
@login_required
def get_signin():
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=False AND doctor=False",
                      (current_user.email, current_user.password))
    roww = fetch_one("SELECT COUNT(*) FROM Appointments WHERE doctor_id=%s", (current_user.id,))
    
    if not owner:
        flash("Kindly login as a Doctor!")
        return redirect(url_for('home'))
    else:
        return render_template('dashboard.html', roww=roww)


@app.route('/get_signin_doctor')
@login_required
def get_signin_doctor():
    user_man = fetch_all_records('User')
    doc_appoint = fetch_all("SELECT * FROM Appointments WHERE doctor_id=%s", (current_user.id,))
    rows = fetch_one("SELECT COUNT(*) FROM Appointments WHERE doctor_id=%s", (current_user.id,))
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=False AND doctor=True",
                      (current_user.email, current_user.password))
    
    if not owner:
        flash("Kindly login as a patient!")
        return redirect(url_for('home'))
    else:
        return render_template('appointment_recieved.html', appoints=doc_appoint, rows=rows)


@app.route('/get_signin_admin')
@login_required
def get_signin_admin():
    rows = fetch_one("SELECT COUNT(*) FROM User WHERE doctor=0 AND admin=0")
    appoint_rows = fetch_one("SELECT COUNT(*) FROM Appointments")
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=True",
                      (current_user.email, current_user.password))
    
    if not owner:
        flash("The provided login is not an admin!")
        return redirect(url_for('home'))
    else:
        return render_template('admin_dash.html', rows=rows, appoint_rows=appoint_rows)


@app.route('/get_appointment_recieved')
@login_required
def get_appointment_recieved():
    rows = fetch_one("SELECT COUNT(*) FROM Appointments WHERE doctor_id=%s", (current_user.id,))
    doc_appoint = fetch_all("SELECT * FROM Appointments WHERE doctor_id=%s", (current_user.id,))
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=False AND doctor=True",
                      (current_user.email, current_user.password))

    if not owner:
        flash("Kindly login as a patient!")
        return redirect(url_for('home'))
    else:
        return render_template('appointment_recieved.html', appoints=doc_appoint, rows=rows)

@app.route('/dash')
@login_required
def dash():
     return render_template('dash.html')

@app.route('/doctor_dash')
@login_required
def doctor_dash():
    rows = fetch_one("SELECT COUNT(*) FROM Appointments")
    return render_template('doctor_dash.html', rows=rows)

@app.route('/signup')
def get_signup():
    return render_template('signup.html')

@app.route('/signup_doctor')
def get_signup_doctor():
    return render_template('signup_doctor.html')

@app.route('/logindoctor', methods=['POST'])
def logindoctor():
    email = request.form['email']
    password = request.form['password']
    owner = fetch_one("SELECT * FROM User WHERE email=%s", (email,))
    if owner and check_password_hash(owner['password'], password):
        user = User(**owner)
        login_user(user)
        flash("Welcome")
        return redirect(url_for('get_signin_doctor'))
    else:
        flash("Username or password is wrong")
        return redirect(url_for('home'))


@app.route('/profile_doctor', methods=['POST', 'GET'])
@login_required
def profile_doctor():
    rows = fetch_one("SELECT COUNT(*) FROM Appointments")
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND doctor=True",
                      (current_user.email, current_user.password))
    get_usors = fetch_all_records('User')

    if not owner:
        flash('Register or login to access the page')
        return redirect(url_for('home'))
    else:
        return render_template('profile_doctor.html', users=get_usors, rows=rows)
    

@app.route('/register_patient', methods=['POST', 'GET'])
def register_patient():
    username = request.form['username']
    email = request.form['email']
    unhashed_password = request.form['password']
    image = request.form['image']
    work = request.form['work']
    country = request.form['country']
    hashed_password = generate_password_hash(unhashed_password)
    insert_record('User', ['username', 'email', 'password', 'doctor', 'admin', 'work', 'country', 'image'],
                  [username, email, hashed_password, False, False, work, country, image])

    flash("Successfully registered")
    return redirect(url_for('patients'))


@app.route('/register_doctor', methods=['POST', 'GET'])
def register_doctor():
    username = request.form['username']
    email = request.form['email']
    image = request.form['image']
    unhashed_password = request.form['password']
    work = request.form['work']
    country = request.form['country']

    hashed_password = generate_password_hash(unhashed_password)
    insert_record('User', ['username', 'email', 'password', 'doctor', 'admin', 'work', 'country', 'image'],
                  [username, email, hashed_password, True, False, work, country, image])

    flash("Registration Successfull login as  doctor.")
    return redirect(url_for('get_signin_doctor'))


@app.route('/loginpatient', methods=['POST', 'GET'])
def loginpatient():
    email = request.form['email']
    password = request.form['password']
    owner = fetch_one("SELECT * FROM User WHERE email=%s", (email,))
    if owner and check_password_hash(owner['password'], password):
        user = User(**owner)
        login_user(user)
        flash("Welcome")
        return redirect(url_for('get_signin'))
    else:
        flash("Username or password is wrong")
        return redirect(url_for('home'))


@app.route('/loginadmin', methods=['POST'])
def loginadmin():
    email = request.form['email']
    password = request.form['password']
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=True",
                      (email, password))
    if not owner:
        flash("Username or password is wrong")
        return redirect(url_for('home'))
    else:
        login_user(User(**owner))
        flash("Welcome")
        return redirect(url_for('get_signin_admin'))



@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/manage')
def manage():
    roww = fetch_one("SELECT COUNT(*) FROM Appointments WHERE doctor_id=%s", (current_user.id,))
    experties = fetch_all_records('User', doctor=True)
    all_appointees = fetch_all("SELECT * FROM Appointments WHERE asked_by_id=%s", (current_user.id,))
    admin_appointees = fetch_all_records('Appointments')
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=False AND doctor=False",
                      (current_user.email, current_user.password))
    if not owner:
        flash("Kindly login as a patient!")
        return redirect(url_for('home'))
    else:
        return render_template('manage.html', appointees=all_appointees, experts=experties, roww=roww)

@app.route('/appointment')
def appointment():
    roww = fetch_one("SELECT COUNT(*) FROM Appointments WHERE doctor_id=%s", (current_user.id,))
    experties = fetch_all_records('User', doctor=True)
    all_appointees = fetch_all("SELECT * FROM Appointments WHERE asked_by_id=%s", (current_user.id,))
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=False AND doctor=False",
                      (current_user.email, current_user.password))
    if not owner:
        flash("Kindly login as a patient!")
        return redirect(url_for('home'))
    else:
        return render_template('appointment.html', appointees=all_appointees, experts=experties, roww=roww)


@app.route('/get_all_appointments')
@login_required
def get_all_appointments():
    admin_appointments = fetch_all_records('Appointments')
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=True",
                      (current_user.email, current_user.password))
    if not owner:
        flash("The provided login is not an admin!")
        return redirect(url_for('home'))
    else:
        return render_template('get_all_appointments.html', appointees=admin_appointments)



@app.route('/doctors')
def doctors():
    user_doctors = fetch_all_records('User', doctor=True)
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s",
                      (current_user.email, current_user.password))

    if not owner:
        flash("The provided login is not an admin!")
        return redirect(url_for('home'))
    else:
        return render_template('signup_doctor.html', doctors=user_doctors)


@app.route('/patients')
@login_required
def patients():
    rows = fetch_one("SELECT COUNT(*) FROM User WHERE doctor=0 AND admin=0")
    user_patients = fetch_all_records('User', doctor=False)
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=True",
                      (current_user.email, current_user.password))
    if not owner:
        flash("The provided login is not an admin!")
        return redirect(url_for('home'))
    else:
        return render_template('patient.html', patients=user_patients, rows=rows)



@app.route('/change_profile')
@login_required
def change_profile():
    get_usors = fetch_all_records('User')
    owner = fetch_one("SELECT * FROM User WHERE email=%s AND password=%s AND admin=False AND doctor=False",
                      (current_user.email, current_user.password))

    if not owner:
        flash("Kindly login as a Doctor!")
        return redirect(url_for('home'))
    else:
        return render_template('profile.html', users=get_usors)


@app.route('/rating')
@login_required
def rating():
    users = get_users()
    return render_template('rating.html', users=users)


@app.route('/count')
def count():
    rows = fetch_one("SELECT COUNT(*) FROM Appointments")
    return redirect(url_for('home'))


@app.route('/update', methods=['POST'])
def update():
    appointment_id = int(request.form['id'])
    name = request.form['name']
    email = request.form['email']
    date = request.form['date']
    query = "UPDATE Appointments SET name = %s, email = %s, date = %s WHERE id = %s"
    values = (name, email, date, appointment_id)
    execute_query(query, values)
    
    flash("Appointment updated successfully")
    return redirect(url_for('appointment'))


@app.route('/update_profile', methods=['POST'])
def update_profile():
    user_id = int(request.form['id'])
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    work = request.form['work']
    country = request.form['country']
    query = "UPDATE User SET username = %s, email = %s, password = %s, work = %s, country = %s WHERE id = %s"
    values = (username, email, password, work, country, user_id)
    execute_query(query, values)

    flash("Profile updated successfully")
    return redirect(url_for('appointment'))


@app.route('/update_profile_doctor', methods=['POST'])
def update_profile_doctor():
    if request.method == 'POST':
        user_id = int(request.form['id'])
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        work = request.form['work']
        country = request.form['country']
        query = "UPDATE User SET username = %s, email = %s, password = %s, work = %s, country = %s WHERE id = %s"
        values = (username, email, password, work, country, user_id)
        execute_query(query, values)

        flash("Profile updated successfully")
        return redirect(url_for('manage'))


@app.route('/delete/<int:id>/', methods=['GET', 'POST'])
def delete(id):
    query = "DELETE FROM Appointments WHERE id = %s"
    values = (id,)
    execute_query(query, values)

    flash("Appointment Deleted")
    return redirect(url_for('manage'))


@app.route('/delete_user/<int:id>/', methods=['GET', 'POST'])
def delete_user(id):
    query = "DELETE FROM User WHERE id = %s"
    values = (id,)
    execute_query(query, values)

    flash("User Deleted successfully")
    return redirect(url_for('patients'))


@app.route("/messg", methods=['POST'])
def mymessage():
    em = request.form['email']
    mm = request.form['message']
    msg = Message('Hello', sender='nithinsaiadupa@gmail.com', recipients=[em])
    msg.body = mm
    try:
        mail.send(msg)
        flash("Message sent successfully")
    except Exception as e:
        flash(f"Failed to send the message: {str(e)}")

    return redirect(url_for('get_appointment_recieved'))


def fetch_one(query, values=None):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, values)
        row = cursor.fetchone()
    except Exception as e:
        row = None
    finally:
        cursor.close()
        connection.close()
    return row

def fetch_all(query, values=None):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, values)
        rows = cursor.fetchall()
    except Exception as e:
        rows = []
    finally:
        cursor.close()
        connection.close()
    return rows


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
