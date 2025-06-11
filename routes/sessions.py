"""Session-related routes."""

from flask import request, render_template, redirect, url_for, flash
from . import routes_bp
from models import Student, Event, TrialLog, Objective, Goal, db
from datetime import datetime, timedelta
from collections import defaultdict
from calendar import monthrange


@routes_bp.route('/sessions')
def sessions():
    filter_date = request.args.get('filter_date')
    filter_student = request.args.get('filter_student', type=int)
    filter_status = request.args.get('filter_status')

    # Query active students for the student dropdown
    students = Student.query.filter_by(active=True).order_by(Student.last_name.asc(), Student.first_name.asc()).all()

    # Build the base query for sessions
    base_q = Event.query.filter_by(active=True, event_type='Session')
    if filter_date:
        base_q = base_q.filter_by(date_of_session=filter_date)
    if filter_student:
        base_q = base_q.filter_by(student_id=filter_student)
    if filter_status:
        base_q = base_q.filter_by(status=filter_status)

    events = base_q.order_by(Event.time_of_start).all()

    return render_template(
        'sessions.html',
        sessions=events,
        filter_date=filter_date,
        filter_student=filter_student,
        filter_status=filter_status,
        students=students
    )


@routes_bp.route('/bulk_sessions', methods=['GET', 'POST'])
def bulk_sessions():
    """Bulk-create one Session event per student for a chosen date."""
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()

    if request.method == 'POST':
        date_str = request.form['session_date']
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        for student in students:
            time_key = f"time_{student.student_id}"
            status_key = f"status_{student.student_id}"
            start_str = request.form.get(time_key)
            if not start_str:
                continue

            start_obj = datetime.strptime(start_str, '%H:%M').time()
            end_obj = (datetime.combine(date_obj, start_obj) + timedelta(minutes=30)).time()
            status_val = request.form.get(status_key, 'Scheduled')

            ev = Event(
                student_id=student.student_id,
                event_type='Session',
                date_of_session=date_obj,
                time_of_start=start_obj,
                time_of_end=end_obj,
                status=status_val,
                active=True,
                plan_notes=''
            )
            db.session.add(ev)

        db.session.commit()
        flash(f"Created sessions for {date_str}", 'success')
        return redirect(url_for('routes.sessions', filter_date=date_str))

    return render_template('bulk_sessions.html', students=students)


@routes_bp.route('/student/<int:student_id>/sessions')
def student_sessions(student_id):
    student = Student.query.get_or_404(student_id)

    sessions = (
        Event.query
               .filter_by(student_id=student_id, event_type='Session')
               .order_by(Event.date_of_session.desc(), Event.time_of_start)
               .all()
    )

    trial_logs = (
        TrialLog.query
                 .filter_by(student_id=student_id)
                 .order_by(TrialLog.date_of_session.desc())
                 .all()
    )

    objectives = (
        Objective.query
        .join(Goal)
        .filter(Goal.student_id == student_id, Objective.active == True)
        .order_by(Objective.objective_description)
        .all()
    )

    legacy_logs = [log for log in trial_logs if log.uses_legacy_system()]
    new_logs = [log for log in trial_logs if log.uses_new_system()]

    return render_template(
        'student_sessions.html',
        student=student,
        sessions=sessions,
        legacy_logs=legacy_logs,
        new_logs=new_logs,
        objectives=objectives
    )


@routes_bp.route('/makeups_by_month')
def makeups_by_month():
    """Show a matrix of Makeup Needed session counts per student per month."""
    students = Student.query.filter_by(active=True).order_by(Student.last_name, Student.first_name).all()

    months = [
        ("September", 9), ("October", 10), ("November", 11), ("December", 12),
        ("January", 1), ("February", 2), ("March", 3), ("April", 4),
        ("May", 5), ("June", 6)
    ]
    year_start = 2024

    makeups_matrix = defaultdict(lambda: defaultdict(int))

    for student in students:
        for month_name, month_num in months:
            year = year_start if month_num >= 9 else year_start + 1
            first_day = f"{year}-{month_num:02d}-01"
            last_day = f"{year}-{month_num:02d}-{monthrange(year, month_num)[1]}"
            count = (
                Event.query
                .filter_by(student_id=student.student_id, status="Makeup Needed", active=1)
                .filter(Event.date_of_session >= first_day)
                .filter(Event.date_of_session <= last_day)
                .count()
            )
            makeups_matrix[student.student_id][month_name] = count

    return render_template(
        "makeups_by_month.html",
        students=students,
        months=[name for name, _ in months],
        makeups_matrix=makeups_matrix
    )

@routes_bp.route('/archive_session/<int:event_id>', methods=['POST'])
def archive_event(event_id):
    ev = Event.query.get_or_404(event_id)
    ev.active = False
    db.session.commit()
    flash('Event archived successfully!', 'success')
    next_url = request.form.get('next') or url_for('routes.sessions')
    return redirect(next_url)


@routes_bp.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    ev = Event.query.get_or_404(event_id)
    db.session.delete(ev)
    db.session.commit()
    flash('Event deleted successfully!', 'success')
    next_url = request.form.get('next') or url_for('routes.sessions')
    return redirect(next_url)


@routes_bp.route('/update_session_status/<int:event_id>', methods=['POST'])
def update_session_status(event_id):
    ev = Event.query.get_or_404(event_id)
    new_status = request.form.get('status')
    if new_status:
        ev.status = new_status
        db.session.commit()
        flash('Session status updated!', 'success')
    next_url = request.form.get('next') or url_for('routes.sessions')
    return redirect(next_url)


@routes_bp.route('/scheduled_sessions_pending')
def scheduled_sessions_pending():
    """Display unupdated Scheduled sessions."""
    sessions = (
        Event.query
             .filter_by(event_type='Session', status='Scheduled', active=True)
             .order_by(Event.date_of_session, Event.time_of_start)
             .all()
    )

