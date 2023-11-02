from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
    jsonify,
    make_response,
)
from flask_sqlalchemy import SQLAlchemy
from flask import render_template, request, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from sqlalchemy import event, func
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from functools import wraps
import pytz
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from datetime import datetime
from models import (
    ActivityLog,
    BaseModel,
    Cohort,
    Grade,
    Profile,
    Especializacion,
    Rotacion,
    Universidad,
    User,
    ParametroCalificacion,
    grade_parametro,
    Year,
    db,
)
import smtplib
from email.message import EmailMessage


app = Flask(__name__)

app.config[
    "SQLALCHEMY_DATABASE_URI"
] = "sqlite:///qualifications.db"  # SQLite database URI

db.init_app(app)
app.config["SECRET_KEY"] = "RgD0c3ncia16@"
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)
migrate = Migrate(app, db)


def send_verification_code(destinatario, pin):
    remitente = "docentesrec@outlook.es"
    mensaje = f"Tu PIN de verificación es: {pin}. Guardalo en un lugar seguro. ¡No pierdas este PIN!"

    email = EmailMessage()
    email["From"] = remitente
    email["To"] = destinatario
    email["Subject"] = "PIN de Verificación"
    email.set_content(mensaje)

    try:
        smtp = smtplib.SMTP("smtp-mail.outlook.com", 587)
        smtp.starttls()
        smtp.login(remitente, "elsgvonvwhvpgdrs")
        smtp.sendmail(remitente, destinatario, email.as_string())
        smtp.quit()
    except smtplib.SMTPException as e:
        print(f"Error al enviar el correo: {e}")
        flash(f"GUARDA ESTE PIN EN UN LUGAR SEGURO {pin}", "info")


def current_time_in_bogota():
    local_tz = pytz.timezone("America/Bogota")
    return datetime.now(local_tz)


def log_activity(user, activity_type, details=None):
    log = ActivityLog(user_id=user.id, activity_type=activity_type, details=details)
    db.session.add(log)
    db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if current_user.is_admin:
            return f(*args, **kwargs)
        if current_user.is_normal:
            flash("Solo los administradores pueden usar esta función", "danger")
            return redirect(url_for("teacher_dashboard"))
        if current_user.is_student:
            flash("Solo los administradores pueden usar esta función", "danger")
            return redirect(url_for("student_dashboard"))

    return wrap


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            if not user.is_active:
                flash(
                    "Su cuenta ha sido desactivada, comuníquese con su administrador",
                    "danger",
                )
                return redirect(url_for("login"))

            login_user(user)
            log_activity(user, "Inicio de sesión")

            if user.is_admin:
                return redirect(url_for("admin_dashboard"))
            elif user.is_student:
                return redirect(url_for("student_dashboard"))
            elif user.is_normal:
                return redirect(url_for("teacher_dashboard"))
        else:
            flash("Usuario o contraseña incorrectos", "danger")

    return render_template("login.html")


@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    # Lógica para la vista del panel de administrador
    return render_template("admin_dashboard.html", user=current_user)


@app.route("/student/dashboard")
@login_required
def student_dashboard():
    # Lógica para la vista del panel de estudiante
    return render_template("student_dashboard.html", user=current_user)


@app.route("/teacher/dashboard")
@login_required
def teacher_dashboard():
    # Lógica para la vista del panel de docente
    return render_template("teacher_dashboard.html", user=current_user)


@app.route("/add_universidad", methods=["GET", "POST"])
@admin_required
@login_required
def add_universidad():
    if request.method == "POST":
        nombre = request.form.get("nombre")
        existing_universidad = Universidad.query.filter_by(nombre=nombre).first()
        if existing_universidad:
            flash("Esta universidad ya existe!", "danger")
        else:
            new_universidad = Universidad(
                nombre=nombre, created_by=current_user.full_name
            )  # Utiliza el campo creado en BaseModel)
            db.session.add(new_universidad)
            db.session.commit()
            log_activity(
                current_user, "Creación de universidad", f"Universidad: {nombre}"
            )
            flash("Universidad agregada con éxito!", "success")
            return redirect(url_for("admin_dashboard"))
    return render_template("add_universidad.html")


