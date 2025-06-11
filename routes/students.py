"""Student management routes."""

from flask import request, redirect, url_for, render_template, flash
from . import routes_bp
from models import Student, Goal, Objective, db


@routes_bp.route('/add_student', methods=['GET', 'POST'])
def add_student():
    """Add a new student."""
    if request.method == 'POST':
        first_name       = request.form.get('first_name', '').strip()
        last_name        = request.form.get('last_name', '').strip()
        grade_level      = request.form.get('grade_level', '').strip()
        preferred_name   = request.form.get('preferred_name', '').strip()
        pronouns         = request.form.get('pronoun', '').strip()
        monthly_services = request.form.get('monthly_services', '').strip()

        new_student = Student(
            first_name       = first_name,
            last_name        = last_name,
            grade            = grade_level,
            preferred_name   = preferred_name,
            pronouns         = pronouns,
            monthly_services = monthly_services
        )
        db.session.add(new_student)
        db.session.commit()
        flash('Student added successfully!', 'success')
        return redirect(url_for('routes.index'))
    return render_template('add_student.html')


@routes_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    """Edit an existing student's details, including goals and objectives."""

    student = Student.query.get_or_404(student_id)
    goals = Goal.query.filter_by(student_id=student_id).all()
    objectives = Objective.query.join(Goal).filter(Goal.student_id == student_id).all()

    if request.method == 'POST':
        student.first_name = request.form['first_name']
        student.last_name = request.form['last_name']
        student.grade = request.form['grade_level']
        student.pronouns = request.form['pronoun']
        student.preferred_name = request.form.get('preferred_name', student.preferred_name)
        student.monthly_services = request.form['monthly_services']

        for goal in goals:
            goal_key = f'goal_{goal.goal_id}'
            if goal_key in request.form:
                goal.goal_description = request.form[goal_key]

        for objective in objectives:
            obj_key = f'objective_{objective.objective_id}'
            if obj_key in request.form:
                objective.objective_description = request.form[obj_key]

        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('routes.index'))

    return render_template('edit_student.html', student=student, goals=goals, objectives=objectives)


@routes_bp.route('/delete_student/<int:student_id>')
def delete_student(student_id):
    """Archive (soft-delete) a student by marking them as inactive."""

    student = Student.query.get_or_404(student_id)
    student.active = False
    db.session.commit()
    flash('Student archived (soft-deleted) successfully!', 'success')
    return redirect(url_for('routes.index'))


@routes_bp.route('/students')
def students():
    """List all active students, with optional grade filter."""
    grade_filter = request.args.get('grade')
    if grade_filter:
        students = Student.query.filter_by(active=True, grade=grade_filter).order_by(Student.first_name).all()
    else:
        students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    return render_template('students.html', students=students, grade_filter=grade_filter)


@routes_bp.route('/student/<int:student_id>')
def student_info(student_id):
    """Display detailed information for a single student, including goals and objectives."""
    student = Student.query.get_or_404(student_id)
    goals = Goal.query.filter_by(student_id=student_id).all()
    objectives = Objective.query.join(Goal).filter(Goal.student_id == student_id).all()
    return render_template('student_info.html', student=student, goals=goals, objectives=objectives)


@routes_bp.route('/student_search', methods=['GET'])
def student_search():
    """Search for students by first or last name."""

    query = request.args.get('q')
    students = []
    if query:
        students = Student.query.filter(
            ((Student.first_name.ilike(f'%{query}%')) |
             (Student.last_name.ilike(f'%{query}%'))) &
            (Student.active)
        ).all()
    return render_template('student_search.html', students=students, query=query)
