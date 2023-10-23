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
from sqlalchemy import event
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


def current_time_in_bogota():
    local_tz = pytz.timezone("America/Bogota")
    return datetime.now(local_tz)


app = Flask(__name__)
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = "sqlite:///qualifications.db"  # SQLite database URI
db = SQLAlchemy(app)
app.config["SECRET_KEY"] = "RgD0c3ncia16@"
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)
migrate = Migrate(app, db)


class BaseModel(db.Model):
    __abstract__ = True

    created_at = db.Column(db.DateTime, default=current_time_in_bogota)
    updated_at = db.Column(
        db.DateTime, default=current_time_in_bogota, onupdate=current_time_in_bogota
    )
    created_by = db.Column(db.String(50), nullable=True)
    modified_by = db.Column(db.String(50), nullable=True)


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(
        db.DateTime, default=current_time_in_bogota, onupdate=current_time_in_bogota
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    activity_type = db.Column(db.String(128))
    details = db.Column(db.String(512))

    def __repr__(self):
        return f"<ActivityLog {self.activity_type} by User {self.user_id} at {self.timestamp}>"


class Profile(BaseModel):
    __tablename__ = "profile"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False, unique=True)  # Admin or Normal

    users = db.relationship("User", back_populates="profile")

    def __repr__(self):
        return f"<Profile {self.type}>"