@admin_required
@login_required
@app.route("/add_especializacion", methods=["POST", "GET"])
def add_especializacion():
    if request.method == "POST":
        nombre = request.form.get("nombre")

        # Verificar si el nombre ya existe
        existing_especializacion = Especializacion.query.filter_by(
            nombre=nombre
        ).first()
        if existing_especializacion:
            flash("La especialización ya existe.", "danger")
            return redirect(url_for("add_especializacion"))

        # Crear y guardar la nueva especialización
        new_especializacion = Especializacion(nombre=nombre)
        db.session.add(new_especializacion)
        db.session.commit()
        log_activity(
            current_user, "Creación de especializacion", f"Universidad: {nombre}"
        )

        flash("Especialización agregada con éxito.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("add_especializacion.html")


@app.route("/register", methods=["GET", "POST"])
@admin_required
@login_required
def register():
    if request.method == "POST":
        tipo_identificacion = request.form.get("tipo_identificacion")  # Nuevo campo
        identificacion = request.form.get("identificacion")
        full_name = request.form.get("full_name").upper()
        email = request.form.get("email")
        user_with_email = User.query.filter_by(email=email).first()
        if user_with_email:
            flash(
                "El correo electrónico ya está en uso. Por favor, elija otro.", "danger"
            )
            return render_template(
                "register.html", especializaciones=Especializacion.query.all()
            )
        password = request.form.get("password")
        sexo = request.form.get("sexo")
        telefono = request.form.get("telefono")
        direccion_residencia = request.form.get("direccion_residencia")
        profile_id = request.form.get("profile_id")
        pin_security = request.form.get("pin_security")
        especializacion_id = request.form.get("especializacion_id")
        send_verification_code(email, pin_security)
        especializacion = Especializacion.query.filter_by(id=especializacion_id).first()

        if not especializacion:
            flash("Especialización no válida.", "danger")
            return render_template(
                "register.html", especializaciones=Especializacion.query.all()
            )
        # Verificación adicional para el nuevo campo
        if not pin_security or len(pin_security) != 6 or not pin_security.isdigit():
            flash("El PIN de seguridad debe ser un número de 6 dígitos.", "danger")
            return render_template(
                "register.html", especializaciones=Especializacion.query.all()
            )
        if tipo_identificacion not in ["CC", "TI", "CE", "PA"]:
            flash("Tipo de identificación no válido.", "danger")
            return render_template(
                "register.html", especializaciones=Especializacion.query.all()
            )

        # Verifica si el perfil especificado es "admin" o "normal"

        else:
            # Obtén el perfil correspondiente desde la base de datos
            profile = Profile.query.filter_by(id=profile_id).first()

            if profile:
                # Crea un nuevo usuario y asigna el perfil y el creador
                new_user = User(
                    tipo_identificacion=tipo_identificacion,
                    identificacion=identificacion,
                    full_name=full_name,
                    password=generate_password_hash(password, method="sha256"),
                    email=email,
                    sexo=sexo,
                    telefono=telefono,
                    direccion_residencia=direccion_residencia,
                    profile_id=profile_id,
                    especializacion_id=especializacion_id,
                    pin_security=generate_password_hash(pin_security, method="sha256"),
                    created_by=current_user.full_name,  # Utiliza el campo creado en BaseModel
                )
                db.session.add(new_user)
                db.session.commit()
                log_activity(
                    current_user, "Registro de docente", f"Docente: {full_name}"
                )
                flash("Docente Registrado!!.", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash("No encontrado, intente nuevamente.", "danger")
    especializaciones = Especializacion.query.all()
    return render_template("register.html", especializaciones=especializaciones)


@app.route("/admin/docentes", methods=["GET", "POST"])
@login_required
@admin_required  # Asumiendo que ya existe un decorador para verificar si el usuario es administrador.
def manage_teachers():
    ID_ADMIN = 1
    ID_DOCENTE_NORMAL = 2

    if request.method == "POST":
        # Si se envía el formulario para activar/desactivar docente
        if "toggle_active" in request.form:
            teacher_id = request.form.get("toggle_active")
            teacher = User.query.get(teacher_id)
            if teacher:
                if teacher.profile_id == ID_ADMIN:
                    flash("No se puede desactivar a un administrador.")
                else:
                    teacher.is_active = not teacher.is_active
                    teacher.modified_by = current_user.full_name

                    db.session.commit()
                    status = "activado" if teacher.is_active else "desactivado"
                    log_activity(
                        current_user,
                        f"Docente {status}",
                        f"Docente: {teacher.full_name}",
                    )
                    flash(f"Docente {status} con éxito.")

    teachers = User.query.filter_by(profile_id=ID_DOCENTE_NORMAL).all()
    return render_template("manage_teachers.html", teachers=teachers)


@app.route("/admin/estudiantes", methods=["GET", "POST"])
@login_required
@admin_required  # Asumiendo que ya existe un decorador para verificar si el usuario es administrador.
def manage_students():
    ID_ADMIN = 1
    ID_ESTUDIANTE_NORMAL = 3  # Asumiendo que los estudiantes tienen una ID distinta

    if request.method == "POST":
        # Si se envía el formulario para activar/desactivar estudiante
        if "toggle_active" in request.form:
            student_id = request.form.get("toggle_active")
            student = User.query.get(student_id)
            if student:
                if student.profile_id == ID_ADMIN:
                    flash("No se puede desactivar a un administrador.")
                else:
                    student.is_active = not student.is_active
                    student.modified_by = current_user.full_name

                    db.session.commit()
                    status = "activado" if student.is_active else "desactivado"
                    log_activity(
                        current_user,
                        f"Estudiante {status}",
                        f"Estudiante: {student.full_name}",
                    )
                    flash(f"Estudiante {status} con éxito.")

    students = User.query.filter_by(profile_id=ID_ESTUDIANTE_NORMAL).all()
    return render_template("manage_students.html", students=students)


@app.route("/admin/edit_teacher/<int:teacher_id>", methods=["GET", "POST"])
@admin_required
def edit_teacher(teacher_id):
    teacher = User.query.get(teacher_id)
    if not teacher:
        flash("Docente no encontrado.")
        return redirect(url_for("manage_teachers"))

    if request.method == "POST":
        # Actualizar los campos del docente
        teacher.full_name = request.form.get("full_name")
        teacher.email = request.form.get("email")
        teacher.sexo = request.form.get("sexo")
        teacher.telefono = request.form.get("telefono")
        teacher.direccion_residencia = request.form.get("direccion_residencia")

        db.session.commit()
        log_activity(
            current_user,
            "Edición de docente",
            f"Docente ID: {teacher_id}, Nombre: {teacher.full_name}",
        )
        flash("Datos del docente actualizados con éxito.")
        return redirect(url_for("manage_teachers"))

    return render_template("edit_teacher.html", teacher=teacher)


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # Verify if the current password is correct
        if not check_password_hash(current_user.password, current_password):
            flash("Contraseña actual incorrecta", "danger")
        elif new_password != confirm_password:
            flash("Las contraseñas nuevas no coinciden", "danger")
        else:
            # Update the user's password with the new one
            current_user.password = generate_password_hash(
                new_password, method="sha256"
            )
            db.session.commit()
            log_activity(current_user, "Cambio de contraseña")

            flash("Contraseña cambiada con éxito", "success")
            # Redirect user based on their type
            if current_user.is_admin:
                return redirect(url_for("admin_dashboard"))
            elif current_user.is_normal:
                return redirect(url_for("teacher_dashboard"))
            elif current_user.is_student:
                return redirect(url_for("student_dashboard"))

    return render_template("change_password.html")


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")
        new_password = request.form.get("new_password")

        # Buscar el usuario por correo electrónico
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("No existe un usuario con ese correo electrónico.", "danger")
            return redirect(url_for("reset_password"))

        # Verificar si el PIN coincide
        if not check_password_hash(user.pin_security, pin):
            flash("PIN incorrecto. Por favor, inténtalo de nuevo.", "danger")
            return redirect(url_for("reset_password"))

        # Actualizar la contraseña del usuario
        user.password = generate_password_hash(new_password, method="sha256")
        db.session.commit()
        log_activity(user, "Recuperó contraseña")

        flash("Contraseña actualizada con éxito. Ya puede iniciar sesión", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")


@app.route("/add_year", methods=["GET", "POST"])
@login_required
@admin_required
def add_year():
    if request.method == "POST":
        name = request.form.get("name")
        teacher_id = current_user.id

        # Comprobar si el año ya existe
        existing_year = Year.query.filter_by(name=name).first()
        if existing_year:
            flash("Este año ya existe!", "danger")
        else:
            new_year = Year(
                name=name, teacher_id=teacher_id, created_by=current_user.full_name
            )
            db.session.add(new_year)
            db.session.commit()
            log_activity(current_user, "Creación de año", f"Año: {name}")
            flash("Año creado con exito!", "success")
            return redirect(url_for("admin_dashboard"))

    return render_template("add_year.html")


@app.route("/add_cohort", methods=["GET", "POST"])
@login_required
@admin_required
def add_cohort():
    if request.method == "POST":
        name = request.form.get("name")
        year_id = request.form.get("year_id")
        teacher_id = current_user.id

        # Comprobar si el cohort ya existe para este docente en particular
        existing_cohort = Cohort.query.filter_by(
            name=name, year_id=year_id, teacher_id=teacher_id
        ).first()
        if existing_cohort:
            flash("Ya tienes un cohorte con este nombre!.", "danger")
        else:
            new_cohort = Cohort(
                name=name,
                year_id=year_id,
                teacher_id=teacher_id,
                created_by=current_user.full_name,
            )
            db.session.add(new_cohort)
            db.session.commit()
            year_name = Year.query.get(year_id).name
            log_activity(
                current_user,
                "Creación de cohorte",
                f"Cohorte: {name}, Año: {year_name}",
            )
            flash("Cohorte añadido correctamente!.", "success")
            return redirect(url_for("admin_dashboard"))
    years = (
        Year.query.all()
    )  # Lista de años para que el usuario elija al crear un cohort
    return render_template("add_cohort.html", years=years)

@app.route('/delete_cohort/<int:cohort_id>', methods=['POST'])
@admin_required
@login_required
def delete_cohort(cohort_id):
    cohort = Cohort.query.get_or_404(cohort_id)
    if cohort.students:  # Si hay estudiantes asociados al cohorte
        flash('No puedes eliminar un cohorte que tiene estudiantes asociados.', 'danger')
        return redirect(url_for('view_students_admin'))
    else:
        # Asumiendo que no hay otras relaciones que dependan de Cohort, simplemente eliminamos el cohorte.
        # En caso de haber otras relaciones, asegúrate de manejarlas adecuadamente antes de eliminar el cohorte.
        db.session.delete(cohort)
        db.session.commit()
        flash('Cohorte eliminado con éxito.', 'success')
        return redirect(url_for('view_students_admin'))

@app.route("/register_student", methods=["GET", "POST"])
@admin_required
@login_required
def register_student():
    if request.method == "POST":
        tipo_identificacion = request.form.get("tipo_identificacion")
        identificacion = request.form.get("identificacion")
        full_name = request.form.get("full_name").upper()
        email = request.form.get("email")
        user_with_email = User.query.filter_by(email=email).first()
        if user_with_email:
            flash(
                "El correo electrónico ya está en uso. Por favor, elija otro.", "danger"
            )
            return render_template(
                "add_student.html", universidades=Universidad.query.all()
            )
        password = request.form.get("password")
        sexo = request.form.get("sexo")
        telefono = request.form.get("telefono")
        direccion_residencia = request.form.get("direccion_residencia")
        pin_security = request.form.get("pin_security")
        universidad_id = request.form.get("universidad_id")
        send_verification_code(email, pin_security)

        # Verificaciones
        if not pin_security or len(pin_security) != 6 or not pin_security.isdigit():
            flash("El PIN de seguridad debe ser un número de 6 dígitos.", "danger")
            return render_template(
                "add_student.html", universidades=Universidad.query.all()
            )

        if tipo_identificacion not in ["CC", "TI", "CE", "PA"]:
            flash("Tipo de identificación no válido.", "danger")
            return render_template(
                "add_student.html", universidades=Universidad.query.all()
            )

        universidad = Universidad.query.filter_by(id=universidad_id).first()
        if not universidad:
            flash("Universidad no válida.", "danger")
            return render_template(
                "add_student.html", universidades=Universidad.query.all()
            )

        profile = Profile.query.filter_by(id=3).first()  # Estudiante
        if not profile:
            flash("Perfil de estudiante no encontrado.", "danger")
            return render_template(
                "add_student.html", universidades=Universidad.query.all()
            )

        # Creación del usuario
        new_user = User(
            tipo_identificacion=tipo_identificacion,
            identificacion=identificacion,
            full_name=full_name,
            password=generate_password_hash(password, method="sha256"),
            email=email,
            sexo=sexo,
            telefono=telefono,
            direccion_residencia=direccion_residencia,
            profile_id=3,  # Estudiante
            universidad=universidad,
            pin_security=generate_password_hash(pin_security, method="sha256"),
            created_by=current_user.full_name,
        )

        db.session.add(new_user)
        db.session.commit()

        log_activity(current_user, "Registro de Estudiante", f"Estudiante: {full_name}")
        flash("Estudiante Registrado!!.", "success")
        return redirect(url_for("admin_dashboard"))

    universidades = Universidad.query.all()
    return render_template("add_student.html", universidades=universidades)


@app.route("/admin/edit_student/<int:student_id>", methods=["GET", "POST"])
@admin_required
@login_required
def edit_student(student_id):
    student = User.query.get(student_id)
    if not student:
        flash("Estudiante no encontrado.")
        return redirect(url_for("view_students_admin"))

    if request.method == "POST":
        # Actualizar los campos del docente
        student.full_name = request.form.get("full_name")
        student.email = request.form.get("email")
        student.sexo = request.form.get("sexo")
        student.telefono = request.form.get("telefono")
        student.direccion_residencia = request.form.get("direccion_residencia")

        db.session.commit()
        log_activity(
            current_user,
            "Edición de docente",
            f"Estudiante ID: {student_id}, Nombre: {student.full_name}",
        )
        flash("Datos del docente actualizados con éxito.")
        return redirect(url_for("view_students_admin"))

    return render_template("edit_student.html", student=student)


@app.route("/enroll_student", methods=["GET", "POST"])
@login_required
@admin_required
def enroll_student():
    if request.method == "POST":
        student_id = request.form.get("student_id")
        cohort_id = request.form.get("cohort_id")

        student = User.query.get(student_id)
        cohort = Cohort.query.get(cohort_id)

        # Validar si el estudiante existe
        if not student:
            flash("El estudiante enviado no existe.", "error")
            return redirect(url_for("enroll_student"))

        try:
            cohort.enroll_student(student)
            log_activity(
                current_user,
                "Matriculó a",
                f"Estudiante: {student.full_name} al cohorte: {cohort.name}, {cohort.year.name}",
            )
            flash("Estudiante matriculado con éxito!", "success")
        except ValueError as e:
            flash(str(e), "error")

        return redirect(url_for("enroll_student"))

    # Filtrar solo los estudiantes cuyo profile_id es 3
    students = User.query.filter_by(profile_id=3).all()
    cohorts = Cohort.query.all()
    return render_template("enroll_student.html", students=students, cohorts=cohorts)


@app.route("/unenroll_student", methods=["POST"])
@login_required
@admin_required
def unenroll_student():
    student_id = request.form.get("student_id")
    cohort_id = request.form.get("cohort_id")

    student = User.query.get(student_id)
    cohort = Cohort.query.get(cohort_id)

    # Validar si el estudiante existe
    if not student:
        flash("El estudiante enviado no existe.", "error")
        return redirect(url_for("admin_dashboard"))

    grade_entry = Grade.query.filter_by(
        student_id=student.id, cohort_id=cohort.id
    ).first()

    # Check if the student is actually enrolled in the cohort
    if not grade_entry:
        flash("El estudiante no está matriculado en este cohorte.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        # Unenrolling the student by deleting the Grade entry
        db.session.delete(grade_entry)
        db.session.commit()

        log_activity(
            current_user,
            "Desmatriculó a",
            f"Estudiante: {student.full_name} del cohorte: {cohort.name}, {cohort.year.name}",
        )
        flash("Estudiante desmatriculado con éxito!", "success")
    except Exception as e:
        flash(f"Error al desmatricular: {str(e)}", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/view_students_admin", methods=["GET", "POST"])
@login_required
@admin_required
def view_students_admin():
    cohorts = Cohort.query.all()
    students = []
    selected_cohort = None

    if request.method == "POST":
        cohort_id = request.form.get("selected_cohort")
        selected_cohort = Cohort.query.get(cohort_id)

        # Fetching students and their grades for the selected cohort
        grades = Grade.query.filter_by(cohort_id=cohort_id).all()
        for grade in grades:
            # Check if all three grades are present
            if grade.teacher_grade and grade.self_evaluation and grade.group_grade:
                grade.final_grade = (
                    grade.teacher_grade + grade.self_evaluation + grade.group_grade
                ) / 3
                db.session.commit()  # Save the updated final_grade to database

            student_data = {
                "id": grade.student.id,
                "full_name": grade.student.full_name,
                "identificacion": grade.student.identificacion,
                "teacher_grade": grade.teacher_grade,
                "self_evaluation": grade.self_evaluation,
                "group_grade": grade.group_grade,
                "final_grade": grade.final_grade,
            }
            students.append(student_data)

    teacher = selected_cohort.teacher if selected_cohort else None
    return render_template(
        "view_students_admin.html",
        cohorts=cohorts,
        students=students,
        selected_cohort=selected_cohort,
        teacher=teacher,
    )


@app.route("/view_students_teacher", methods=["GET", "POST"])
@login_required  # Asumiendo que ya existe un decorador para verificar si el usuario es administrador.
def view_students_teacher():
    # Filtrando cohortes basado en el docente actual
    cohorts = Cohort.query.filter_by(teacher_id=current_user.id).all()
    students = []
    selected_cohort = None

    if request.method == "POST":
        cohort_id = request.form.get("selected_cohort")
        selected_cohort = Cohort.query.get(cohort_id)

        # Obteniendo estudiantes y sus calificaciones para el cohorte seleccionado.
        grades = Grade.query.filter_by(cohort_id=cohort_id).all()
        for grade in grades:
            if grade.teacher_grade and grade.self_evaluation and grade.group_grade:
                grade.final_grade = (
                    grade.teacher_grade + grade.self_evaluation + grade.group_grade
                ) / 3
                db.session.commit()  # Save the updated final_grade to database
            student_data = {
                "id": grade.student.id,
                "full_name": grade.student.full_name,
                "identificacion": grade.student.identificacion,
                "teacher_grade": grade.teacher_grade,
                "self_evaluation": grade.self_evaluation,
                "group_grade": grade.group_grade,
                "final_grade": grade.final_grade,
            }
            students.append(student_data)

    return render_template(
        "view_students_teacher.html",
        cohorts=cohorts,
        students=students,
        selected_cohort=selected_cohort,
    )


@app.route("/view_cohorts_student", methods=["GET", "POST"])
def view_cohorts_student():
    # Getting cohorts where the student is enrolled
    student_cohorts = current_user.joined_cohorts
    grades = []

    for cohort in student_cohorts:
        grade = Grade.query.filter_by(
            student_id=current_user.id, cohort_id=cohort.id
        ).first()

        # If the student has a grade entry for the cohort
        if grade:
            # Check if all three grades are present
            if (
                grade.teacher_grade is not None
                and grade.self_evaluation is not None
                and grade.group_grade is not None
            ):
                grade.final_grade = (
                    grade.teacher_grade + grade.self_evaluation + grade.group_grade
                ) / 3
                db.session.commit()  # Save the updated final_grade to database
        grades.append(grade)

    combined_data = zip(student_cohorts, grades)
    return render_template("view_cohorts_student.html", combined_data=combined_data)


@app.route("/get_students_by_cohort/<int:cohort_id>")
def get_students_by_cohort(cohort_id):
    cohort = Cohort.query.get(cohort_id)
    students = cohort.students  # Añade esta línea
    return render_template("students_list.html", students=students)


@app.route("/create_rotacion", methods=["GET", "POST"])
@login_required
@admin_required
def create_rotacion():
    if request.method == "POST":
        original_cohort_id = request.form.get("cohort_id")
        teacher_id = request.form.get("teacher_id")
        selected_students_ids = request.form.getlist("students")
        numero_rotacion = int(request.form.get("numero_rotacion"))

        original_cohort = Cohort.query.get(original_cohort_id)
        base_cohort_name = original_cohort.name.split(" R ")[0]

        # Crear un nuevo cohorte basado en la rotación
        new_cohort_name = f"{base_cohort_name} R {numero_rotacion}"
        cohort_exist = Cohort.query.filter_by(
            name=new_cohort_name, year_id=original_cohort.year_id
        ).first()
        if cohort_exist:
            flash("Esta rotación ya existe", 'warning')
            return redirect(url_for("create_rotacion"))
        else:
            new_cohort = Cohort(
                name=new_cohort_name,
                year_id=original_cohort.year_id,
                teacher_id=teacher_id,
            )
            db.session.add(new_cohort)
            db.session.commit()

            # Copiar solo los estudiantes seleccionados del cohorte original al nuevo cohorte
            for student_id in selected_students_ids:
                grade = Grade(student_id=student_id, cohort_id=new_cohort.id)
                db.session.add(grade)
            db.session.commit()

            log_activity(
                current_user,
                f"Rotación creada {new_cohort_name}",
                # f"Estudiante: {user.full_name}, Cohorte: {cohort_name}",
            )

            flash("Rotación creada con éxito.", "success")
            return redirect(url_for("create_rotacion"))

    cohorts = Cohort.query.all()
    teachers = User.query.filter_by(
        profile_id=2
    ).all()  # Asumiendo que 2 es el ID de perfil de docente
    return render_template("create_rotacion.html", cohorts=cohorts, teachers=teachers)


@app.route("/inactive_student/<int:user_id>", methods=["POST"])
@login_required
def inactive_student(student_id):
    student = User.query.get_or_404(student_id)

    # Asegurarse de que el usuario es un estudiante antes de continuar
    if not student.is_student:
        flash("El usuario no es un estudiante.", "danger")
        return redirect(url_for("view_students_admin"))

    if (
        student.grades
    ):  # Usando el atributo 'grades' para verificar si hay notas asociadas
        flash("No puedes inactivar a un estudiante con notas asociadas.", "danger")
        return redirect(url_for("view_students_admin"))

    student.is_active = not student.is_active
    student.modified_by = current_user.full_name

    db.session.commit()
    status = "activado" if student.is_active else "desactivado"
    # cohort_name = Cohort.query.get(user.cohort_id).name if user.cohort_id else "N/A"
    log_activity(
        current_user,
        f"Estudiante {status}",
        # f"Estudiante: {user.full_name}, Cohorte: {cohort_name}",
    )
    flash(f"Estudiante {status} con éxito.")

    return redirect(url_for("view_students_admin"))


@app.route(
    "/student_self_grade/<int:student_id>/<int:cohort_id>", methods=["GET", "POST"]
)
@login_required
def student_self_grade(student_id, cohort_id):
    student = User.query.get(student_id)
    cohort = Cohort.query.get(cohort_id)

    # Verificar que el usuario actual es el estudiante correcto
    if current_user.id != student_id:
        flash("No tienes permiso para acceder a esta página.")
        return redirect(url_for("index"))

    # Verify if the student has already submitted a self-evaluation for this cohort
    existing_grade = Grade.query.filter_by(
        student_id=student_id, cohort_id=cohort_id
    ).first()
    if existing_grade and existing_grade.self_evaluation is not None:
        flash("Ya has realizado tu autoevaluación para este cohorte.", "warning")
        return redirect(url_for("student_dashboard"))

    parameters = ParametroCalificacion.query.all()

    if request.method == "POST":
        grades = []
        for param in parameters:
            grade_value = request.form.get(f"parametro_{param.id}")
            if grade_value:
                grades.append(float(grade_value))
        # Calcular el promedio de las calificaciones
        average_grade = sum(grades) / len(grades) if grades else 0

        # Save the self-evaluation in the database
        if not existing_grade:
            grade_entry = Grade(
                student_id=student_id,
                cohort_id=cohort_id,
                self_evaluation=average_grade,
            )
            db.session.add(grade_entry)
        else:
            existing_grade.self_evaluation = average_grade
        db.session.commit()
        log_activity(
            current_user,
            f"Agregó su autoevaluación, { average_grade } al cohorte { cohort.name } ",
        )

        flash("Autoevaluación realizada con éxito!")
        return redirect(url_for("student_dashboard"))

    return render_template(
        "student_self_grade.html", student=student, cohort=cohort, parameters=parameters
    )


@app.route(
    "/add_teacher_grade/<int:student_id>/<int:cohort_id>", methods=["GET", "POST"]
)
@login_required
def add_teacher_grade(student_id, cohort_id):
    if (
        not current_user.is_normal
    ):  # Asumiendo que los docentes tienen el perfil de "admin"
        flash("Solo los docentes pueden agregar esta calificación.", "danger")
        return redirect(url_for("teacher_dashboard"))

    student = User.query.get(student_id)
    cohort = Cohort.query.get(cohort_id)
    parametros = ParametroCalificacion.query.all()

    # Verificar si ya existe una calificación
    grade = Grade.query.filter_by(student_id=student_id, cohort_id=cohort_id).first()
    if grade and grade.teacher_grade:
        flash("Ya has asignado una calificación a este estudiante.", "warning")
        return redirect(url_for("view_students_teacher"))

    if request.method == "POST":
        total = 0
        total_weight = 0
        for parametro in parametros:
            value = float(request.form.get(f"parametro_{parametro.id}"))
            weight = parametro.peso
            total += value * weight
            total_weight += weight
        final_grade = total / total_weight

        if not grade:
            # Crear una nueva entrada Grade si no existe
            grade = Grade(student_id=student_id, cohort_id=cohort_id)
            db.session.add(grade)

        grade.teacher_grade = final_grade
        db.session.commit()
        log_activity(
            current_user,
            f"Agregó la calificacion, { final_grade } al estudiante { student.full_name } ",
            f" del cohorte {cohort.name}",
        )
        flash("Calificación añadida!", "message")

        return redirect(url_for("view_students_teacher"))

    return render_template(
        "add_teacher_grade.html", student=student, parametros=parametros, cohort=cohort
    )


@app.route("/add_admin_grade/<int:student_id>/<int:cohort_id>", methods=["GET", "POST"])
@login_required
@admin_required
def add_admin_grade(student_id, cohort_id):
    student = User.query.get(student_id)
    parametros = ParametroCalificacion.query.all()

    grade = Grade.query.filter_by(student_id=student_id, cohort_id=cohort_id).first()

    # Check if grade already exists and if the group_grade is already assigned
    if grade and grade.group_grade is not None:
        flash("Ya has asignado una calificación para este estudiante.", "warning")
        return redirect(url_for("view_students_admin"))

    cohort = Cohort.query.get(cohort_id)  # Obtener el cohorte

    if request.method == "POST":
        total = 0
        total_weight = 0
        for parametro in parametros:
            value = float(request.form.get(f"parametro_{parametro.id}"))
            weight = parametro.peso
            total += value * weight
            total_weight += weight
        final_grade = total / total_weight

        # If grade does not exist, initialize it
        if not grade:
            grade = Grade(student_id=student_id, cohort_id=cohort_id)

        grade.group_grade = final_grade

        # Check if the logged-in admin is also the teacher of the cohort
        if current_user.id == cohort.teacher_id:
            grade.teacher_grade = final_grade

        db.session.add(grade)  # This line ensures the grade is added if it didn't exist
        flash("Calificaciones agregadas!.", "sucess")
        db.session.commit()
        log_activity(
            current_user,
            f"Agregó la calificacion, { final_grade } al estudiante { student.full_name } ",
            f" del cohorte {cohort.name}",
        )
        flash("Calificación añadida!", "message")

        return redirect(url_for("view_students_admin"))

    return render_template(
        "add_admin_grade.html", student=student, parametros=parametros, cohort=cohort
    )


@app.route("/add_parametro", methods=["GET", "POST"])
@login_required
@admin_required
def add_parametro():
    if request.method == "POST":
        nombre = request.form.get("nombre")
        peso = float(request.form.get("peso"))
        new_parametro = ParametroCalificacion(nombre=nombre, peso=peso)
        db.session.add(new_parametro)
        db.session.commit()
        log_activity(
            current_user,
            f"Creó el parámetro, { nombre }",
        )
        flash("Calificación añadida!", "message")
        flash("Parámetro añadido con éxito", "sucess")
        return redirect(url_for("add_parametro"))
    parametros = ParametroCalificacion.query.all()
    return render_template("add_parametro.html", parametros=parametros)


@app.route("/verify_password", methods=["POST"])
@login_required
def verify_password():
    password = request.json.get("password")
    if current_user and check_password_hash(current_user.password, password):
        return jsonify(valid=True)
    return jsonify(valid=False)


@app.route("/generate_student_report/<int:student_id>", methods=["GET"])
@login_required
@admin_required
def generate_student_report(student_id):
    student = User.query.get(student_id)
    grades = Grade.query.filter_by(student_id=student_id).all()

    # Configura el documento
    filename = f"report_student_{student.identificacion}.pdf"
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))

    # Configura estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"], alignment=1, spaceAfter=20
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Heading2"], alignment=1, spaceAfter=15
    )
    normal_style = styles["Normal"]

    # Genera el contenido
    content = []

    # Título
    title = f"Reporte Académico de {student.full_name}"
    content.append(Paragraph(title, title_style))

    # Subtítulo: Parámetros de Calificación
    content.append(Paragraph("Parámetros de Calificación", subtitle_style))
    parametros = ParametroCalificacion.query.all()
    for param in parametros:
        content.append(
            Paragraph(f"- {param.nombre} (Peso: {param.peso})", normal_style)
        )
    content.append(Spacer(1, 12))

    # Tabla de calificaciones del estudiante
    data = [
        [
            "Cohorte",
            "Docente",
            "Autoevaluación",
            "Administrador",
            "Nota Final",
            "Docente a Cargo",
        ]
    ]
    for grade in grades:
        cohort = Cohort.query.get(grade.cohort_id)
        teacher = cohort.teacher

        final_grade = (
            round(grade.final_grade, 2)
            if grade and grade.final_grade is not None
            else "N/A"
        )
        teacher_grade = (
            round(grade.teacher_grade, 2)
            if grade and grade.teacher_grade is not None
            else "N/A"
        )
        self_evaluation = (
            round(grade.self_evaluation, 2)
            if grade and grade.self_evaluation is not None
            else "N/A"
        )
        group_grade = (
            round(grade.group_grade, 2)
            if grade and grade.group_grade is not None
            else "N/A"
        )

        data.append(
            [
                cohort.name,
                teacher_grade,
                self_evaluation,
                group_grade,
                final_grade,
                teacher.full_name,
            ]
        )

    table = Table(data)
    table_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.skyblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 14),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]
    )
    table.setStyle(table_style)
    content.append(table)

    # Nota al pie
    nota = "Nota: Las calificaciones presentadas en este reporte son el resultado de una evaluación basada en los parámetros mencionados anteriormente."
    content.append(Spacer(1, 20))
    content.append(Paragraph(nota, normal_style))

    doc.build(content)
    pdf_data = buffer.getvalue()

    response = make_response(pdf_data)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename={filename}"
    log_activity(
        current_user, "Generó reporte individual", f"Estudiante: {student.full_name}"
    )
    return response


