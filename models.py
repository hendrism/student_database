from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, time

db = SQLAlchemy()

# Association table (existing)
session_objectives_association = db.Table(
    'session_objectives',
    db.Column('session_id', db.Integer, db.ForeignKey('session.session_id'), primary_key=True),
    db.Column('objective_id', db.Integer, db.ForeignKey('objective.objective_id'), primary_key=True)
)

class Student(db.Model):
    __tablename__ = 'student'
    student_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(255), nullable=False)
    last_name = db.Column(db.String(255), nullable=False)
    reevaluation_date = db.Column(db.Date)
    annual_review_date = db.Column(db.Date)
    monthly_services = db.Column(db.String(255))
    grade = db.Column(db.String(255))
    preferred_name = db.Column(db.String(255))
    pronouns = db.Column(db.String(50))  # NEW FIELD
    active = db.Column(db.Boolean, default=True)
        
    sessions = db.relationship('Session', back_populates='student', cascade='all, delete-orphan')
    goals = db.relationship('Goal', back_populates='student', cascade='all, delete-orphan')
    trial_logs = db.relationship('TrialLog', back_populates='student', cascade='all, delete-orphan')  # NEW RELATIONSHIP

class Goal(db.Model):
    __tablename__ = 'goal'
    goal_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    goal_description = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)  # NEW
    
    objectives = db.relationship('Objective', back_populates='goal', cascade='all, delete-orphan')
    student = db.relationship('Student', back_populates='goals')

class Objective(db.Model):
    __tablename__ = 'objective'
    objective_id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.goal_id'), nullable=False)
    objective_description = db.Column(db.String(255), nullable=False)
    with_accuracy = db.Column(db.String(255))
    notes = db.Column(db.Text)  # NEW
    active = db.Column(db.Boolean, default=True)  # NEW
    
    goal = db.relationship('Goal', back_populates='objectives')
    sessions = db.relationship('Session', secondary=session_objectives_association, back_populates='objectives')
    trial_logs = db.relationship('TrialLog', back_populates='objective', cascade='all, delete-orphan')  # NEW RELATIONSHIP

class Session(db.Model):
    __tablename__ = 'session'
    session_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    date_of_session = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(255))
    time_of_session = db.Column(db.Time, nullable=False, default=time(9, 0))  # Default to 9:00 AM
    plan_notes = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True)  # New field for archiving

    student = db.relationship('Student', back_populates='sessions')
    objectives = db.relationship('Objective', secondary=session_objectives_association, back_populates='sessions')

# New TrialLog Table
class TrialLog(db.Model):
    __tablename__ = 'trial_log'
    trial_log_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    objective_id = db.Column(db.Integer, db.ForeignKey('objective.objective_id'), nullable=True)
    date_of_session = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    
    correct_no_support = db.Column(db.Integer, default=0)
    correct_visual_cue = db.Column(db.Integer, default=0)
    correct_verbal_cue = db.Column(db.Integer, default=0)
    correct_visual_verbal_cue = db.Column(db.Integer, default=0)
    correct_modeling = db.Column(db.Integer, default=0)
    incorrect = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    
    student = db.relationship('Student', back_populates='trial_logs')
    objective = db.relationship('Objective', back_populates='trial_logs')
    
    # ✅ Add these methods for total trials and percentage calculations
    
    def total_trials(self):
        return (
            self.correct_no_support +
            self.correct_visual_cue +
            self.correct_verbal_cue +
            self.correct_visual_verbal_cue +
            self.correct_modeling +
            self.incorrect
        )
    
    def percent_no_support(self):
        total = self.total_trials()
        return round((self.correct_no_support / total) * 100, 1) if total > 0 else 0
    
    def percent_with_1_cue(self):
        total = self.total_trials()
        combined = self.correct_no_support + self.correct_visual_cue + self.correct_verbal_cue
        return round((combined / total) * 100, 1) if total > 0 else 0
    
    def percent_visual_verbal_cues(self):
        total = self.total_trials()
        combined = (self.correct_no_support + self.correct_visual_cue + 
                    self.correct_verbal_cue + self.correct_visual_verbal_cue)
        return round((combined / total) * 100, 1) if total > 0 else 0
    
    def percent_with_modeling(self):
        total = self.total_trials()
        combined = (self.correct_no_support + self.correct_visual_cue + 
                    self.correct_verbal_cue + self.correct_visual_verbal_cue + self.correct_modeling)
        return round((combined / total) * 100, 1) if total > 0 else 0