class User(BaseModel, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    identificacion = db.Column(db.Integer, nullable=False, unique=True)
    tipo_identificacion = db.Column(db.String(2), nullable=False)
    full_name = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    sexo = db.Column(db.String(10), nullable=False)  # Masculino, Femenino, Otro
    telefono = db.Column(db.String(20), nullable=True)
    direccion_residencia = db.Column(db.String(255), nullable=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profile.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    cohorts = db.relationship("Cohort", back_populates="teacher")
    profile = db.relationship("Profile", back_populates="users")

    @property
    def is_admin(self):
        return self.profile.type.lower() == "admin"

    def __repr__(self):
        return f"<User {self.identificacion}>"


class Year(BaseModel):
    __tablename__ = "year"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False, unique=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    cohorts = db.relationship(
        "Cohort", back_populates="year", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Year {self.name}>"


class Universidad(BaseModel):
    __tablename__ = "universidad"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False, unique=True)

    students = db.relationship("Student", back_populates="universidad")


class Cohort(BaseModel):
    __tablename__ = "cohort"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    # Foreign Keys
    year_id = db.Column(db.Integer, db.ForeignKey("year.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Relationships
    year = db.relationship("Year", back_populates="cohorts")
    teacher = db.relationship("User", back_populates="cohorts")
    students = db.relationship(
        "Student", back_populates="cohort", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Cohort {self.name}>"


class Student(BaseModel):
    __tablename__ = "student"

    id = db.Column(db.Integer, primary_key=True)
    identification = db.Column(db.String(20), nullable=False, unique=True)
    tipo_identificacion = db.Column(db.String(2), nullable=False)  # Nuevo campo
    full_name = db.Column(db.String(50), nullable=False)
    sexo = db.Column(db.String(10), nullable=False)  # New field
    # New field for students only
    telefono = db.Column(db.String(20), nullable=True)  # New field
    direccion_residencia = db.Column(db.String(255), nullable=True)  # New field
    is_active = db.Column(db.Boolean, default=True)

    universidad_id = db.Column(
        db.Integer, db.ForeignKey("universidad.id"), nullable=True
    )

    universidad = db.relationship("Universidad", back_populates="students")

    # Foreign Keys
    cohort_id = db.Column(db.Integer, db.ForeignKey("cohort.id"), nullable=False)

    # Relationships
    cohort = db.relationship("Cohort", back_populates="students")
    grades = db.relationship(
        "Grade", back_populates="student", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Student {self.full_name}>"


class Grade(BaseModel):
    __tablename__ = "grade"

    id = db.Column(db.Integer, primary_key=True)
    teacher_grade = db.Column(db.Float)
    self_evaluation = db.Column(db.Float)
    group_grade = db.Column(db.Float)
    final_grade = db.Column(db.Float)

    # Foreign Keys
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)

    # Relationships
    student = db.relationship("Student", back_populates="grades")

    def __repr__(self):
        return f"<Grade {self.id} for Student {self.student_id}>"


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
        else:
            flash("Solo los administradores pueden usar esta función", "danger")
            return redirect(url_for("dashboard"))

    return wrap


@app.route("/", methods=["GET", "POST"])
def login():
    # Si es una solicitud POST, procesa el formulario de inicio de sesión
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()

        # Verifica si el usuario existe y si la contraseña es correcta
        if user and check_password_hash(user.password, password):
            # Si el usuario está desactivado, muestra un mensaje y redirige al login
            if not user.is_active:
                flash(
                    "Su cuenta ha sido desactivada, si desconoce esta acción, comuníquese con su administrador"
                )
                return redirect(url_for("login"))

            # Si todo está bien, inicia sesión y redirige al dashboard
            login_user(user)
            log_activity(user, "Inicio de sesión")
            return redirect(url_for("dashboard"))
        else:
            flash("Usuario o contraseña incorrectos", "danger")

    # Si es una solicitud GET o si hay un error en el formulario, muestra la página de inicio de sesión
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)


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
            return redirect(url_for("dashboard"))
    return render_template("add_universidad.html")


@app.route("/register", methods=["GET", "POST"])
@admin_required
@login_required
def register():
    if request.method == "POST":
        tipo_identificacion = request.form.get("tipo_identificacion")  # Nuevo campo
        identificacion = request.form.get("identificacion")
        full_name = request.form.get("full_name").upper()
        email = request.form.get("email")
        password = request.form.get("password")
        sexo = request.form.get("sexo")
        telefono = request.form.get("telefono")
        direccion_residencia = request.form.get("direccion_residencia")
        profile_type = request.form.get("profile_type")

        # Verificación adicional para el nuevo campo
        if tipo_identificacion not in ["CC", "TI", "CE", "PA"]:
            flash("Tipo de identificación no válido.", "danger")
            return render_template("register.html")

        # Verifica si el perfil especificado es "admin" o "normal"
        if profile_type.lower() not in ["admin", "normal"]:
            flash(
                'Tipo de perfil no válido. por favor defina si su docente es "administrador" o "normal".',
                "danger",
            )
        else:
            # Obtén el perfil correspondiente desde la base de datos
            profile = Profile.query.filter_by(type=profile_type).first()

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
                    profile=profile,
                    created_by=current_user.full_name,  # Utiliza el campo creado en BaseModel
                )
                db.session.add(new_user)
                db.session.commit()
                log_activity(
                    current_user, "Registro de docente", f"Docente: {full_name}"
                )
                flash("Docente Registrado!!.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("No encontrado, intente nuevamente.", "danger")

    return render_template("register.html")


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
            return redirect(url_for("dashboard"))

    return render_template("add_year.html")


@app.route("/add_cohort", methods=["GET", "POST"])
@login_required
@login_required
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
            return redirect(url_for("dashboard"))

    years = (
        Year.query.all()
    )  # Lista de años para que el usuario elija al crear un cohort
    return render_template("add_cohort.html", years=years)


@app.route("/add_student", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        identification = request.form.get("identification")
        tipo_identificacion = request.form.get("tipo_identificacion")  # Nuevo campo
        full_name = request.form.get("full_name").upper()
        sexo = request.form.get("sexo")
        universidad_id = request.form.get("universidad_id")
        telefono = request.form.get("telefono")
        direccion_residencia = request.form.get("direccion_residencia")
        cohort_id = request.form.get("cohort_id")

        # Verifica si el número de identificación coincide con el del docente en sesión
        if identification == str(current_user.identificacion):
            flash(
                "No puedes registrarte como estudiante en tus propias cohortes.",
                "danger",
            )
            return redirect(url_for("dashboard"))

        # Verificación adicional para el nuevo campo
        if tipo_identificacion not in ["CC", "TI", "CE", "PA"]:
            flash("Tipo de identificación no válido.", "danger")
            return render_template("add_student.html", cohorts=cohorts)

        # Verifica si el estudiante ya está inscrito en el cohorte especificado
        existing_student = Student.query.filter_by(
            identification=identification, cohort_id=cohort_id
        ).first()
        if existing_student:
            flash("El estudiante ya existe en este cohorte!!", "danger")
        else:
            new_student = Student(
                tipo_identificacion=tipo_identificacion,
                identification=identification,
                full_name=full_name,
                sexo=sexo,
                universidad_id=universidad_id,
                telefono=telefono,
                direccion_residencia=direccion_residencia,
                cohort_id=cohort_id,
                created_by=current_user.full_name,
            )
            db.session.add(new_student)
            db.session.commit()
            log_activity(
                current_user,
                "Adición de estudiante",
                f"Estudiante: {full_name}, ID: {identification}",
            )
            flash("Estudiante añadido con exito!", "success")
            return redirect(url_for("dashboard"))
    universidades = Universidad.query.all()
    # Obtiene los cohortes creados por el docente actual
    cohorts = Cohort.query.filter_by(teacher_id=current_user.id).all()
    return render_template(
        "add_student.html", cohorts=cohorts, universidades=universidades
    )


@app.route("/edit_student/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    # 1. Recuperar los datos del estudiante usando student_id
    student = Student.query.get_or_404(student_id)

    # Si se envía el formulario (POST request)
    if request.method == "POST":
        if (student.tipo_identificacion != request.form["tipo_identificacion"]) or (
            student.identification != request.form["identification"]
        ):
            flash("Por favor no modifique la identificación del estudiante", "danger")
            return redirect(url_for("dashboard"))
        else:
            # Aquí puedes agregar validaciones como en el método de agregar estudiante

            # 2. Actualizar los datos del estudiante con los datos del formulario
            student.tipo_identificacion = request.form["tipo_identificacion"]
            student.identification = request.form["identification"]
            student.full_name = request.form["full_name"].upper()
            student.sexo = request.form["sexo"]
            student.universidad_id = request.form["universidad_id"]
            student.telefono = request.form["telefono"]
            student.direccion_residencia = request.form["direccion_residencia"]
            student.cohort_id = request.form["cohort_id"]

            # 3. Actualizar metadatos
            student.modified_by = current_user.full_name
            student.updated_at = datetime.utcnow()

            # Guardar cambios en la base de datos
            db.session.commit()
            log_activity(
                current_user,
                "Edición de estudiante",
                f"Estudiante: {student.full_name}, ID: {student.identification}",
            )
            flash("Datos del estudiante actualizados con éxito!", "success")
            return redirect(url_for("dashboard"))

    # 4. Renderizar la plantilla add_student.html con los datos existentes del estudiante
    universidades = Universidad.query.all()
    cohorts = Cohort.query.filter_by(teacher_id=current_user.id).all()
    return render_template(
        "add_student.html",
        student=student,
        cohorts=cohorts,
        universidades=universidades,
    )


@app.route("/view_students", methods=["GET", "POST"])
@login_required
def view_students():
    if request.method == "POST":
        cohort_id = request.form.get("cohort_id")
        students = Student.query.filter_by(cohort_id=cohort_id).all()
        selected_cohort = Cohort.query.get(cohort_id)
    else:
        students = []
        selected_cohort = None

    # Obtener todos los cohortes y años creados por el docente actual
    cohorts = Cohort.query.filter_by(teacher_id=current_user.id).all()

    return render_template(
        "view_students.html",
        cohorts=cohorts,
        students=students,
        selected_cohort=selected_cohort,
    )


@app.route("/inactive_student/<int:student_id>", methods=["POST"])
@login_required
def inactive_student(student_id):
    student = Student.query.get_or_404(student_id)
    student.is_active = not student.is_active
    student.modified_by = current_user.full_name

    db.session.commit()
    status = "activado" if student.is_active else "desactivado"
    cohort_name = Cohort.query.get(student.cohort_id).name
    log_activity(
        current_user,
        f"Estudiante {status}",
        f"Estudiante: {student.full_name}, Cohorte: {cohort_name}",
    )
    flash(f"Estudiante {status} con éxito.")

    return redirect(url_for("view_students"))


"""@app.route("/delete_student/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):
    # 1. Recuperar el estudiante usando student_id
    student = Student.query.get_or_404(student_id)

    # 2. Eliminar el estudiante de la base de datos
    db.session.delete(student)
    db.session.commit()

    # Mostrar un mensaje de confirmación
    flash("Estudiante eliminado con éxito!", "success")

    # 3. Redireccionar al panel de control o a la lista de estudiantes
    return redirect(url_for("view_students"))"""


@app.route("/add_grade/<int:student_id>", methods=["GET", "POST"])
@login_required
def add_grade(student_id):
    student = Student.query.get(student_id)
    if not student:
        flash("Estudiante no encontrado!.", "danger")
        return redirect(url_for("view_students"))

    grade_entry = Grade.query.filter_by(student_id=student_id).first()

    # Si ya existe una entrada de notas para este estudiante, redirigir a la página de edición.
    if grade_entry:
        return redirect(url_for("edit_grade", student_id=student_id))

    if request.method == "POST":
        try:
            teacher_grade = float(request.form.get("teacher_grade"))
            self_evaluation = float(request.form.get("self_evaluation"))
            group_grade = float(request.form.get("group_grade"))

            final_grade = round((teacher_grade + self_evaluation + group_grade) / 3, 2)
            grade = Grade(
                teacher_grade=teacher_grade,
                self_evaluation=self_evaluation,
                group_grade=group_grade,
                final_grade=final_grade,
                student_id=student_id,
                created_by=current_user.full_name,
            )
            db.session.add(grade)
            db.session.commit()
            log_activity(
                current_user,
                "Adición de calificaciones",
                f"Estudiante: {student.full_name}, Cohorte: {student.cohort.name}, Año: {student.cohort.year.name}, Nota final: {final_grade}",
            )
            flash("Calificaciones añadidas con exito!.", "success")
            return redirect(url_for("view_students"))
        except ValueError:
            flash("Notas inválidas!.", "danger")

    return render_template("add_grade.html", student=student)


@app.route("/edit_grade/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_grade(student_id):
    student = Student.query.get(student_id)
    if not student:
        flash("Estudiante no encontrado!.", "danger")
        return redirect(url_for("view_students"))

    grade_entry = Grade.query.filter_by(student_id=student_id).first()
    if not grade_entry:
        flash("No hay calificaciones para editar a este estudiante!.", "danger")
        return redirect(url_for("view_students"))

    if request.method == "POST":
        try:
            teacher_grade = float(request.form.get("teacher_grade"))
            self_evaluation = float(request.form.get("self_evaluation"))
            group_grade = float(request.form.get("group_grade"))

            final_grade = round((teacher_grade + self_evaluation + group_grade) / 3, 2)

            grade_entry.teacher_grade = teacher_grade
            grade_entry.self_evaluation = self_evaluation
            grade_entry.group_grade = group_grade
            grade_entry.final_grade = final_grade
            grade_entry.modified_by = current_user.full_name
            db.session.commit()
            log_activity(
                current_user,
                "Edición de calificaciones",
                f"Estudiante: {student.full_name}, Cohorte: {student.cohort.name}, Año: {student.cohort.year.name}, Nota final: {final_grade}",
            )
            flash("Edición exitosa!.", "success")
            return redirect(url_for("view_students"))
        except ValueError:
            flash("Notas inválidas!.", "danger")

    return render_template("edit_grade.html", student=student, grade=grade_entry)


@app.route("/verify_password", methods=["POST"])
@login_required
def verify_password():
    password = request.json.get("password")
    if current_user and check_password_hash(current_user.password, password):
        return jsonify(valid=True)
    return jsonify(valid=False)


@app.route(
    "/generate_report/<int:teacher_id>/<int:year_id>/<int:cohort_id>", methods=["POST"]
)
@login_required
def generate_report(teacher_id, year_id, cohort_id):
    especificar_parametros = request.form.get("especificar_parametros")
    parametros = request.form.get("parametros")
    # Recupera la información necesaria de la base de datos
    teacher = User.query.get(teacher_id)
    year = Year.query.get(year_id)
    cohort = Cohort.query.get(cohort_id)
    students = Student.query.filter_by(cohort_id=cohort_id).all()

    # Configura el documento
    filename = f"report_{cohort.name}_{year.name}.pdf"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))

    # Configura estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], alignment=1)
    normal_style = styles["Normal"]
    note_style = ParagraphStyle(
        "Note", parent=styles["Italic"], textColor=colors.red, fontSize=10
    )

    # Genera el contenido
    content = []

    title = f"{cohort.name} - {year.name}"
    content.append(Paragraph(title, title_style))
    content.append(Paragraph(f"Docente: {teacher.full_name}", normal_style))
    content.append(Spacer(1, 12))

    # Tabla de estudiantes y calificaciones
    data = [["Identificacion", "Estudiante", "Nota Final"]]
    for student in students:
        grade = Grade.query.filter_by(student_id=student.id).first()
        final_grade = round(grade.final_grade, 2) if grade else "N/A"
        data.append([student.identification, student.full_name, final_grade])
    if especificar_parametros == "si" and parametros:
        content.append(Paragraph("Parámetros Evaluados:", title_style))
        content.append(Paragraph(parametros, normal_style))
        content.append(Spacer(1, 12))

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

    # Sección de firmas
    content.append(Spacer(1, 24))  # Espaciado incrementado
    content.append(Paragraph("Firmas", title_style))
    for student in students:
        content.append(
            Paragraph(f"{student.full_name}: _______________________", normal_style)
        )
        content.append(Spacer(1, 12))  # Espaciado entre firmas

    # Nota sobre firmas
    content.append(Spacer(1, 24))
    content.append(
        Paragraph(
            "Nota: El estudiante que no firme no tendrá su nota registrada.", note_style
        )
    )

    doc.build(content)

    pdf_data = buffer.getvalue()
    log_activity(
        current_user,
        "Generación de reporte PDF",
        f"Reporte para el cohorte: {cohort.name} del año: {year.name}",
    )

    response = make_response(pdf_data)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename={filename}"
    return response


@app.route("/logout")
@login_required
def logout():
    log_activity(current_user, "Cierre de sesión")
    logout_user()
    return redirect(url_for("login"))


@app.route("/view_logs", methods=['GET', 'POST'])
@admin_required  # Asumiendo que solo los administradores pueden ver los logs
@login_required
def view_logs():
    date_filter = request.form.get('dateFilter')
    teacher_filter = request.form.get('teacherFilter')

    query = db.session.query(ActivityLog, User.full_name).join(User, User.id == ActivityLog.user_id)

    if date_filter:
        query = query.filter(ActivityLog.timestamp == date_filter)
    if teacher_filter:
        query = query.filter(User.full_name == teacher_filter)

    logs = query.order_by(ActivityLog.timestamp.desc()).all()
    teachers = User.query.all()

    return render_template("view_logs.html", logs=logs, teachers=teachers)


@app.route("/create_db")
def create_db():
    db.create_all()

    # Verifica si los perfiles "admin" y "normal" ya existen en la base de datos
    admin_profile = Profile.query.filter_by(type="admin").first()
    normal_profile = Profile.query.filter_by(type="normal").first()

    # Si no existen, créalos
    if not admin_profile:
        admin_profile = Profile(type="admin")
        db.session.add(admin_profile)

    if not normal_profile:
        normal_profile = Profile(type="normal")
        db.session.add(normal_profile)

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

    db.session.commit()

    return "Database created"


if __name__ == "__main__":
    app.run(debug=True)
