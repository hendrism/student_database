from datetime import datetime

from flask import request, render_template, redirect, url_for, flash
from sqlalchemy.orm import joinedload

from . import routes_bp
from models import Student, Objective, Goal, TrialLog, db


@routes_bp.route('/trial_log', methods=['GET', 'POST'])
def trial_log():
    """Handle trial log submissions and display objectives for a student."""
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    selected_student_id = request.args.get('student_id')

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        objective_ids = request.form.getlist('objective_ids')
        date_of_session = request.form.get('date_of_session')
        correct_no_support = request.form.get('correct_no_support', type=int, default=0)
        correct_visual_cue = request.form.get('correct_visual_cue', type=int, default=0)
        correct_verbal_cue = request.form.get('correct_verbal_cue', type=int, default=0)
        correct_visual_verbal_cue = request.form.get('correct_visual_verbal_cue', type=int, default=0)
        correct_modeling = request.form.get('correct_modeling', type=int, default=0)
        incorrect = request.form.get('incorrect', type=int, default=0)
        notes = request.form.get('notes', '')

        visual_cues = request.form.getlist('visual_cues')
        visual_cues_other = request.form.get('visual_cues_other', '').strip()
        if visual_cues_other:
            visual_cues.append(visual_cues_other)
        verbal_cues = request.form.getlist('verbal_cues')
        verbal_cues_other = request.form.get('verbal_cues_other', '').strip()
        if verbal_cues_other:
            verbal_cues.append(verbal_cues_other)

        support_text_parts = []
        if visual_cues:
            support_text_parts.append('Visual: ' + ', '.join(visual_cues))
        if verbal_cues:
            support_text_parts.append('Verbal: ' + ', '.join(verbal_cues))
        support_text = 'Supports provided: ' + '; '.join(support_text_parts) + '.'

        full_notes = f"{support_text} {notes}".strip()

        independent = request.form.get('independent', type=int, default=0)
        minimal_support = request.form.get('minimal_support', type=int, default=0)
        moderate_support = request.form.get('moderate_support', type=int, default=0)
        maximal_support = request.form.get('maximal_support', type=int, default=0)
        incorrect_new = request.form.get('incorrect_new', type=int, default=0)

        trial_logs = [
            TrialLog(
                student_id=student_id,
                objective_id=obj_id,
                date_of_session=datetime.strptime(date_of_session, '%Y-%m-%d').date(),
                correct_no_support=correct_no_support,
                correct_visual_cue=correct_visual_cue,
                correct_verbal_cue=correct_verbal_cue,
                correct_visual_verbal_cue=correct_visual_verbal_cue,
                correct_modeling=correct_modeling,
                incorrect=incorrect,
                notes=full_notes,
                independent=independent,
                minimal_support=minimal_support,
                moderate_support=moderate_support,
                maximal_support=maximal_support,
                incorrect_new=incorrect_new,
            )
            for obj_id in objective_ids
        ]
        db.session.bulk_save_objects(trial_logs)
        db.session.commit()
        flash('Trial log(s) submitted successfully!', 'success')
        return redirect(url_for('routes.trial_log'))

    objectives = []
    if selected_student_id:
        try:
            selected_student_id_int = int(selected_student_id)
            objectives = Objective.query.filter(
                Objective.goal.has(Goal.student_id == selected_student_id_int),
                Objective.active
            ).all()
        except ValueError:
            objectives = []

    return render_template(
        'trial_log.html',
        students=students,
        objectives=objectives,
        today=datetime.utcnow().date(),
        selected_student_id=selected_student_id,
    )


@routes_bp.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        grade_level = request.form.get('grade_level', '').strip()
        preferred_name = request.form.get('preferred_name', '').strip()
        pronouns = request.form.get('pronoun', '').strip()
        monthly_services = request.form.get('monthly_services', '').strip()

        new_student = Student(
            first_name=first_name,
            last_name=last_name,
            grade=grade_level,
            preferred_name=preferred_name,
            pronouns=pronouns,
            monthly_services=monthly_services,
        )
        db.session.add(new_student)
        db.session.commit()
        flash('Student added successfully!', 'success')
        return redirect(url_for('routes.index'))
    return render_template('add_student.html')


