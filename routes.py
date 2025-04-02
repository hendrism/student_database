from flask import request, redirect, url_for, render_template, flash, Blueprint
from models import Student, Objective, Goal, TrialLog, Session, db  # Now includes Session!
from datetime import datetime
from sqlalchemy import extract, or_

routes_bp = Blueprint('routes', __name__)

@routes_bp.route('/')
def index():
  grade_filter = request.args.get('grade')
  if grade_filter:
    students = Student.query.filter_by(active=True, grade=grade_filter).order_by(Student.first_name).all()
  else:
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
  return render_template('index.html', students=students, grade_filter=grade_filter)

@routes_bp.route('/trial_log', methods=['GET', 'POST'])
def trial_log():
  students = Student.query.filter_by(active=True).order_by(Student.first_name).all()  # for the dropdown
  selected_student_id = request.args.get('student_id')  # when selecting a student via GET
  
  # ---------- Handling trial submission ----------
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
    
    # Loop through each selected objective and save trial log
    for objective_id in objective_ids:
      trial_log = TrialLog(
        student_id=student_id,
        objective_id=objective_id,
        date_of_session=datetime.strptime(date_of_session, '%Y-%m-%d').date(),
        correct_no_support=correct_no_support,
        correct_visual_cue=correct_visual_cue,
        correct_verbal_cue=correct_verbal_cue,
        correct_visual_verbal_cue=correct_visual_verbal_cue,
        correct_modeling=correct_modeling,
        incorrect=incorrect,
        notes=notes
      )
      db.session.add(trial_log)
      
    db.session.commit()
    flash('Trial log(s) submitted successfully!', 'success')
    return redirect(url_for('routes.trial_log'))
  
  # ---------- Handling objective fetching for selected student ----------
  objectives = []
  if selected_student_id:
    try:
      selected_student_id_int = int(selected_student_id)  # Convert to int for query
      print("Selected student ID:", selected_student_id_int)  # TEMP DEBUGGING
      objectives = Objective.query.filter(
        Objective.goal.has(Goal.student_id == selected_student_id_int),
        Objective.active == True
      ).all()
      print(f"Objectives found: {len(objectives)}")  # TEMP DEBUGGING
    except ValueError:
      print("Invalid student ID received:", selected_student_id)
      objectives = []
      
  return render_template(
    'trial_log.html',
    students=students,
    objectives=objectives,
    today=datetime.utcnow().date(),
    selected_student_id=selected_student_id
  )
  
