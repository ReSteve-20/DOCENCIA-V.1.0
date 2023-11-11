from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
import pytz
from sqlalchemy.orm import validates


db = SQLAlchemy()


def current_time_in_bogota():
    local_tz = pytz.timezone("America/Bogota")
    return datetime.now(local_tz)


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
    pin_security = db.Column(db.String(6), nullable=True)

    # Relaciones
    cohorts = db.relationship("Cohort", back_populates="teacher")
    profile = db.relationship("Profile", back_populates="users")
    universidad_id = db.Column(db.Integer, db.ForeignKey("universidad.id"), nullable=True)
    universidad = db.relationship("Universidad", back_populates="students", lazy="select")
    grades = db.relationship(
        "Grade", back_populates="student", cascade="all, delete-orphan"
    )
    cohort = db.relationship("Cohort", back_populates="students")
    especializacion_id = db.Column(db.Integer, db.ForeignKey("especializacion.id"), nullable=True)
    especializacion = db.relationship("Especializacion", back_populates="docentes")
    joined_cohorts = db.relationship("Cohort", secondary="grade", back_populates="students")

    @property
    def is_admin(self):
        return self.profile.type.lower() == "admin"

    def __repr__(self):
        return f"<User {self.identificacion}>"

    @property
    def is_student(self):
        return self.profile.type.lower() == "estudiante"
    @property
    def is_normal(self):
        return self.profile.type.lower() == "normal"
    
 


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

    students = db.relationship("User", back_populates="universidad")

    def __repr__(self):
        return f"<Universidad {self.nombre}>"




class Cohort(BaseModel):
    __tablename__ = "cohort"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    # Foreign Keys
    year_id = db.Column(db.Integer, db.ForeignKey("year.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Relationships
    year = db.relationship("Year", back_populates="cohorts")
    teacher = db.relationship("User", backref="taught_cohorts")
    students = db.relationship("User", secondary="grade", back_populates="joined_cohorts")
    rotaciones = db.relationship("Rotacion", back_populates="cohort", cascade="all, delete-orphan")

    def enroll_student(self, student):
        """
        Matricula un estudiante en este cohorte.
        """
        # Verificar si el estudiante ya está matriculado en este cohorte
        existing_grade = Grade.query.filter_by(student_id=student.id, cohort_id=self.id).first()
        if existing_grade:
            raise ValueError(f"El estudiante ya está matriculado en el cohorte seleccionado")

        # Crear una nueva entrada en la tabla grade
        new_grade = Grade(student_id=student.id, cohort_id=self.id)
        db.session.add(new_grade)
        db.session.commit()


class Rotacion(BaseModel):
    __tablename__ = "rotacion"

    id = db.Column(db.Integer, primary_key=True)
    numero_rotacion = db.Column(db.Integer, nullable=False)
    
    # Clave foránea para relacionar la rotación con un cohorte
    cohort_id = db.Column(db.Integer, db.ForeignKey("cohort.id"), nullable=False)
    
    # Clave foránea para relacionar la rotación con un docente
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    # Relaciones
    cohort = db.relationship("Cohort", back_populates="rotaciones")
    teacher = db.relationship("User")

    def __repr__(self):
        return f"<Rotacion {self.numero_rotacion} del Cohort {self.cohort_id}>"


    

    def __repr__(self):
        return f"<Cohort {self.name}>"


# Tabla asociativa para la relación muchos-a-muchos
grade_parametro = db.Table(
    'grade_parametro',
    db.Column('grade_id', db.Integer, db.ForeignKey('grade.id'), primary_key=True),
    db.Column('parametro_id', db.Integer, db.ForeignKey('parametro_calificacion.id'), primary_key=True),
    db.Column('valor', db.Float, nullable=False)  # Valor de la calificación para este parámetro
)


class Grade(BaseModel):
    __tablename__ = "grade"

    id = db.Column(db.Integer, primary_key=True)
    teacher_grade = db.Column(db.Float)
    self_evaluation = db.Column(db.Float)
    
    final_grade = db.Column(db.Float)

    # Foreign Keys
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    cohort_id = db.Column(db.Integer, db.ForeignKey("cohort.id"), nullable=False)

    # Define la relación 'student' que apunta a la clase 'User'
    student = db.relationship("User", back_populates="grades")

    def __repr__(self):
        return f"<Grade {self.id} for Student {self.student_id} in Cohort {self.cohort_id}>"


    

class Especializacion(BaseModel):
    __tablename__ = "especializacion"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False, unique=True)

    # Relación inversa para acceder a los docentes desde una especialización
    docentes = db.relationship("User", back_populates="especializacion")

    def __repr__(self):
        return f"<Especializacion {self.nombre}>"
    
class ParametroCalificacion(BaseModel):
    __tablename__ = "parametro_calificacion"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(255), nullable=False, unique=True)
    peso = db.Column(db.Float, default=1.0, nullable=False)  # Peso por defecto es 1.0

    def __repr__(self):
        return f"<ParametroCalificacion {self.nombre}>"