@routes_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
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
    student = Student.query.get_or_404(student_id)
    student.active = False
    db.session.commit()
    flash('Student archived (soft-deleted) successfully!', 'success')
    return redirect(url_for('routes.index'))


@routes_bp.route('/add_goal/<int:student_id>', methods=['GET', 'POST'])
def add_goal(student_id):
    student = Student.query.filter_by(student_id=student_id, active=True).first_or_404()
    if request.method == 'POST':
        goal_description = request.form['goal_description']
        first_objective = request.form.get('first_objective')
        new_goal = Goal(student_id=student.student_id, goal_description=goal_description)
        db.session.add(new_goal)
        db.session.commit()
        if first_objective:
            new_objective = Objective(goal_id=new_goal.goal_id, objective_description=first_objective)
            db.session.add(new_objective)
            db.session.commit()
        flash('Goal added successfully!', 'success')
        return redirect(url_for('routes.edit_student', student_id=student.student_id))
    return render_template('add_goal.html', student=student)


@routes_bp.route('/add_objective/<int:goal_id>', methods=['GET', 'POST'])
def add_objective(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    if request.method == 'POST':
        objective_description = request.form['objective_description']
        with_accuracy = request.form.get('with_accuracy', '')
        new_objective = Objective(
            goal_id=goal.goal_id,
            objective_description=objective_description,
            with_accuracy=with_accuracy,
        )
        db.session.add(new_objective)
        db.session.commit()
        flash('Objective added successfully!', 'success')
        return redirect(url_for('routes.edit_student', student_id=goal.student.student_id))
    return render_template('add_objective.html', goal=goal)


@routes_bp.route('/edit_objective/<int:objective_id>', methods=['GET', 'POST'])
def edit_objective(objective_id):
    objective = Objective.query.get_or_404(objective_id)
    if request.method == 'POST':
        objective.objective_description = request.form['objective_description']
        objective.with_accuracy = request.form['with_accuracy']
        db.session.commit()
        flash('Objective updated successfully!', 'success')
        return redirect(url_for('routes.index'))
    return render_template('edit_objective.html', objective=objective)


@routes_bp.route('/delete_objective/<int:objective_id>', methods=['POST'])
def delete_objective(objective_id):
    objective = Objective.query.get_or_404(objective_id)
    db.session.delete(objective)
    db.session.commit()
    flash('Objective deleted successfully!', 'success')
    return redirect(url_for('routes.index'))


@routes_bp.route('/edit_goal/<int:goal_id>', methods=['GET', 'POST'])
def edit_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    if request.method == 'POST':
        goal.goal_description = request.form['goal_description']
        db.session.commit()
        flash('Goal updated successfully!', 'success')
        return redirect(url_for('routes.edit_student', student_id=goal.student_id))
    return render_template('edit_goal.html', goal=goal)


@routes_bp.route('/delete_goal/<int:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    db.session.delete(goal)
    db.session.commit()
    flash('Goal deleted successfully!', 'success')
    return redirect(url_for('routes.index'))


@routes_bp.route('/archive_goal/<int:goal_id>', methods=['POST'])
def archive_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    goal.active = False
    db.session.commit()
    flash('Goal archived successfully!', 'success')
    return redirect(url_for('routes.edit_student', student_id=goal.student_id))


@routes_bp.route('/student_search', methods=['GET'])
def student_search():
    query = request.args.get('q')
    students = []
    if query:
        students = Student.query.filter(
            ((Student.first_name.ilike(f'%{query}%')) | (Student.last_name.ilike(f'%{query}%'))) & (Student.active)
        ).all()
    return render_template('student_search.html', students=students, query=query)


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
        new_logs=new_logs,
    )


@routes_bp.route('/students')
def students():
    grade_filter = request.args.get('grade')
    if grade_filter:
        students = Student.query.filter_by(active=True, grade=grade_filter).order_by(Student.first_name).all()
    else:
        students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    return render_template('students.html', students=students, grade_filter=grade_filter)


@routes_bp.route('/student/<int:student_id>')
def student_info(student_id):
    student = Student.query.get_or_404(student_id)
    goals = Goal.query.filter_by(student_id=student_id).all()
    objectives = Objective.query.join(Goal).filter(Goal.student_id == student_id).all()
    return render_template('student_info.html', student=student, goals=goals, objectives=objectives)