@routes_bp.route('/add_student', methods=['GET', 'POST'])
def add_student():
  """
  Add a new student.
  """
  if request.method == 'POST':
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    grade_level = request.form['grade_level']
    pronoun = request.form['pronoun']
    monthly_services = request.form['monthly_services']
    
    new_student = Student(
      first_name=first_name,
      last_name=last_name,
      grade=grade_level,
      pronoun=pronoun,
      monthly_services=monthly_services
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
    student.pronoun = request.form['pronoun']  # Updated to use "pronoun"
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

@routes_bp.route('/sessions')
def sessions():
  filter_date = request.args.get('filter_date')
  
  if filter_date:
    # Convert filter_date string to a date object to compare
    try:
      date_obj = datetime.strptime(filter_date, '%Y-%m-%d').date()
      sessions_list = Session.query.filter(
        Session.date_of_session == date_obj,
        Session.active == True  # ✅ Only active sessions
      ).order_by(Session.date_of_session, Session.time_of_session).all()
    except ValueError:
      flash('Invalid date format!', 'danger')
      sessions_list = Session.query.filter(Session.active == True).order_by(
        Session.date_of_session, Session.time_of_session
      ).all()
  else:
    # If no filter, show all active sessions
    sessions_list = Session.query.filter(Session.active == True).order_by(
      Session.date_of_session, Session.time_of_session
    ).all()
    
  return render_template('sessions.html', sessions=sessions_list)

@routes_bp.route('/session_action/<int:session_id>', methods=['GET', 'POST'])
def session_action(session_id):
  session = Session.query.get_or_404(session_id)
  student = session.student  # Direct relationship from session
  objectives = session.objectives  # Related objectives
  
  if request.method == 'POST':
    # Update status and plan notes
    session.status = request.form['status']
    session.plan_notes = request.form['plan_notes']
    db.session.commit()
    flash('Session updated successfully!', 'success')
    filter_date = request.args.get('filter_date')
    status_filter = request.args.get('status_filter')
    return redirect(url_for('routes.sessions', filter_date=filter_date, status_filter=status_filter) if filter_date or status_filter else url_for('routes.sessions'))  
  return render_template('session_action.html', session=session, student=student, objectives=objectives)

@routes_bp.route('/add_session', methods=['GET', 'POST'])
def add_session():
  filter_date = request.args.get('filter_date')  # ✅ Preserve date filter
  status_filter = request.args.get('status_filter')  # ✅ Preserve status filter
  
  students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
  objectives = Objective.query.all()
  
  selected_student_id = request.args.get('student_id')
  selected_student = Student.query.get(selected_student_id) if selected_student_id else None
  selected_student_goals = selected_student.goals if selected_student else None
  
  if request.method == 'POST':
    student_id = request.form['student_id']
    date_str = request.form['date_of_session']
    time_str = request.form['time_of_session']
    status = request.form['status']
    plan_notes = request.form['plan_notes']
    objective_ids = request.form.getlist('objectives')
    
    try:
      date_of_session = datetime.strptime(date_str, '%Y-%m-%d').date()
      time_of_session = datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
      flash('Invalid date or time format!', 'error')
      return redirect(url_for('routes.add_session', filter_date=filter_date, status_filter=status_filter))
    
    new_session = Session(
      student_id=student_id,
      date_of_session=date_of_session,
      time_of_session=time_of_session,
      status=status,
      plan_notes=plan_notes
    )
    db.session.add(new_session)
    
    for obj_id in objective_ids:
      objective = Objective.query.get(obj_id)
      if objective:
        new_session.objectives.append(objective)
        
    db.session.commit()
    flash('Session added successfully!', 'success')
    
    # ✅ Redirect back with filters if they were used
    return redirect(url_for('routes.sessions', filter_date=filter_date) if filter_date else url_for('routes.sessions'))
  
  return render_template(
    'add_session.html',
    students=students,
    objectives=objectives,
    selected_student_id=selected_student_id,
    selected_student=selected_student,
    selected_student_goals=selected_student_goals,
    filter_date=filter_date,
    status_filter=status_filter
  )
  
@routes_bp.route('/edit_session/<int:session_id>', methods=['GET', 'POST'])
def edit_session(session_id):
    filter_date = request.args.get('filter_date')  # Preserve filter_date
    status_filter = request.args.get('status_filter')  # Optional status filter
  
    session_obj = Session.query.get_or_404(session_id)
    students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
    objectives = Objective.query.all()
  
    new_student_id = request.args.get('student_id')
    selected_student_id = int(new_student_id) if new_student_id else session_obj.student_id
    selected_student = Student.query.get(selected_student_id) if selected_student_id else None
    student_goals = selected_student.goals if selected_student else None
  
    if request.method == 'POST':
        session_obj.student_id = request.form['student_id']
        try:
            session_obj.date_of_session = datetime.strptime(request.form['date_of_session'], '%Y-%m-%d').date()
            session_obj.time_of_session = datetime.strptime(request.form['time_of_session'], '%H:%M').time()
        except ValueError:
            flash('Invalid date or time format!', 'error')
            return render_template(
              'edit_session.html',
              session_obj=session_obj,
              students=students,
              objectives=objectives,
              selected_student_id=selected_student_id,
              student_goals=student_goals,
              filter_date=filter_date,
              status_filter=status_filter
            )
            
        session_obj.status = request.form['status']
        session_obj.plan_notes = request.form['plan_notes']
      
        # Update selected objectives
        session_obj.objectives.clear()
        for obj_id in request.form.getlist('objectives'):
            objective = Objective.query.get(obj_id)
            if objective:
                session_obj.objectives.append(objective)
              
        db.session.commit()
        flash('Session updated successfully!', 'success')
        next_page = request.form.get('next') or request.args.get('next')
        if next_page:
            return redirect(next_page)
        else:
            return redirect(url_for('routes.sessions', filter_date=filter_date, status_filter=status_filter)
                            if filter_date or status_filter else url_for('routes.sessions'))
      
    # When rendering, pass the next parameter so your form can include it:
    return render_template(
      'edit_session.html',
      session_obj=session_obj,
        students=students,
        objectives=objectives,
        selected_student_id=selected_student_id,
        student_goals=student_goals,
        filter_date=filter_date,
        status_filter=status_filter,
        next=request.args.get('next')
    )
    
  
@routes_bp.route('/delete_session/<int:session_id>', methods=['POST'])
def delete_session(session_id):
  session_obj = Session.query.get_or_404(session_id)
  db.session.delete(session_obj)
  db.session.commit()
  flash('Session deleted successfully!', 'success')
  next_page = request.form.get('next') or request.args.get('next')
  if next_page:
    return redirect(next_page)
  else:
    filter_date = request.args.get('filter_date')
    status_filter = request.args.get('status_filter')
    return redirect(url_for('routes.sessions', filter_date=filter_date, status_filter=status_filter)
            if filter_date or status_filter else url_for('routes.sessions'))
  

@routes_bp.route('/add_goal/<int:student_id>', methods=['GET', 'POST'])
def add_goal(student_id):
  student = Student.query.filter_by(student_id=student_id, active=True).first_or_404()
  if request.method == 'POST':
    goal_description = request.form['goal_description']
    first_objective = request.form.get('first_objective')
    
    # Create goal
    new_goal = Goal(student_id=student.student_id, goal_description=goal_description)
    db.session.add(new_goal)
    db.session.commit()
    
    # If an objective was added, create and link it
    if first_objective:
      new_objective = Objective(goal_id=new_goal.goal_id, objective_description=first_objective)
      db.session.add(new_objective)
      db.session.commit()
      
    flash('Goal added successfully!', 'success')
    return redirect(url_for('routes.student_info', student_id=student.student_id))
  
  return render_template('add_goal.html', student=student)

@routes_bp.route('/add_objective/<int:goal_id>', methods=['GET', 'POST'])
def add_objective(goal_id):
  """
  Add an objective for a specific goal.
  """
  goal = Goal.query.get_or_404(goal_id)
  if request.method == 'POST':
    objective_description = request.form['objective_description']
    with_accuracy = request.form.get('with_accuracy', '')  # Optional
    
    new_objective = Objective(
      goal_id=goal.goal_id,
      objective_description=objective_description,
      with_accuracy=with_accuracy
    )
    db.session.add(new_objective)
    db.session.commit()
    flash('Objective added successfully!', 'success')
    
    # ✅ Redirect back to student profile
    return redirect(url_for('routes.student_info', student_id=goal.student.student_id))
  
  return render_template('add_objective.html', goal=goal)

@routes_bp.route('/edit_objective/<int:objective_id>', methods=['GET', 'POST'])
def edit_objective(objective_id):
    """
    Edit an existing objective.
    """
    objective = Objective.query.get_or_404(objective_id)
    if request.method == 'POST':
        objective.objective_description = request.form['objective_description']
        objective.with_accuracy = request.form['with_accuracy']
        db.session.commit()
        flash('Objective updated successfully!', 'success')
        return redirect(url_for('routes.index'))
    return render_template('edit_objective.html', objective=objective)

@routes_bp.route('/delete_objective/<int:objective_id>')
def delete_objective(objective_id):
    """
    Delete an objective.
    NOTE: Consider using POST to avoid accidental deletions.
    """
    objective = Objective.query.get_or_404(objective_id)
    db.session.delete(objective)
    db.session.commit()
    flash('Objective deleted successfully!', 'success')
    return redirect(url_for('routes.index'))

@routes_bp.route('/edit_goal/<int:goal_id>', methods=['GET', 'POST'])
def edit_goal(goal_id):
    """
    Edit an existing goal.
    """
    goal = Goal.query.get_or_404(goal_id)
    if request.method == 'POST':
        goal.goal_description = request.form['goal_description']
        db.session.commit()
        flash('Goal updated successfully!', 'success')
        return redirect(url_for('routes.index'))
    return render_template('edit_goal.html', goal=goal)

@routes_bp.route('/delete_goal/<int:goal_id>')
def delete_goal(goal_id):
    """
    Delete a goal.
    NOTE: Consider using POST to avoid accidental deletions.
    """
    goal = Goal.query.get_or_404(goal_id)
    db.session.delete(goal)
    db.session.commit()
    flash('Goal deleted successfully!', 'success')
    return redirect(url_for('routes.index'))


@routes_bp.route('/student/<int:student_id>')
def student_info(student_id):
    student = Student.query.filter_by(student_id=student_id, active=True).first_or_404()
    recent_sessions = Session.query.filter_by(student_id=student_id)\
                                   .order_by(Session.date_of_session.desc())\
                                   .limit(5).all()
    return render_template('student_info.html', student=student, recent_sessions=recent_sessions)
                            
@routes_bp.route('/student_search', methods=['GET'])
def student_search():
    query = request.args.get('q')
    students = []
    if query:
        students = Student.query.filter(
          ((Student.first_name.ilike(f'%{query}%')) |
          (Student.last_name.ilike(f'%{query}%'))) &
          (Student.active == True)
        ).all()
      
    return render_template('student_search.html', students=students, query=query)

@routes_bp.route('/student/<int:student_id>/trial_logs')
def student_trial_logs(student_id):
  student = Student.query.get_or_404(student_id)
  
  # Fetch trial logs for the student and join with objectives
  trial_logs = TrialLog.query.filter_by(student_id=student_id).join(Objective, isouter=True).all()
  
  return render_template('student_trial_logs.html', student=student, trial_logs=trial_logs)

@routes_bp.route('/soap_note', methods=['GET', 'POST'])
def soap_note():
  students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
  
  # Handle selected student for filtering
  selected_student_id = request.args.get('student_id', type=int)
  selected_student = Student.query.get(selected_student_id) if selected_student_id else None
  
  # Monthly services display
  monthly_services = selected_student.monthly_services if selected_student and selected_student.monthly_services else "Not specified"
  
  # Session count for the current month
  session_count = 0  # Default if no student is selected
  if selected_student:
    current_month = datetime.now().month
    current_year = datetime.now().year
    session_count = Session.query.filter(
      Session.student_id == selected_student_id,
      db.extract('month', Session.date_of_session) == current_month,
      db.extract('year', Session.date_of_session) == current_year,
      Session.status.in_(["Completed", "Excused Absence"])
    ).count()
    
  # Filter objectives if student selected
  if selected_student_id:
    objectives = Objective.query.join(Goal).filter(
      Goal.student_id == selected_student_id, Objective.active == True
    ).all()
  else:
    objectives = []
    
  months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ]
  current_month_str = datetime.now().strftime('%B')
  
  if request.method == 'POST':
    # Fetch form data
    student_id = request.form.get('student_id')
    student = Student.query.get(student_id) if student_id else None  # Needed for pronouns and name
    
    month = request.form.get('month')
    session_number = request.form.get('session_number')
    total_sessions = request.form.get('total_sessions')
    performance = request.form.get('performance')
    additional_S = request.form.get('additional_S')
    
    # New: Session Type dropdown (defaults to Individual)
    session_type = request.form.get('session_type', 'Individual')
    
    # Activity dropdown with custom option restored
    activity = request.form.get('activity') if request.form.get('activity') != 'Other' else request.form.get('activity_other')
    
    # Objective dropdown with custom option restored
    objective = request.form.get('objective') if request.form.get('objective') != 'Other' else request.form.get('objective_other')
    
    accuracy = request.form.get('accuracy')
    
    # Support level dropdown with custom option restored
    support_level = request.form.get('support_level')
    if support_level == 'Other':
      support_level = request.form.get('support_level_other', 'with support')
      
    additional_O = request.form.get('additional_O')
    
    # Gather visual and verbal cues, including "Other" input if provided
    visual_cues = request.form.getlist('visual_cues')
    visual_cues_other = request.form.get('visual_cues_other', '').strip()
    if visual_cues_other:
      visual_cues.append(visual_cues_other)
      
    verbal_cues = request.form.getlist('verbal_cues')
    verbal_cues_other = request.form.get('verbal_cues_other', '').strip()
    if verbal_cues_other:
      verbal_cues.append(verbal_cues_other)
      
    # Proper formatting for cue lists
    def format_list(items):
      if len(items) == 1:
        return items[0].lower()
      elif len(items) == 2:
        return f"{items[0].lower()} and {items[1].lower()}"
      else:
        return f"{', '.join(item.lower() for item in items[:-1])}, and {items[-1].lower()}"
      
    visual_cues_formatted = format_list(visual_cues) if visual_cues else 'N/A'
    verbal_cues_formatted = format_list(verbal_cues) if verbal_cues else 'N/A'
    
    # Enhanced Pronoun Handling
    pronoun_map = {
      "he/him": ("he", "his", "him"),
      "she/her": ("she", "her", "her"),
      "they/them": ("they", "their", "them"),
      "other": ("they", "their", "them")
    }
    
    if student and student.pronouns:
      pronoun_key = student.pronouns.lower().strip()
      if pronoun_key not in pronoun_map:
        if "she" in pronoun_key:
          pronoun_key = "she/her"
        elif "he" in pronoun_key:
          pronoun_key = "he/him"
        else:
          pronoun_key = "they/them"
    else:
      pronoun_key = "they/them"
      
    pronoun_subject, pronoun_possessive, pronoun_object = pronoun_map.get(pronoun_key, ("they", "their", "them"))
    verb_be = "was" if pronoun_subject in ["he", "she"] else "were"
    
    # Formatted SOAP Note Sections
    # S Section with Session Type and corrected possessive pronoun
    s_note = f"{month} Session {session_number}/{total_sessions}: {student.first_name} attended {pronoun_possessive} {session_type.lower()} speech therapy session. {pronoun_subject.capitalize()} {verb_be} {performance}."
    if additional_S:
      s_note += f" {additional_S}"
      
    # O Section
    o_note = f"{pronoun_subject.capitalize()} {verb_be} given {activity.lower()}. {pronoun_subject.capitalize()} {verb_be} able to {objective} with {accuracy}% accuracy {support_level}."
    if additional_O:
      o_note += f" {additional_O}"
      
    # A Section (adaptive wording based on what's filled)
    if visual_cues and verbal_cues:
      a_note = f"{pronoun_subject.capitalize()} benefited from visual and verbal cues. Visual cues included {visual_cues_formatted}. Verbal cues included {verbal_cues_formatted}."
    elif visual_cues:
      a_note = f"{pronoun_subject.capitalize()} benefited from visual cues. Visual cues included {visual_cues_formatted}."
    elif verbal_cues:
      a_note = f"{pronoun_subject.capitalize()} benefited from verbal cues. Verbal cues included {verbal_cues_formatted}."
    else:
      a_note = f"{pronoun_subject.capitalize()} did not require visual or verbal cues during this session."
      
    p_note = "Continue to target IEP goals. -Sean Hendricks, MA CCC-SLP"
    
    return render_template(
      'soap_note_result.html',
      s_note=s_note,
      o_note=o_note,
      a_note=a_note,
      p_note=p_note
    )
  
  return render_template(
    'soap_note.html',
    students=students,
    objectives=objectives,
    months=months,
    current_month=current_month_str,
    selected_student=selected_student,
    monthly_services=monthly_services,
    session_count=session_count
  )
  
