from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Student(db.Model):
    """Represents a student with personal info and related records."""
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
        
    goals = db.relationship('Goal', back_populates='student', cascade='all, delete-orphan')
    trial_logs = db.relationship('TrialLog', back_populates='student', cascade='all, delete-orphan')  # NEW RELATIONSHIP

class Goal(db.Model):
    """Represents a goal set for a student, containing objectives."""
    __tablename__ = 'goal'
    goal_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    goal_description = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True)  # NEW
    
    objectives = db.relationship('Objective', back_populates='goal', cascade='all, delete-orphan')
    student = db.relationship('Student', back_populates='goals')

class Objective(db.Model):
    """Represents an objective under a goal with related sessions and trial logs."""
    __tablename__ = 'objective'
    objective_id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.goal_id'), nullable=False)
    objective_description = db.Column(db.String(255), nullable=False)
    with_accuracy = db.Column(db.String(255))
    notes = db.Column(db.Text)  # NEW
    active = db.Column(db.Boolean, default=True)  # NEW
    
    goal = db.relationship('Goal', back_populates='objectives')
    trial_logs = db.relationship('TrialLog', back_populates='objective', cascade='all, delete-orphan')  # NEW RELATIONSHIP

# New TrialLog Table
class TrialLog(db.Model):
    """Represents trial log data for a student on a specific objective and session date."""
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
    # New columns added 2024-06
    independent = db.Column(db.Integer, default=0)
    minimal_support = db.Column(db.Integer, default=0)
    moderate_support = db.Column(db.Integer, default=0)
    maximal_support = db.Column(db.Integer, default=0)
    incorrect_new = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)

    student = db.relationship('Student', back_populates='trial_logs')
    objective = db.relationship('Objective', back_populates='trial_logs')

    # Ordered support levels reused by multiple percentage helpers
    SUPPORT_LEVELS = (
        'independent',
        'minimal_support',
        'moderate_support',
        'maximal_support',
    )

    # Methods for total trials and percentage calculations
    
    def total_trials(self):
        """Calculate the total number of trials recorded."""
        return (
            self.correct_no_support +
            self.correct_visual_cue +
            self.correct_verbal_cue +
            self.correct_visual_verbal_cue +
            self.correct_modeling +
            self.incorrect
        )
    
    def percent_no_support(self):
        """Calculate the percentage of correct trials with no support."""
        total = self.total_trials()
        return round((self.correct_no_support / total) * 100, 1) if total > 0 else 0
    
    def percent_with_1_cue(self):
        """Calculate the percentage of correct trials with up to one cue (no support, visual, or verbal)."""
        total = self.total_trials()
        combined = self.correct_no_support + self.correct_visual_cue + self.correct_verbal_cue
        return round((combined / total) * 100, 1) if total > 0 else 0
    
    def percent_visual_verbal_cues(self):
        """Calculate the percentage of correct trials with visual and/or verbal cues."""
        total = self.total_trials()
        combined = (self.correct_no_support + self.correct_visual_cue + 
                    self.correct_verbal_cue + self.correct_visual_verbal_cue)
        return round((combined / total) * 100, 1) if total > 0 else 0
    
    def percent_with_modeling(self):
        """Calculate the percentage of correct trials including modeling cue."""
        total = self.total_trials()
        combined = (self.correct_no_support + self.correct_visual_cue + 
                    self.correct_verbal_cue + self.correct_visual_verbal_cue + self.correct_modeling)
        return round((combined / total) * 100, 1) if total > 0 else 0

    # System usage checks
    def uses_new_system(self):
        """Return True if any new support columns are > 0 or not None."""
        return any(
            (getattr(self, attr) or 0) > 0
            for attr in [
                "independent", "minimal_support", "moderate_support", "maximal_support", "incorrect_new"
            ]
        )

    def uses_legacy_system(self):
        """Return True if any legacy support columns are > 0 or not None."""
        return any(
            (getattr(self, attr) or 0) > 0
            for attr in [
                "correct_no_support", "correct_visual_cue", "correct_verbal_cue",
                "correct_visual_verbal_cue", "correct_modeling", "incorrect"
            ]
        )

    # New methods for added columns (safe for None)
    def total_trials_new(self):
        """Calculate the total number of trials recorded using new columns."""
        return (
            (self.independent or 0) +
            (self.minimal_support or 0) +
            (self.moderate_support or 0) +
            (self.maximal_support or 0) +
            (self.incorrect_new or 0)
        )

    def percent_independent(self):
        """Calculate the percentage of trials that were independent."""
        total = self.total_trials_new()
        return round(((self.independent or 0) / total) * 100, 1) if total > 0 else 0

    def percent_minimal_support(self):
        """Calculate the percentage of trials with minimal support."""
        total = self.total_trials_new()
        return round(((self.minimal_support or 0) / total) * 100, 1) if total > 0 else 0

    def percent_moderate_support(self):
        """Calculate the percentage of trials with moderate support."""
        total = self.total_trials_new()
        return round(((self.moderate_support or 0) / total) * 100, 1) if total > 0 else 0

    def percent_maximal_support(self):
        """Calculate the percentage of trials with maximal support."""
        total = self.total_trials_new()
        return round(((self.maximal_support or 0) / total) * 100, 1) if total > 0 else 0

    def percent_incorrect_new(self):
        """Calculate the percentage of trials that were incorrect (new)."""
        total = self.total_trials_new()
        return round(((self.incorrect_new or 0) / total) * 100, 1) if total > 0 else 0

    def percent_correct_up_to(self, support_level):
        """
        Return percent correct at or below the specified support level.
        support_level: str, one of 'independent', 'minimal_support', 'moderate_support', 'maximal_support'
        """
        total = self.total_trials_new()
        if total == 0 or support_level not in self.SUPPORT_LEVELS:
            return 0.0
        idx = self.SUPPORT_LEVELS.index(support_level) + 1
        correct_sum = sum((getattr(self, lvl) or 0) for lvl in self.SUPPORT_LEVELS[:idx])
        return round((correct_sum / total) * 100, 1)
    

