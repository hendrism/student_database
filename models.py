from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

session_objectives_association = db.Table('session_objectives',
    db.Column('session_id', db.Integer, db.ForeignKey('session.session_id'), primary_key=True),
    db.Column('objective_id', db.Integer, db.ForeignKey('objective.objective_id'), primary_key=True)
)

class Goal(db.Model):
    __tablename__ = 'goal'
    goal_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    goal_description = db.Column(db.String(255), nullable=False)
    objectives = db.relationship('Objective', backref='goal')

class Session(db.Model):
    __tablename__ = 'session'
    session_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    date_of_session = db.Column(db.Date, nullable=False)
    time_of_session = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(255))
    plan_notes = db.Column(db.Text)
    objectives = db.relationship('Objective', secondary=session_objectives_association, back_populates='sessions')


class Objective(db.Model):
    __tablename__ = 'objective'
    objective_id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.goal_id'), nullable=False)
    objective_description = db.Column(db.String(255), nullable=False)
    with_accuracy = db.Column(db.String(255))

    sessions = db.relationship('Session',
                               secondary=session_objectives_association,
                               primaryjoin=(objective_id == session_objectives_association.c.objective_id),
                               secondaryjoin=(session_objectives_association.c.session_id == Session.session_id),
                               back_populates='objectives'
                               )

class Student(db.Model):
    __tablename__ = 'student'
    student_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    grade_level = db.Column(db.String(255))
    iep_goals = db.Column(db.Text)
    sessions = db.relationship('Session', backref='student')
    goals = db.relationship('Goal', backref='student')