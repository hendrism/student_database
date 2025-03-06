print("--- test_models.py: Starting execution ---") # ADD THIS at the very TOP

try:
    from models import session_objectives_association, Objective, Session, Student, Goal, db # Import from models.py
    print("--- test_models.py: Import from models.py successful ---") # ADD THIS if import succeeds

    print(f"--- test_models.py: session_objectives_association: {session_objectives_association} ---") # Try to access session_objectives_association
    print(f"--- test_models.py: Objective: {Objective} ---") # Try to access Objective model
    print(f"--- test_models.py: Session: {Session} ---") # Try to access Session model
    print(f"--- test_models.py: Student: {Student} ---") # Try to access Student model
    print(f"--- test_models.py: Goal: {Goal} ---") # Try to access Goal model
    print(f"--- test_models.py: db: {db} ---") # Try to access db object

    print("--- test_models.py: Successfully accessed models ---") # ADD THIS if all accesses succeed

except ImportError as e:
    print(f"--- test_models.py: ImportError! ---") # ADD THIS if ImportError occurs
    print(f"ImportError details: {e}") # Print ImportError details
except NameError as e:
    print(f"--- test_models.py: NameError! ---") # ADD THIS if NameError occurs (like session_objectives_association not defined)
    print(f"NameError details: {e}") # Print NameError details
except Exception as e:
    print(f"--- test_models.py: Other Error! ---") # ADD THIS for any other errors
    print(f"Error details: {e}") # Print error details


print("--- test_models.py: Reached end of script ---") # ADD THIS at the very BOTTOM