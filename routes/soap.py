"""Routes related to SOAP notes."""

from flask import request, render_template, redirect, url_for, flash, Response
from datetime import datetime, date
from io import StringIO
import csv
from sqlalchemy import extract

from . import routes_bp
from models import Student, Objective, Goal, Activity, Event, SoapNote, db


@routes_bp.route('/soap_note', methods=['GET', 'POST'])
def soap_note():
    """Generate a SOAP note form and preview."""
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    selected_student_id = request.args.get('student_id', type=int)
    selected_student = Student.query.get(selected_student_id) if selected_student_id else None
    monthly_services = selected_student.monthly_services if selected_student and selected_student.monthly_services else "Not specified"

    objectives = []
    if selected_student_id:
        objectives = Objective.query.join(Goal).filter(Goal.student_id == selected_student_id, Objective.active).all()

    activities = Activity.query.filter_by(active=True).order_by(Activity.name).all()

    if request.method == 'POST':
        s_note = request.form.get('s_note', '')
        o_note = request.form.get('o_note', '')
        a_note = request.form.get('a_note', '')
        p_note = request.form.get('p_note', '')
        full_note = f"S: {s_note}\nO: {o_note}\nA: {a_note}\nP: {p_note}"
        selected_date = datetime.now().date().isoformat()
        return render_template('soap_note_result.html', student_id=selected_student_id, note_date=selected_date, s_note=s_note, o_note=o_note, a_note=a_note, p_note=p_note, full_note=full_note)

    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    return render_template('soap_note.html', students=students, objectives=objectives, months=months, current_month=datetime.now().strftime('%B'), selected_student=selected_student, monthly_services=monthly_services, session_count=0, activities=activities)


@routes_bp.route('/soap_note/add', methods=['POST'])
def add_soap_note():
    """Save a SOAP note generated from the form."""
    student_id = request.form.get('student_id', type=int)
    note_date_str = request.form.get('note_date')
    full_note = request.form.get('full_note', '')
    if not student_id or not full_note:
        flash('Missing required fields; note was not saved.', 'warning')
        return redirect(url_for('routes.soap_note'))

    note_dt = datetime.strptime(note_date_str, '%Y-%m-%d').date() if note_date_str else date.today()
    new_note = SoapNote(student_id=student_id, note_date=note_dt, note_text=full_note)
    db.session.add(new_note)
    db.session.commit()
    flash('SOAP note saved successfully.', 'success')
    return redirect(url_for('routes.view_soap_notes'))


@routes_bp.route('/soap_notes/bulk_add', methods=['GET', 'POST'])
def bulk_add_soap():
    """Quickly add SOAP notes for a selected student/date."""
    students = Student.query.filter_by(active=True).order_by(Student.last_name, Student.first_name).all()
    if request.method == 'POST':
        student_id = request.form.get('student_id', type=int)
        note_date = datetime.strptime(request.form.get('note_date'), '%Y-%m-%d').date()
        note_text = request.form.get('note_text', '').strip()
        if not student_id or not note_text:
            flash('All fields are required.', 'warning')
            return redirect(url_for('routes.bulk_add_soap'))
        new_note = SoapNote(student_id=student_id, note_date=note_date, note_text=note_text)
        db.session.add(new_note)
        db.session.commit()
        flash('SOAP note added.', 'success')
        return redirect(url_for('routes.bulk_add_soap'))
    return render_template('bulk_add_soap.html', students=students)


@routes_bp.route('/soap_notes')
def view_soap_notes():
    """View saved SOAP notes with optional filters."""
    filter_student = request.args.get('filter_student', type=int)
    filter_start_date = request.args.get('start_date')
    filter_end_date = request.args.get('end_date')
    students = Student.query.filter_by(active=True).order_by(Student.last_name, Student.first_name).all()

    query = SoapNote.query
    if filter_student:
        query = query.filter(SoapNote.student_id == filter_student)
    if filter_start_date:
        query = query.filter(SoapNote.note_date >= datetime.strptime(filter_start_date, '%Y-%m-%d').date())
    if filter_end_date:
        query = query.filter(SoapNote.note_date <= datetime.strptime(filter_end_date, '%Y-%m-%d').date())

    soap_notes = query.order_by(SoapNote.note_date.desc()).all()

    return render_template('view_soap_notes.html', soap_notes=soap_notes, students=students, filter_student=filter_student, filter_start_date=filter_start_date, filter_end_date=filter_end_date)


@routes_bp.route('/soap_notes/export')
def export_soap_notes_csv():
    """Export SOAP notes matching current filters as CSV."""
    filter_student = request.args.get('filter_student', type=int)
    filter_start_date = request.args.get('start_date')
    filter_end_date = request.args.get('end_date')

    query = SoapNote.query
    if filter_student:
        query = query.filter(SoapNote.student_id == filter_student)
    if filter_start_date:
        query = query.filter(SoapNote.note_date >= datetime.strptime(filter_start_date, '%Y-%m-%d').date())
    if filter_end_date:
        query = query.filter(SoapNote.note_date <= datetime.strptime(filter_end_date, '%Y-%m-%d').date())

    soap_notes = query.order_by(SoapNote.note_date.desc()).all()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Note ID', 'Student ID', 'Date', 'Note Text'])
    for note in soap_notes:
        cw.writerow([note.soap_note_id, note.student_id, note.note_date.isoformat(), note.note_text.replace('\n', ' ')])
    output = si.getvalue()
    si.close()
    return Response(output, mimetype='text/csv', headers={'Content-disposition': 'attachment; filename=soap_notes.csv'})