@routes_bp.route('/archive_session/<int:session_id>', methods=['POST'])
def archive_session(session_id):
  session_obj = Session.query.get_or_404(session_id)
  session_obj.active = False  # Mark session as archived
  db.session.commit()
  flash('Session archived successfully!', 'success')
  next_page = request.form.get('next') or request.args.get('next')
  if next_page:
    return redirect(next_page)
  else:
    filter_date = request.args.get('filter_date')
    status_filter = request.args.get('status_filter')
    return redirect(url_for('routes.sessions', filter_date=filter_date, status_filter=status_filter)
            if filter_date or status_filter else url_for('routes.sessions'))
  
@routes_bp.route('/reports')
def reports():
  return render_template('reports.html')

@routes_bp.route('/monthly_sessions_report')
def monthly_sessions_report():
  # Get month and year from query parameters (or default to current)
  month = request.args.get('month', datetime.now().month, type=int)
  year = request.args.get('year', datetime.now().year, type=int)
  sort_by = request.args.get('sort_by', '')
  
  students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
  
  report_data = []
  
  for student in students:
    total_expected = int(student.monthly_services) if student.monthly_services and student.monthly_services.isdigit() else 0
    
    completed_sessions = Session.query.filter(
      Session.student_id == student.student_id,
      extract('month', Session.date_of_session) == month,
      extract('year', Session.date_of_session) == year,
      Session.status.in_(['Completed', 'Excused Absence']),
      Session.active == True
    ).count()
    
    makeup_needed = Session.query.filter(
      Session.student_id == student.student_id,
      extract('month', Session.date_of_session) == month,
      extract('year', Session.date_of_session) == year,
      Session.status == 'Makeup Needed',
      Session.active == True
    ).count()
    
    total_makeups = Session.query.filter(
      Session.student_id == student.student_id,
      Session.status == 'Makeup Needed',
      Session.active == True,
      Session.date_of_session < datetime(year, month, 1)
    ).count()
    
    remaining = max(total_expected - completed_sessions, 0)
    
    report_data.append({
      'student_name': f"{student.first_name} {student.last_name}",
      'expected_sessions': total_expected,
      'completed_sessions': completed_sessions,
      'makeup_needed': makeup_needed,
      'remaining_sessions': remaining,
      'total_makeups': total_makeups
    })
    
  # ✅ Sort the report data if sorting is selected
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
    sort_by=sort_by  # ✅ Pass it back so the dropdown stays selected
  )
  
