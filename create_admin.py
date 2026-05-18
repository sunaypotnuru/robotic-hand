import os
from app import app, db, User, SiteContent, TeamMember
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def bootstrap():
    with app.app_context():
        print("[SETUP] LUNA Administrative Bootstrapper")
        
        # 1. Create Tables
        db.create_all()
        print("[SUCCESS] Database tables created.")

        # 2. Create Admin User from environment variables
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@luna.local')
        admin_password = os.getenv('ADMIN_PASSWORD')
        
        if not admin_password:
            print("[ERROR] ADMIN_PASSWORD not set in .env file")
            print("   Please create a .env file with ADMIN_PASSWORD=your-secure-password")
            return
        
        admin_user = User.query.filter_by(username=admin_email).first()
        if not admin_user:
            new_admin = User(username=admin_email, role='admin')
            new_admin.set_password(admin_password)
            db.session.add(new_admin)
            print(f"[SUCCESS] Admin user created: {admin_email}")
            print(f"   Password: (stored securely from .env)")
        else:
            admin_user.set_password(admin_password)
            print(f"[SUCCESS] Admin user {admin_email} already exists. Password updated to match .env")

        # 3. Populate Initial CMS Content
        initial_content = {
            'about_description': 'Project LUNA is a 4-DOF robotic system integrated with Gemini AI.',
            'contact_email': 'luna@invicta.io',
            'contact_phone': '+1 555-LUNA',
            'contact_address': 'Grid Sector 7, Neo-Tech District',
            'contact_github': 'https://github.com/sunaypotnuru/Healix',
            'contact_linkedin': 'https://linkedin.com/company/invicta-labs'
        }

        for section, content in initial_content.items():
            if not SiteContent.query.filter_by(page_section=section).first():
                db.session.add(SiteContent(page_section=section, content_text=content))
        
        print("[SUCCESS] Initial CMS content populated.")

        # 4. Create Initial Team Members
        if not TeamMember.query.first():
            members = [
                TeamMember(name="Sunay", role="Computer Vision Specialist", bio="Expert in YOLOv8 and MediaPipe."),
                TeamMember(name="Rohith", role="Systems Architect", bio="Lead developer of LUNA AI."),
                TeamMember(name="Vamsi", role="Firmware Engineer", bio="ESP32 and Arduino logic designer.")
            ]
            db.session.add_all(members)
            print("[SUCCESS] Initial team members added.")

        db.session.commit()
        print("\n[SUCCESS] LUNA System Ready. Run 'python app.py' to start.")

if __name__ == "__main__":
    bootstrap()
