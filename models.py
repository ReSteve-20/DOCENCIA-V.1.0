from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
import pytz


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

    cohorts = db.relationship("Cohort", back_populates="teacher")
    profile = db.relationship("Profile", back_populates="users")
    especializacion = db.relationship("Especializacion", back_populates="teacher")

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
    email = db.Column(db.String(100), nullable=False, unique=True)
    telefono = db.Column(db.String(20), nullable=True)  # New field
    direccion_residencia = db.Column(db.String(255), nullable=True)  # New field
    password = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    

    universidad_id = db.Column(
        db.Integer, db.ForeignKey("universidad.id"), nullable=True
    )
    

    universidad = db.relationship("Universidad", back_populates="students")

    # Foreign Keys
    cohort_id = db.Column(db.Integer, db.ForeignKey("cohort.id"), nullable=True)

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
    

class Especializacion(BaseModel):
    __tablename__ = "especializacion"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    teacher = db.relationship("User", back_populates="especializacion")

    # Relación inversa con Student
        