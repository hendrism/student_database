"""Reporting routes."""

from flask import request, render_template
from datetime import datetime, date, timedelta
from sqlalchemy import extract
from collections import defaultdict
from calendar import monthrange

from . import routes_bp
from models import Student, Event, MonthlyQuota


@routes_bp.route('/reports')
def reports():
    """Display the main reports page."""
    return render_template('reports.html')


@routes_bp.route('/monthly_sessions_report')
def monthly_sessions_report():
    """Generate a monthly sessions report for all active students."""
    month = request.args.get('month', datetime.now().month, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    sort_by = request.args.get('sort_by', '')

    month_str = f"{year}-{month:02d}"
    first_of_month = date(year, month, 1)
    next_month = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    report_data = []

    for student in students:
        quota_entry = MonthlyQuota.query.filter_by(student_id=student.student_id, month=month_str).first()
        if quota_entry:
            expected_sessions = quota_entry.required_sessions
        else:
            try:
                expected_sessions = int(student.monthly_services)
            except (TypeError, ValueError):
                expected_sessions = 0

        completed_sessions = (
            Event.query
                .filter(
                    Event.student_id == student.student_id,
                    Event.event_type == 'Session',
                    Event.status == 'Completed',
                    Event.is_makeup.is_(False),
                    Event.active.is_(True),
                    extract('month', Event.date_of_session) == month,
                    extract('year',  Event.date_of_session) == year
                )
                .count()
        )

        excused_sessions = (
            Event.query
                .filter(
                    Event.student_id == student.student_id,
                    Event.event_type == 'Session',
                    Event.status == 'Excused Absence',
                    Event.active.is_(True),
                    extract('month', Event.date_of_session) == month,
                    extract('year',  Event.date_of_session) == year
                )
                .count()
        )

        makeup_needed = (
            Event.query
                .filter(
                    Event.student_id == student.student_id,
                    Event.event_type == 'Session',
                    Event.status == 'Makeup Needed',
                    Event.active.is_(True),
                    extract('month', Event.date_of_session) == month,
                    extract('year',  Event.date_of_session) == year
                )
                .count()
        )

        total_makeups = (
            Event.query
                .filter(
                    Event.student_id == student.student_id,
                    Event.event_type == 'Session',
                    Event.status == 'Makeup Needed',
                    Event.active.is_(True),
                    Event.date_of_session < first_of_month
                )
                .count()
        )

        credited = completed_sessions + excused_sessions
        remaining = max(expected_sessions - credited, 0)

        report_data.append({
            'student_name': f"{student.first_name} {student.last_name}",
            'expected_sessions': expected_sessions,
            'completed_sessions': completed_sessions,
            'excused_sessions': excused_sessions,
            'makeup_needed': makeup_needed,
            'remaining_sessions': remaining,
            'total_makeups': total_makeups
        })

    if sort_by == 'student_az':
        report_data.sort(key=lambda x: x['student_name'])
    elif sort_by == 'student_za':
        report_data.sort(key=lambda x: x['student_name'], reverse=True)
    elif sort_by == 'remaining_desc':
        report_data.sort(key=lambda x: x['remaining_sessions'], reverse=True)
    elif sort_by == 'remaining_asc':
        report_data.sort(key=lambda x: x['remaining_sessions'])
    elif sort_by == 'makeups_desc':
        report_data.sort(key=lambda x: x['total_makeups'], reverse=True)
    elif sort_by == 'makeups_asc':
        report_data.sort(key=lambda x: x['total_makeups'])

    return render_template(
        'monthly_sessions_report.html',
        report_data=report_data,
        month=month,
        year=year,
        sort_by=sort_by
    )


@routes_bp.route('/reports/makeup_needed')
def makeup_needed_report():
    """Display report of all Session events with 'Makeup Needed' status."""
    now = datetime.now()
    current_month = now.month
    current_year = now.year

    sort_by = request.args.get('sort_by', '')
    base_query = Event.query.filter_by(
        event_type='Session',
        status='Makeup Needed',
        active=True
    )
    if sort_by == 'date_asc':
        base_query = base_query.order_by(Event.date_of_session.asc(), Event.time_of_start.asc())
    elif sort_by == 'date_desc':
        base_query = base_query.order_by(Event.date_of_session.desc(), Event.time_of_start.asc())
    elif sort_by == 'student_az':
        base_query = base_query.join(Event.student).order_by(Student.last_name.asc(), Student.first_name.asc())
    elif sort_by == 'student_za':
        base_query = base_query.join(Event.student).order_by(Student.last_name.desc(), Student.first_name.desc())
    elif sort_by == 'status_asc':
        base_query = base_query.order_by(Event.status.asc())
    elif sort_by == 'status_desc':
        base_query = base_query.order_by(Event.status.desc())
    else:
        base_query = base_query.order_by(Event.time_of_start.asc())

    all_makeup_needed = base_query.all()
    this_month_makeup_needed = base_query.filter(
        extract('month', Event.date_of_session) == current_month,
        extract('year', Event.date_of_session) == current_year
    ).all()

    return render_template(
        'makeup_needed_report.html',
        all_makeup_needed=all_makeup_needed,
        this_month_makeup_needed=this_month_makeup_needed,
        current_month=current_month,
        current_year=current_year,
        sort_by=sort_by
    )
