from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

session_objectives_association = db.Table('session_objectives',  # Database table name is 'session_objectives' (can stay as is)
    db.Column('session_id', db.Integer, db.ForeignKey('sessions.session_id'), primary_key=True),
    db.Column('objective_id', db.Integer, db.ForeignKey('objectives.objective_id'), primary_key=True)
)

class Goal(db.Model):
    goal_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    goal_description = db.Column(db.String(255), nullable=False)
    objectives = db.relationship('Objective', backref='goal')

class Objective(db.Model):
    objective_id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.goal_id'), nullable=False)
    objective_description = db.Column(db.String(255), nullable=False)
    with_accuracy = db.Column(db.String(255))

    sessions = db.relationship('Session',
                               secondary=session_objectives_association,
                               primaryjoin=('Objective.objective_id == session_objectives_association.c.objective_id'),
                               secondaryjoin=('Session.session_id == session_objectives_association.c.session_id'),
                               backref=db.backref('objectives', lazy='dynamic'))

class Session(db.Model):
    session_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    date_of_session = db.Column(db.Date, nullable=False)
    time_of_session = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(255))
    plan_notes = db.Column(db.Text)

    objectives = db.relationship('Objective', secondary=session_objectives_association, backref=db.backref('sessions'))

class Student(db.Model):
    student_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    grade_level = db.Column(db.String(255))
    iep_goals = db.Column(db.Text)

    sessions = db.relationship('Session', backref='student')
    goals = db.relationship('Goal', backref='student')