from datetime import datetime, date, timedelta

from flask import request, render_template, jsonify, redirect, url_for, flash

from . import routes_bp
from models import (
    Student, Goal, Objective, TrialLog, Event, db
)


@routes_bp.route('/')
def index():
    """Dashboard landing page with summary metrics and upcoming sessions."""
    total_students = Student.query.filter_by(active=True).count()
    total_goals = Goal.query.filter_by(active=True).count()

    today = date.today()
    upcoming_sessions = (
        Event.query
        .filter(
            Event.active.is_(True),
            Event.event_type == 'Session',
            Event.status == 'Scheduled',
            Event.date_of_session >= today
        )
        .order_by(Event.date_of_session, Event.time_of_start)
        .limit(5)
        .all()
    )
    today_str = today.strftime('%Y-%m-%d')
    return render_template(
        'index.html',
        total_students=total_students,
        total_goals=total_goals,
        upcoming_sessions=upcoming_sessions,
        today_str=today_str,
    )


@routes_bp.route('/calendar')
def calendar():
    """Display the calendar page."""
    filter_date = request.args.get('filter_date')
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    return render_template('calendar.html', students=students, filter_date=filter_date)


@routes_bp.route('/api/events')
def api_events():
    """Return JSON list of all active events for the calendar."""
    events = Event.query.filter_by(active=True).all()
    data = []
    for e in events:
        start_dt = datetime.combine(e.date_of_session, e.time_of_start)
        end_dt = datetime.combine(e.date_of_session, e.time_of_end)
        data.append({
            'id': e.event_id,
            'title': f"{e.event_type}" + (f" - {e.student.first_name} {e.student.last_name}" if e.student else ''),
            'start': start_dt.isoformat(),
            'end': end_dt.isoformat(),
            'status': e.status,
            'plan_notes': e.plan_notes,
        })
    return jsonify(data)


@routes_bp.route('/api/events', methods=['POST'])
def create_event():
    """Create new events from posted form data."""
    event_type = request.form.get('event_type', 'Session')
    date_str = request.form['date_of_session']
    start_str = request.form['time_of_start']
    end_str = request.form['time_of_end']
    status = request.form.get('status', 'Scheduled')
    plan_notes = request.form.get('plan_notes', '')

    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    start_obj = datetime.strptime(start_str, '%H:%M').time()
    end_obj = datetime.strptime(end_str, '%H:%M').time()

    events_created = 0

    if event_type == 'Session':
        student_ids = request.form.getlist('student_ids')
        for sid in student_ids:
            ev = Event(
                student_id=int(sid),
                event_type=event_type,
                date_of_session=date_obj,
                time_of_start=start_obj,
                time_of_end=end_obj,
                status=status,
                active=True,
                plan_notes=plan_notes,
            )
            db.session.add(ev)
            events_created += 1
    elif event_type in ('Meeting', 'Assessment'):
        student_id = request.form.get('student_id')
        if not student_id:
            return jsonify({'error': 'Student required for this event type.'}), 400
        ev = Event(
            student_id=int(student_id),
            event_type=event_type,
            date_of_session=date_obj,
            time_of_start=start_obj,
            time_of_end=end_obj,
            status=status,
            active=True,
            plan_notes=plan_notes,
        )
        db.session.add(ev)
        events_created += 1
    else:
        student_id = request.form.get('student_id')
        ev = Event(
            student_id=int(student_id) if student_id else None,
            event_type=event_type,
            date_of_session=date_obj,
            time_of_start=start_obj,
            time_of_end=end_obj,
            status=status,
            active=True,
            plan_notes=plan_notes,
        )
        db.session.add(ev)
        events_created += 1

    db.session.commit()
    return jsonify({'created': events_created}), 201


@routes_bp.route('/api/events/<int:event_id>', methods=['POST'])
def update_event(event_id):
    """Update an existing event."""
    ev = Event.query.get_or_404(event_id)

    if 'student_id' in request.form:
        ev.student_id = request.form['student_id']
    if 'event_type' in request.form:
        ev.event_type = request.form['event_type']
    if 'date_of_session' in request.form:
        ev.date_of_session = datetime.strptime(request.form['date_of_session'], '%Y-%m-%d').date()
    if 'time_of_start' in request.form:
        ev.time_of_start = datetime.strptime(request.form['time_of_start'], '%H:%M').time()
    if 'time_of_end' in request.form:
        ev.time_of_end = datetime.strptime(request.form['time_of_end'], '%H:%M').time()
    if 'status' in request.form:
        ev.status = request.form['status']
    if 'plan_notes' in request.form:
        ev.plan_notes = request.form['plan_notes']

    db.session.commit()
    return '', 200


@routes_bp.route('/sessions')
def sessions():
    """View and filter session events."""
    filter_date = request.args.get('filter_date')
    filter_student = request.args.get('filter_student', type=int)
    filter_status = request.args.get('filter_status')

    students = Student.query.filter_by(active=True).order_by(Student.last_name.asc(), Student.first_name.asc()).all()

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
        students=students,
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
    """Display unupdated 'Scheduled' sessions."""
    sessions = (
        Event.query
        .filter_by(event_type='Session', status='Scheduled', active=True)
        .order_by(Event.date_of_session, Event.time_of_start)
        .all()
    )
    return render_template('scheduled_sessions_pending.html', sessions=sessions)


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
                plan_notes='',
            )
            db.session.add(ev)
        db.session.commit()
        flash(f'Created sessions for {date_str}', 'success')
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
        .filter(Goal.student_id == student_id, Objective.active.is_(True))
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
        objectives=objectives,
    )
