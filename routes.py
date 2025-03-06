from flask import request, redirect, url_for, render_template, flash, Blueprint
from models import Student, Session, Goal, Objective, session_objectives_association # Change back to absolute import (remove .)
from datetime import datetime

routes_bp = Blueprint('routes', __name__)

@routes_bp.route('/')
def index():
    return render_template('index.html')

@routes_bp.route('/students')
def student_list():
    search_term = request.args.get('search')
    if search_term:
        students = Student.query.filter(Student.first_name.contains(search_term) | Student.last_name.contains(search_term)).all()
    else:
        students = Student.query.all()
        
    print("Debugging - Student List Route:") # Debugging print statement (start of route)
    print(f"  search_term: {search_term}") # Debugging: Check search term
    print(f"  students: {students}, type: {type(students) if students else None}") # Debugging: Check students list
    if students:
        print(f"  Number of students fetched: {len(students)}") # Debugging: Count students
    else:
        print("  No students fetched (students is empty or None)") # Debugging: No students message
        
    return render_template('students.html', students=students, search_term=search_term)

@routes_bp.route('/schedule_session/confirmation')
def schedule_session_confirmation():
    return render_template('schedule_confirmation.html')

@routes_bp.route('/schedule_session', methods=['GET', 'POST'])
def schedule_session():
    students = Student.query.all()
    selected_student_id = request.args.get('student_id') # Get student_id from query parameters for "View Goals"
    selected_student = Student.query.get(selected_student_id) if selected_student_id else None
    selected_student_goals = selected_student.goals if selected_student else None
    date_of_session = None # Initialize date_of_session to None for GET requests
    time_of_session = None # Initialize time_of_session to None for GET requests
    plan_notes = None # Initialize plan_notes to None for GET requests
    action = request.args.get('action') # Check if "View Goals/Objectives" button was clicked
    
    if action == 'view_goals': # Check if "View Goals/Objectives" button was clicked
        print("Debugging - View Goals Action:")
        print(f"  selected_student_id: {selected_student_id}")
        print(f"  selected_student: {selected_student}, type: {type(selected_student) if selected_student else None}")
        print(f"  selected_student_goals: {selected_student_goals}, type: {type(selected_student_goals) if selected_student_goals else None}")
        if selected_student_goals:
            print(f"  Number of goals fetched: {len(selected_student_goals)}")
        else:
            print("  No goals fetched")
            
        # If "View Goals/Objectives" button is clicked, just re-render the template with goals/objectives
        return render_template('session_scheduling.html',
                               students=students,
                               selected_student_id=selected_student_id,
                               selected_student=selected_student,
                               selected_student_goals=selected_student_goals)
                                
    if request.method == 'POST': # If form is submitted (Schedule Session button)
        selected_student_id = request.form['student_id']
        date_of_session_str = request.form['date_of_session']
        date_of_session_python_date = datetime.strptime(date_of_session_str, '%Y-%m-%d').date() # Convert date string to date object
        time_of_session_str = request.form['time_of_session']
        time_of_session_python_time = datetime.strptime(time_of_session_str, '%H:%M').time() # Convert time string to time object
        plan_notes = request.form['plan_notes']
        selected_objective_ids = request.form.getlist('selected_objectives') # Get list of selected objective IDs
        
        print("Debugging - Schedule Session POST Request:")
        print(f"  Selected Student ID: {selected_student_id}")
        print(f"  Date of Session: {date_of_session_python_date}")
        print(f"  Time of Session: {time_of_session_python_time}")
        print(f"  Plan Notes: {plan_notes}")
        print(f"  Selected Objective IDs: {selected_objective_ids}")
        
        new_session = Session(
            student_id=selected_student_id,
            date_of_session=date_of_session_python_date,
            time_of_session=time_of_session_python_time,
            status='Scheduled',
            plan_notes=plan_notes
        )
        db.session.add(new_session)
        
        if selected_objective_ids: # If any objectives were selected
            selected_objectives = Objective.query.filter(Objective.objective_id.in_(selected_objective_ids)).all()
            new_session.objectives.extend(selected_objectives)
            print(f"  Associated Objectives with Session: {[obj.objective_description for obj in selected_objectives]}")
            
        db.session.commit()
        return redirect(url_for('routes.session_list_route')) # <-- Change to this (likely)
        
    return render_template('session_scheduling.html', # For initial GET request or after "View Goals" action
                           students=students,
                           selected_student_id=selected_student_id,
                           selected_student=selected_student,
                           selected_student_goals=selected_student_goals,
                           date_of_session=date_of_session, # Pass date_of_session, will be None for GET
                           time_of_session=time_of_session, # Pass time_of_session, will be None for GET
                           plan_notes=plan_notes) # Pass plan_notes, will be None for GET

@routes_bp.route('/sessions')
def session_list_route():
    filter_date_str = request.args.get('filter_date') # 1. Get filter_date from request arguments
    filtered_date = None # Initialize filtered_date to None
    
    if filter_date_str: # 2. Check if filter_date_str is not None or empty
        try:
            filtered_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date() # Convert string to date object
            sessions = Session.query.filter(Session.date_of_session == filtered_date).all() # Filter sessions by date
        except ValueError:
            sessions = Session.query.all() # If date parsing fails, show all sessions (or handle error as needed)
            flash('Invalid date format. Showing all sessions.', 'warning') # Optional: Flash a message
    else: # If no filter_date provided
        sessions = Session.query.all() # Get all sessions (no filter)
    
    return render_template('session_list.html', sessions=sessions, filter_date=filter_date_str) # Pass sessions and filter_date to template

@routes_bp.route('/sessions/<int:session_id>/edit', methods=['GET', 'POST'])
def edit_session_route(session_id):
    session = Session.query.get_or_404(session_id)
    students = Student.query.all()
    student_goals = session.student.goals if session.student else []
    session_objective_ids = [objective.objective_id for objective in session.objectives]

    print(f"Debugging: Type of session.time_of_session: {type(session.time_of_session)}")

    if request.method == 'POST':
        print("--- POST request received ---")
        print("Form data:", request.form)
        # ... (rest of your POST handling code - temporarily keep the simplified return)

    return render_template('edit_session.html',
                           session=session,
                           students=students,
                           student_goals=student_goals,
                           session_objective_ids=session_objective_ids)