@routes_bp.route('/reports/makeup_needed')
def makeup_needed_report():
  now = datetime.now()
  current_month = now.month
  current_year = now.year
  
  # All active "Makeup Needed" sessions
  all_makeup_needed = Session.query.filter(
    Session.status == 'Makeup Needed',
    Session.active == True
  ).order_by(Session.date_of_session.asc(), Session.time_of_session.asc()).all()
  
  # "Makeup Needed" sessions for the current month/year
  this_month_makeup_needed = Session.query.filter(
    db.extract('month', Session.date_of_session) == current_month,
    db.extract('year', Session.date_of_session) == current_year,
    Session.status == 'Makeup Needed',
    Session.active == True
  ).order_by(Session.date_of_session.asc(), Session.time_of_session.asc()).all()
  
  return render_template(
    'makeup_needed_report.html',
    all_makeup_needed=all_makeup_needed,
    this_month_makeup_needed=this_month_makeup_needed,
    current_month=current_month,
    current_year=current_year
  )
  
@routes_bp.route('/trial_logs_by_date', methods=['GET'])
def trial_logs_by_date():
  # Get selected date from query or default to today
  selected_date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
  try:
    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
  except ValueError:
    flash('Invalid date format!', 'danger')
    selected_date = datetime.now().date()
    
  # ✅ Query trial logs for that date using correct field name
  trial_logs = TrialLog.query.filter(
    TrialLog.date_of_session == selected_date
  ).order_by(TrialLog.student_id).all()
  
  return render_template(
    'trial_logs_by_date.html',
    trial_logs=trial_logs,
    selected_date=selected_date_str
  )
  
