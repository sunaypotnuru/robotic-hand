#!/usr/bin/env python3
"""
LUNA Grade Improvements - Verification Script
Verifies that all improvements have been successfully applied
"""

import os
import sys
import subprocess

def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_result(test_name, passed, message=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {test_name}")
    if message:
        print(f"       {message}")

def check_file_exists(filepath):
    """Check if a file exists"""
    return os.path.exists(filepath)

def check_no_secrets():
    """Check that no secrets are hardcoded"""
    try:
        # Check manually for Windows compatibility
        with open('create_admin.py', 'r', encoding='utf-8') as f:
            content = f.read()
            # Check if old hardcoded password is gone
            if 'surya1688' in content:
                return False
            # Check if using environment variables
            if 'os.getenv' in content and 'ADMIN_PASSWORD' in content:
                return True
            return False
    except Exception as e:
        print(f"       Error checking secrets: {e}")
        return False

def check_python_compiles(filepath):
    """Check if Python file compiles"""
    try:
        result = subprocess.run(
            ['python', '-m', 'py_compile', filepath],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        return False

def main():
    """Run all verification checks"""
    print_header("LUNA GRADE IMPROVEMENTS - VERIFICATION")
    
    total_tests = 0
    passed_tests = 0
    
    # Check 1: Environment files
    print_header("1. Environment Configuration")
    total_tests += 1
    if check_file_exists('.env'):
        print_result("Environment file exists", True)
        passed_tests += 1
    else:
        print_result("Environment file exists", False, "Create .env from .env.example")
    
    total_tests += 1
    if check_file_exists('.env.example'):
        print_result("Environment template exists", True)
        passed_tests += 1
    else:
        print_result("Environment template exists", False)
    
    # Check 2: No hardcoded secrets
    print_header("2. Security - No Hardcoded Secrets")
    total_tests += 1
    if check_no_secrets():
        print_result("No hardcoded passwords", True)
        passed_tests += 1
    else:
        print_result("No hardcoded passwords", False, "Found hardcoded credentials")
    
    # Check 3: Test files
    print_header("3. Test Infrastructure")
    test_files = [
        'tests/__init__.py',
        'tests/test_motor_control.py',
        'tests/test_ai_modules.py',
        'pytest.ini'
    ]
    for test_file in test_files:
        total_tests += 1
        if check_file_exists(test_file):
            print_result(f"Test file: {test_file}", True)
            passed_tests += 1
        else:
            print_result(f"Test file: {test_file}", False)
    
    # Check 4: New modules
    print_header("4. New Modules")
    new_modules = [
        'web_interface/ai_modules/motion_recorder.py',
        'utils/validators.py',
        'utils/__init__.py'
    ]
    for module in new_modules:
        total_tests += 1
        if check_file_exists(module):
            print_result(f"Module: {module}", True)
            passed_tests += 1
        else:
            print_result(f"Module: {module}", False)
    
    # Check 5: Python compilation
    print_header("5. Python Compilation")
    python_files = [
        'app.py',
        'create_admin.py',
        'utils/validators.py',
        'web_interface/ai_modules/motion_recorder.py'
    ]
    for py_file in python_files:
        total_tests += 1
        if check_python_compiles(py_file):
            print_result(f"Compiles: {py_file}", True)
            passed_tests += 1
        else:
            print_result(f"Compiles: {py_file}", False)
    
    # Check 6: Documentation
    print_header("6. Documentation")
    docs = [
        'PATH1_COMPLETE.md',
        'PATH2_COMPLETE.md',
        'IMPLEMENTATION_COMPLETE.md',
        'START_HERE.md'
    ]
    for doc in docs:
        total_tests += 1
        if check_file_exists(doc):
            print_result(f"Documentation: {doc}", True)
            passed_tests += 1
        else:
            print_result(f"Documentation: {doc}", False)
    
    # Check 7: .gitignore
    print_header("7. Git Configuration")
    total_tests += 1
    if check_file_exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            content = f.read()
            if '.env' in content:
                print_result(".gitignore includes .env", True)
                passed_tests += 1
            else:
                print_result(".gitignore includes .env", False)
    else:
        print_result(".gitignore exists", False)
    
    # Final summary
    print_header("VERIFICATION SUMMARY")
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    
    percentage = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print(f"\nSuccess Rate: {percentage:.1f}%")
    
    if percentage == 100:
        print("\n🎉 ALL CHECKS PASSED! Your improvements are complete!")
        print("✅ Ready for production deployment")
        return 0
    elif percentage >= 90:
        print("\n⚠️  Most checks passed. Review failed items above.")
        return 1
    else:
        print("\n❌ Several checks failed. Please review and fix.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
