from datetime import datetime, date
import csv
from io import StringIO

from flask import request, render_template, redirect, url_for, flash, Response
from sqlalchemy import extract

from . import routes_bp
from models import Student, Objective, Goal, Event, Activity, SoapNote, db


@routes_bp.route('/soap_note', methods=['GET', 'POST'])
def soap_note():
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    selected_student_id = request.args.get('student_id', type=int)
    selected_student = Student.query.get(selected_student_id) if selected_student_id else None

    monthly_services = selected_student.monthly_services if selected_student and selected_student.monthly_services else 'Not specified'
    session_count = 0
    if selected_student:
        current_month = datetime.now().month
        current_year = datetime.now().year
        session_count = (
            Event.query
            .filter(
                Event.event_type == 'Session',
                Event.active == True,
                Event.student_id == selected_student_id,
                extract('month', Event.date_of_session) == current_month,
                extract('year', Event.date_of_session) == current_year,
                Event.status.in_(['Completed', 'Excused Absence'])
            )
            .count()
        )

    if selected_student_id:
        objectives = Objective.query.join(Goal).filter(
            Goal.student_id == selected_student_id, Objective.active
        ).all()
    else:
        objectives = []

    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    current_month_str = datetime.now().strftime('%B')
    activities = Activity.query.filter_by(active=True).order_by(Activity.name).all()

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        student = Student.query.get(student_id) if student_id else None
        month = request.form.get('month')
        session_number = request.form.get('session_number')
        total_sessions = request.form.get('total_sessions')
        performance = request.form.get('performance')
        additional_s = request.form.get('additional_S')
        session_type = request.form.get('session_type', 'Individual')
        activity = request.form.get('activity') if request.form.get('activity') != 'Other' else request.form.get('activity_other')
        objective = request.form.get('objective') if request.form.get('objective') != 'Other' else request.form.get('objective_other')
        accuracy = request.form.get('accuracy')
        support_level = request.form.get('support_level')
        if support_level == 'Other':
            support_level = request.form.get('support_level_other', 'with support')
        additional_O = request.form.get('additional_O')
        visual_cues = request.form.getlist('visual_cues')
        visual_cues_other = request.form.get('visual_cues_other', '').strip()
        if visual_cues_other:
            visual_cues.append(visual_cues_other)
        verbal_cues = request.form.getlist('verbal_cues')
        verbal_cues_other = request.form.get('verbal_cues_other', '').strip()
        if verbal_cues_other:
            verbal_cues.append(verbal_cues_other)

        def format_list(items):
            if len(items) == 1:
                return items[0].lower()
            elif len(items) == 2:
                return f"{items[0].lower()} and {items[1].lower()}"
            else:
                return f"{', '.join(item.lower() for item in items[:-1])}, and {items[-1].lower()}"

        visual_cues_formatted = format_list(visual_cues) if visual_cues else 'N/A'
        verbal_cues_formatted = format_list(verbal_cues) if verbal_cues else 'N/A'

        pronoun_map = {
            'he/him': ('he', 'his', 'him'),
            'she/her': ('she', 'her', 'her'),
            'they/them': ('they', 'their', 'them'),
            'other': ('they', 'their', 'them')
        }

        if student and student.pronouns:
            pronoun_key = student.pronouns.lower().strip()
            if pronoun_key not in pronoun_map:
                if 'she' in pronoun_key:
                    pronoun_key = 'she/her'
                elif 'he' in pronoun_key:
                    pronoun_key = 'he/him'
                else:
                    pronoun_key = 'they/them'
        else:
            pronoun_key = 'they/them'

        pronoun_subject, pronoun_possessive, pronoun_object = pronoun_map.get(pronoun_key, ('they', 'their', 'them'))
        verb_be = 'was' if pronoun_subject in ['he', 'she'] else 'were'

        s_note = f"{month} Session {session_number}/{total_sessions}: {student.first_name} attended {pronoun_possessive} {session_type.lower()} speech therapy session. {pronoun_subject.capitalize()} {verb_be} {performance}."
        if additional_s:
            s_note += f" {additional_s}"
        o_note = f"{pronoun_subject.capitalize()} {verb_be} given {activity.lower()}. {pronoun_subject.capitalize()} {verb_be} able to {objective} with {accuracy}% accuracy {support_level}."
        if additional_O:
            o_note += f" {additional_O}"

        if visual_cues and verbal_cues:
            a_note = f"{pronoun_subject.capitalize()} benefited from visual and verbal cues. Visual cues included {visual_cues_formatted}. Verbal cues included {verbal_cues_formatted}."
        elif visual_cues:
            a_note = f"{pronoun_subject.capitalize()} benefited from visual cues. Visual cues included {visual_cues_formatted}."
        elif verbal_cues:
            a_note = f"{pronoun_subject.capitalize()} benefited from verbal cues. Verbal cues included {verbal_cues_formatted}."
        else:
            a_note = f"{pronoun_subject.capitalize()} did not require visual or verbal cues during this session."

        p_note = 'Continue to target IEP goals. -Sean Hendricks, MA CCC-SLP'
        full_note = f"S: {s_note}\nO: {o_note}\nA: {a_note}\nP: {p_note}"
        selected_date = datetime.now().date()
        return render_template(
            'soap_note_result.html',
            student_id=selected_student_id,
            note_date=selected_date.isoformat(),
            s_note=s_note,
            o_note=o_note,
            a_note=a_note,
            p_note=p_note,
            full_note=full_note,
        )

    return render_template(
        'soap_note.html',
        students=students,
        objectives=objectives,
        months=months,
        current_month=current_month_str,
        selected_student=selected_student,
        monthly_services=monthly_services,
        session_count=session_count,
        activities=activities,
    )