@routes_bp.route('/quarterly_report', methods=['GET', 'POST'])
def quarterly_report():
  # Query active students for the dropdown.
  students = Student.query.filter_by(active=True).order_by(Student.first_name).all()
  quarters = ['Q1', 'Q2', 'Q3', 'Q4']
  overall_progress_options = ["Significant Progress", "Steady Progress", "Minimal Progress", "Other"]
  closing_sentence_options = [
    "Keep up the great work!",
    "We will continue to focus on these skills in the next quarter.",
    "Progress is steady; adjustments will be made next quarter.",
    "Other"
  ]
  
  selected_student = None
  
  if request.method == 'POST':
    form_stage = request.form.get('form_stage')
    if form_stage == 'start':
      # Stage 1: Student selected; show full progress form.
      student_id = request.form.get('student_id')
      if student_id:
        selected_student = Student.query.get(student_id)
      else:
        flash("Please select a student.", "danger")
        return render_template('quarterly_report.html', students=students)
      return render_template('quarterly_report.html',
                  students=students,
                  selected_student=selected_student,
                  quarters=quarters,
                  overall_progress_options=overall_progress_options,
                  closing_sentence_options=closing_sentence_options)
    elif form_stage == 'generate':
      # Stage 2: Full form submitted; generate report.
      student_id = request.form.get('student_id')
      if student_id:
        selected_student = Student.query.get(student_id)
      else:
        flash("Please select a student.", "danger")
        return render_template('quarterly_report.html', students=students)
      
      quarter = request.form.get('quarter')
      overall_progress = request.form.get('overall_progress')
      if overall_progress == 'Other':
        overall_progress = request.form.get('overall_progress_custom')
      closing_sentence = request.form.get('closing_sentence')
      if closing_sentence == 'Other':
        closing_sentence = request.form.get('closing_sentence_custom')
        
      # Map quarter codes to full text.
      quarter_map = {
        "Q1": "the first quarter",
        "Q2": "the second quarter",
        "Q3": "the third quarter",
        "Q4": "the fourth quarter"
      }
      first_name = selected_student.first_name
      # Use the first part of the pronouns field as the subject pronoun (default to first name if missing).
      subject_pronoun = (selected_student.pronouns.split('/')[0].capitalize()
                if selected_student.pronouns else first_name)
      overall_progress_text = overall_progress.lower()
      quarter_text = quarter_map.get(quarter, quarter)
      
      report_paragraphs = []

      # Process each goal separately.
      for goal in selected_student.goals:
          paragraph_lines = []
          # Intro sentence (without goal number).
          intro_sentence = f"{first_name} demonstrated {overall_progress_text} in {quarter_text}."
          paragraph_lines.append(intro_sentence)
        
          # Process each objective in this goal.
          for obj in goal.objectives:
              performances = request.form.getlist(f'performance_{obj.objective_id}')
              supports = request.form.getlist(f'support_{obj.objective_id}')
              entries = []
              for perf, supp in zip(performances, supports):
                  if perf.strip():
                      entries.append(f"with {perf}% accuracy {supp.lower()}")
              if entries:
                  if len(entries) == 1:
                      performance_text = entries[0]
                  elif len(entries) == 2:
                      performance_text = " and ".join(entries)
                  else:
                      performance_text = ", ".join(entries[:-1]) + ", and " + entries[-1]
                  sentence = f"{subject_pronoun} was able to {obj.objective_description} {performance_text}."
                  paragraph_lines.append(sentence)
          paragraph_lines.append(closing_sentence)
          # Join the lines into one paragraph (space-separated, no line breaks).
          report_paragraphs.append(" ".join(paragraph_lines))
        
      # Instead of joining report_paragraphs into one string, pass the list directly:
      return render_template('quarterly_report_result.html',
                report_paragraphs=report_paragraphs,
                selected_student=selected_student)
    
    
  # GET request: show only the student selection form.
  return render_template('quarterly_report.html', students=students)