@app.route(
    "/generate_report/<int:teacher_id>/<int:year_id>/<int:cohort_id>", methods=["GET"]
)
@login_required
@admin_required
def generate_report(teacher_id, year_id, cohort_id):
    teacher = User.query.get(teacher_id)
    year = Year.query.get(year_id)
    cohort = Cohort.query.get(cohort_id)

    # Verificar que los objetos no sean None
    if not teacher or not year or not cohort:
        return (
            "Error: No se pudo encontrar el docente, año o cohorte especificado.",
            400,
        )

    parametros = ParametroCalificacion.query.all()

    # Fetching students and their grades for the selected cohort
    students_data = []
    grades = Grade.query.filter_by(cohort_id=cohort_id).all()
    for grade in grades:
        # Check if all three grades are present
        if grade.teacher_grade and grade.self_evaluation and grade.group_grade:
            grade.final_grade = (
                grade.teacher_grade + grade.self_evaluation + grade.group_grade
            ) / 3
            db.session.commit()  # Save the updated final_grade to database

        student_data = {
            "id": grade.student.id,
            "full_name": grade.student.full_name,
            "identificacion": grade.student.identificacion,
            "teacher_grade": grade.teacher_grade,
            "self_evaluation": grade.self_evaluation,
            "group_grade": grade.group_grade,
            "final_grade": grade.final_grade,
        }
        students_data.append(student_data)

    # Configura el documento
    filename = f"report_{cohort.name}_{year.name}.pdf"
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))

    # Configura estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"], alignment=1, spaceAfter=20
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Heading2"], alignment=1, spaceAfter=15
    )
    normal_style = styles["Normal"]

    # Genera el contenido
    content = []

    # Título
    title = f"Reporte Académico: {cohort.name} - {year.name}"
    content.append(Paragraph(title, title_style))
    content.append(Paragraph(f"Docente a cargo: {teacher.full_name}", subtitle_style))
    content.append(Spacer(1, 12))

    # Tabla de estudiantes y calificaciones
    data = [["Identificación", "Estudiante", "Nota Final"]]
    for student_data in students_data:
        data.append(
            [
                student_data["identificacion"],
                student_data["full_name"],
                round(student_data["final_grade"], 2)
                if student_data["final_grade"] is not None
                else "N/A",
            ]
        )

    table = Table(data)
    table_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.skyblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 14),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]
    )
    table.setStyle(table_style)
    content.append(table)
    content.append(Spacer(1, 20))

    # Parámetros de calificación
    content.append(Paragraph("Parámetros de Calificación:", subtitle_style))
    for param in parametros:
        content.append(
            Paragraph(f"- {param.nombre} (Peso: {param.peso})", normal_style)
        )
    content.append(Spacer(1, 20))

    # Nota al pie
    nota = "Las calificaciones presentadas en este reporte son el resultado de una evaluación basada en los parámetros mencionados anteriormente."
    content.append(Paragraph(nota, normal_style))

    doc.build(content)
    pdf_data = buffer.getvalue()

    response = make_response(pdf_data)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename={filename}"
    log_activity(current_user, "Generó reporte", f"{cohort.name} {cohort.year.name}")
    return response


