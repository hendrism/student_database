from flask import request, redirect, url_for, render_template, flash, Blueprint, current_app
from models import Student, Session, Goal, Objective, session_objectives_association, db  # Absolute imports
from datetime import datetime

routes_bp = Blueprint('routes', __name__)

@routes_bp.route('/')
def index():
    students = Student.query.all()
    return render_template('index.html', students=students)

@routes_bp.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        grade_level = request.form['grade_level']
        iep_goals = request.form['iep_goals']

        new_student = Student(first_name=first_name, last_name=last_name, grade_level=grade_level, iep_goals=iep_goals)

        db.session.add(new_student)
        db.session.commit()
        flash('Student added successfully!', 'success')
        return redirect(url_for('routes.index'))
    return render_template('add_student.html')

@routes_bp.route('/sessions')
def sessions():
    sessions_list = Session.query.all()
    return render_template('sessions.html', sessions=sessions_list)

@routes_bp.route('/add_session', methods=['GET', 'POST'])
def add_session():
    students = Student.query.all()
    objectives = Objective.query.all()  # Get all objectives for the form
    if request.method == 'POST':
        student_id = request.form['student_id']
        date_str = request.form['date_of_session']
        time_str = request.form['time_of_session']
        status = request.form['status']
        plan_notes = request.form['plan_notes']
        objective_ids = request.form.getlist('objectives')  # Get selected objective IDs

        # --- Date and Time Conversion ---
        try:
            date_of_session = datetime.strptime(date_str, '%Y-%m-%d').date()  # Correct date format
            time_of_session = datetime.strptime(time_str, '%H:%M').time()    # Correct time format
        except ValueError:
            flash('Invalid date or time format!', 'error')
            return redirect(url_for('routes.add_session'))  # Re-render the form

        new_session = Session(
            student_id=student_id,
            date_of_session=date_of_session,
            time_of_session=time_of_session,
            status=status,
            plan_notes=plan_notes
        )

        db.session.add(new_session)

        # Add selected objectives to the session
        selected_objectives = Objective.query.filter(Objective.objective_id.in_(objective_ids)).all()
        new_session.objectives.extend(selected_objectives)

        db.session.commit()
        flash('Session added successfully!', 'success')
        return redirect(url_for('routes.sessions'))
    return render_template('add_session.html', students=students, objectives=objectives)  # Pass objectives

@routes_bp.route('/edit_session/<int:session_id>', methods=['GET', 'POST'])
def edit_session(session_id):
    session = Session.query.get_or_404(session_id)
    students = Student.query.all()
    all_objectives = Objective.query.all()  # Get all objectives for editing
    if request.method == 'POST':
        date_str = request.form['date_of_session']
        time_str = request.form['time_of_session']

        # --- Date and Time Conversion (Edit) ---
        try:
            session.date_of_session = datetime.strptime(date_str, '%Y-%m-%d').date()
            session.time_of_session = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            flash('Invalid date or time format!', 'error')
            return redirect(url_for('routes.edit_session', session_id=session_id))  # Re-render

        session.student_id = request.form['student_id']
        session.status = request.form['status']
        session.plan_notes = request.form['plan_notes']
        objective_ids = request.form.getlist('objectives')

        # Update objectives for the session
        selected_objectives = Objective.query.filter(Objective.objective_id.in_(objective_ids)).all()
        session.objectives = selected_objectives  # Replace existing objectives

        db.session.commit()
        flash('Session updated successfully!', 'success')
        return redirect(url_for('routes.sessions'))
    return render_template('edit_session.html', session=session, students=students, objectives=all_objectives)


@routes_bp.route('/delete_session/<int:session_id>')
def delete_session(session_id):
    session = Session.query.get_or_404(session_id)
    db.session.delete(session)
    db.session.commit()
    flash('Session deleted successfully!', 'success')
    return redirect(url_for('routes.sessions'))

@routes_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == 'POST':
        student.first_name = request.form['first_name']
        student.last_name = request.form['last_name']
        student.grade_level = request.form['grade_level']
        student.iep_goals = request.form['iep_goals']
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('routes.index'))
    return render_template('edit_student.html', student=student)

@routes_bp.route('/delete_student/<int:student_id>')
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('routes.index'))