# Event class: Represents a calendar event for any event type (session, meeting, etc.).
class Event(db.Model):
    """Represents a calendar event for any event type (session, meeting, etc.)."""
    __tablename__ = 'events'

    event_id        = db.Column(db.Integer, primary_key=True)
    student_id      = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=True)  # CHANGED HERE
    event_type      = db.Column(db.String(50), nullable=False, default='Session')
    date_of_session = db.Column(db.Date, nullable=False)
    time_of_start   = db.Column(db.Time, nullable=False)
    time_of_end     = db.Column(db.Time, nullable=False)
    status          = db.Column(db.String(16), nullable=False, default='Scheduled')
    active          = db.Column(db.Boolean, nullable=False, default=True)
    plan_notes      = db.Column(db.String(64))
    makeup_for_event_id = db.Column(db.Integer, db.ForeignKey('events.event_id'), nullable=True)
    is_makeup = db.Column(db.Boolean, default=False)
    makeup_for_event = db.relationship('Event', remote_side=[event_id], backref='makeup_sessions', uselist=False)

    student = db.relationship('Student', backref=db.backref('events', lazy='dynamic'))

    def __repr__(self):
        return f'<Event {self.event_id} ({self.event_type}) – student {self.student_id} on {self.date_of_session}>'


# MonthlyQuota model: Tracks required monthly sessions for a student.
class MonthlyQuota(db.Model):
    __tablename__ = 'monthly_quota'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # format "YYYY-MM"
    required_sessions = db.Column(db.Integer, nullable=False, default=4)

    student = db.relationship('Student', backref=db.backref('monthly_quotas', lazy='dynamic'))


# Activity model: Lookup table of possible activities for SOAP Note and other tools.
class Activity(db.Model):
    """Lookup table of possible activities for SOAP Note and other tools."""
    __tablename__ = 'activity'

    activity_id = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(255), nullable=False, unique=True)
    active      = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f'<Activity {self.name}>'


# SOAP Note model: Represents a saved SOAP note entry linked to a student.
class SoapNote(db.Model):
    """Represents a saved SOAP note entry linked to a student."""
    __tablename__ = 'soap_notes'
    
    soap_note_id = db.Column(db.Integer, primary_key=True)
    student_id   = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    note_date    = db.Column(db.Date, nullable=False, default=db.func.current_date())
    note_text    = db.Column(db.Text, nullable=False)
    created_at   = db.Column(db.DateTime, nullable=False, default=db.func.now())

    # Relationship back to Student
    student      = db.relationship('Student', backref=db.backref('soap_notes', lazy='dynamic'))

class QuarterlyReport(db.Model):
    __tablename__ = 'quarterly_reports'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    quarter = db.Column(db.String(10), nullable=False)  # e.g., "2025-Q4"
    report_text = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship('Student', backref=db.backref('quarterly_reports', lazy='dynamic'))

    def __repr__(self):
        return f"<QuarterlyReport id={self.id} student_id={self.student_id} quarter={self.quarter}>"