@app.route("/logout")
@login_required
def logout():
    log_activity(current_user, "Cierre de sesión")
    logout_user()
    return redirect(url_for("login"))


@app.route("/view_logs", methods=["GET", "POST"])
@admin_required  # Asumiendo que solo los administradores pueden ver los logs
@login_required
def view_logs():
    date_filter = request.form.get("dateFilter")
    teacher_filter = request.form.get("teacherFilter")

    query = db.session.query(ActivityLog, User.full_name).join(
        User, User.id == ActivityLog.user_id
    )

    if date_filter:
        query = query.filter(func.date(ActivityLog.timestamp) == date_filter)
    if teacher_filter:
        query = query.filter(User.full_name == teacher_filter)

    logs = query.order_by(ActivityLog.timestamp.desc()).all()
    teachers = User.query.all()

    return render_template("view_logs.html", logs=logs, teachers=teachers)


@app.route("/create_db")
def create_db():
    db.create_all()

    # Verifica si los perfiles "admin", "normal" y "estudiante" ya existen en la base de datos
    admin_profile = Profile.query.filter_by(type="admin").first()
    normal_profile = Profile.query.filter_by(type="normal").first()
    student_profile = Profile.query.filter_by(type="estudiante").first()

    # Si no existen, créalos
    if not admin_profile:
        admin_profile = Profile(type="admin")
        db.session.add(admin_profile)

    if not normal_profile:
        normal_profile = Profile(type="normal")
        db.session.add(normal_profile)

    if not student_profile:
        student_profile = Profile(type="estudiante")
        db.session.add(student_profile)

    # Puedes establecer un usuario específico como creador de estos perfiles si lo deseas.
    # En este ejemplo, se usa "Admin" como creador.
    session["user_id"] = "Admin"

    # Crea un usuario admin por defecto si aún no existe
    default_admin = User.query.filter_by(email="resistsaw@gmail.com").first()
    if not default_admin:
        new_admin = User(
            tipo_identificacion="CC",
            identificacion=12345,
            full_name="Admin Steve",
            password=generate_password_hash("RgD0c3ncia16@", method="sha256"),
            email="resistsaw@gmail.com",
            sexo="MASCULINO",
            telefono="3006009000",
            direccion_residencia="Street 22h",
            profile=admin_profile,
        )
        db.session.add(new_admin)

    # Crea un usuario estudiante por defecto si aún no existe
    default_student = User.query.filter_by(email="student@example.com").first()
    if not default_student:
        new_student = User(
            tipo_identificacion="CC",
            identificacion=54321,
            full_name="Estudiante Example",
            password=generate_password_hash("Password123", method="sha256"),
            email="student@example.com",
            sexo="MASCULINO",
            telefono="3001234567",
            direccion_residencia="Avenida Principal",
            profile=student_profile,
        )
        db.session.add(new_student)

    db.session.commit()

    return "Database created"


if __name__ == "__main__":
    app.run(debug=True)