@routes_bp.route('/soap_note/add', methods=['POST'])
def add_soap_note():
    student_id = request.form.get('student_id', type=int)
    note_date_str = request.form.get('note_date')
    full_note = request.form.get('full_note', '').strip()

    if not student_id or not full_note:
        flash('Missing required fields; note was not saved.', 'warning')
        return redirect(url_for('routes.soap_note'))

    if note_date_str:
        try:
            note_dt = datetime.strptime(note_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format; note was not saved.', 'danger')
            return redirect(url_for('routes.soap_note'))
    else:
        note_dt = date.today()

    new_note = SoapNote(
        student_id=student_id,
        note_date=note_dt,
        note_text=full_note,
    )
    db.session.add(new_note)
    db.session.commit()

    flash('SOAP note saved successfully.', 'success')
    return redirect(url_for('routes.view_soap_notes'))


@routes_bp.route('/soap_notes/bulk_add', methods=['GET', 'POST'])
def bulk_add_soap():
    students = Student.query.filter_by(active=True).order_by(
        Student.last_name, Student.first_name
    ).all()

    if request.method == 'POST':
        student_id_str = request.form.get('student_id')
        note_date_str = request.form.get('note_date')
        note_text = request.form.get('note_text', '').strip()

        if not student_id_str or not note_date_str or not note_text:
            flash('All fields are required.', 'warning')
            return redirect(url_for('routes.bulk_add_soap'))

        try:
            student_id = int(student_id_str)
        except ValueError:
            flash('Invalid student selection.', 'danger')
            return redirect(url_for('routes.bulk_add_soap'))

        try:
            note_dt = datetime.strptime(note_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash(f'Invalid date format: {note_date_str}', 'danger')
            return redirect(url_for('routes.bulk_add_soap'))

        try:
            new_note = SoapNote(
                student_id=student_id,
                note_date=note_dt,
                note_text=note_text,
            )
            db.session.add(new_note)
            db.session.commit()
            flash(f'Successfully added SOAP note for {note_date_str}.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding SOAP note: {str(e)}', 'danger')

        return redirect(url_for('routes.bulk_add_soap'))

    return render_template('bulk_add_soap.html', students=students)


@routes_bp.route('/soap_notes')
def view_soap_notes():
    filter_student = request.args.get('filter_student', type=int)
    filter_start_date = request.args.get('start_date')
    filter_end_date = request.args.get('end_date')

    students = Student.query.filter_by(active=True).order_by(Student.last_name, Student.first_name).all()
    query = SoapNote.query.join(SoapNote.student)
    if filter_student:
        query = query.filter(SoapNote.student_id == filter_student)
    if filter_start_date:
        try:
            dt1 = datetime.strptime(filter_start_date, '%Y-%m-%d').date()
            query = query.filter(SoapNote.note_date >= dt1)
        except ValueError:
            flash('Invalid start date format.', 'warning')
    if filter_end_date:
        try:
            dt2 = datetime.strptime(filter_end_date, '%Y-%m-%d').date()
            query = query.filter(SoapNote.note_date <= dt2)
        except ValueError:
            flash('Invalid end date format.', 'warning')

    soap_notes = query.order_by(SoapNote.note_date.desc()).all()

    return render_template(
        'view_soap_notes.html',
        soap_notes=soap_notes,
        students=students,
        filter_student=filter_student,
        filter_start_date=filter_start_date,
        filter_end_date=filter_end_date,
    )


@routes_bp.route('/soap_notes/export')
def export_soap_notes_csv():
    filter_student = request.args.get('filter_student', type=int)
    filter_start_date = request.args.get('start_date')
    filter_end_date = request.args.get('end_date')

    query = SoapNote.query.join(SoapNote.student)
    if filter_student:
        query = query.filter(SoapNote.student_id == filter_student)
    if filter_start_date:
        try:
            dt1 = datetime.strptime(filter_start_date, '%Y-%m-%d').date()
            query = query.filter(SoapNote.note_date >= dt1)
        except ValueError:
            pass
    if filter_end_date:
        try:
            dt2 = datetime.strptime(filter_end_date, '%Y-%m-%d').date()
            query = query.filter(SoapNote.note_date <= dt2)
        except ValueError:
            pass

    soap_notes = query.order_by(SoapNote.note_date.desc()).all()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Note ID', 'Student ID', 'Date', 'Student', 'Note Text'])
    for note in soap_notes:
        first_name = note.student.first_name
        anonymized_text = note.note_text.replace(first_name, str(note.student_id))
        full_name = f"{note.student.first_name} {note.student.last_name}"
        cw.writerow([
            note.soap_note_id,
            note.student_id,
            note.note_date.strftime('%Y-%m-%d'),
            full_name,
            anonymized_text.replace('\n', ' '),
        ])
    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-disposition': 'attachment; filename=soap_notes.csv'}
    )
