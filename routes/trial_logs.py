"""Trial log related routes."""

from flask import request, render_template
from sqlalchemy.orm import joinedload
from . import routes_bp
from models import Student, TrialLog


@routes_bp.route('/student/<int:student_id>/trial_logs')
def student_trial_logs(student_id):
    student = Student.query.get_or_404(student_id)
    trial_logs = (
        TrialLog.query
            .filter_by(student_id=student_id)
            .options(joinedload(TrialLog.objective))
            .order_by(TrialLog.date_of_session.desc())
            .all()
    )

    legacy_logs = [log for log in trial_logs if log.uses_legacy_system()]
    new_logs = [log for log in trial_logs if log.uses_new_system()]

    return render_template(
        'student_trial_logs.html',
        student=student,
        legacy_logs=legacy_logs,
        new_logs=new_logs
    )
