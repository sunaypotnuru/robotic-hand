# LUNA Quick Reference Card

## 🚀 Quick Start Commands

```bash
# Activate environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Start server
python app.py

# Run tests
pytest tests/ -v

# Create admin
python create_admin.py

# Download models
python download_models.py

# Fix dependencies
python fix_dependencies.py
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `app.py` | Main Flask application |
| `config.py` | Configuration settings |
| `.env` | Environment variables (API keys) |
| `requirements.txt` | Python dependencies |
| `database_schema.sql` | Database setup script |

---

## 📚 Documentation

| Document | Content |
|----------|---------|
| `README.md` | Project overview & quick start |
| `FEATURES.md` | All 28 features documented |
| `INSTALLATION.md` | Complete setup guide |
| `PROJECT_SUMMARY.md` | Project status & achievements |
| `CLEANUP_REPORT.md` | Cleanup details |

---

## 🌐 URLs

| URL | Page |
|-----|------|
| `http://localhost:5000` | Home page |
| `http://localhost:5000/login` | Login |
| `http://localhost:5000/register` | Register |
| `http://localhost:5000/dashboard` | Dashboard (after login) |
| `http://localhost:5000/admin` | Admin panel |
| `http://localhost:5000/logs` | Mission logs |
| `http://localhost:5000/video_feed` | Raw video feed |

---

## 🎮 Control Methods

1. **Virtual Joystick** - On-screen control
2. **Manual Sliders** - Precise positioning
3. **Gamepad** - Xbox/PlayStation controller
4. **Voice** - "Open hand", "Arm up", etc.
5. **Gestures** - Hand tracking
6. **Object Tracking** - Automatic pointing

---

## 🔑 Default Credentials

Created by `create_admin.py` - check console output for credentials.

**⚠️ Change password immediately after first login!**

---

## 🛠️ Motor IDs

| ID | Motor | Voltage |
|----|-------|---------|
| 2 | Main Pivot (Elbow) | 7.4V |
| 3 | Wrist Pitch | 7.4V |
| 4 | Wrist Roll | 7.4V |
| 5 | Thumb | 6V |
| 6 | Index Finger | 6V |
| 7 | Middle Finger | 6V |
| 8 | Ring Finger | 6V |
| 9 | Pinky | 6V |

**⚠️ IDs 0-1 are BLOCKED (removed shoulder)**

---

## 🔒 Security

### Rate Limits
- Login: 5 attempts/minute
- Motor commands: 100/minute
- API: 60/minute

### Roles
- **Operator:** Control robot, view own logs
- **Admin:** Full access + user/content management

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_motor_control.py -v

# Run verification
python verify_improvements.py
```

**Expected:** 22/22 tests passing

---

## 🐛 Troubleshooting

### Camera Not Working
```python
# In config.py, try different index:
CAMERA_INDEX = 1  # or 2, 3, etc.
```

### Serial Port Issues
```bash
# Windows: Check Device Manager
# Linux: ls /dev/tty*
# macOS: ls /dev/cu.*
```

### MediaPipe Error
```bash
pip uninstall mediapipe -y
pip install mediapipe==0.10.9
```

### Gemini API Error
1. Get new key: https://makersuite.google.com/app/apikey
2. Update `.env`: `GEMINI_API_KEY=your-new-key`
3. Restart server

---

## 📊 Database Tables

1. **users** - Authentication & profiles
2. **team_members** - Team page content
3. **site_content** - Dynamic content
4. **mission_logs** - Robot action history

---

## 🔧 Environment Variables

```env
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://...
GEMINI_API_KEY=your-gemini-key
SERIAL_PORT=COM3  # Optional
```

---

## 📦 Key Dependencies

- Flask 3.0 - Web framework
- Flask-SocketIO - Real-time communication
- YOLOv8 (ultralytics) - Object detection
- MediaPipe 0.10.9 - Hand tracking
- Google Gemini - Voice AI
- PySerial - Arduino communication
- SQLAlchemy - Database ORM

---

## 🎯 Quick Actions

### Emergency Stop
- Click "🛑 OVERRIDE STOP" button
- Say "Emergency stop"
- Wave gesture
- Distance < 10cm (auto)

### Home Position
- Click "Home" button
- Say "Home position"
- Thumbs up gesture

### Reset System
1. Click emergency stop
2. Refresh browser
3. Restart server if needed

---

## 📞 Support Checklist

When reporting issues, provide:

1. ✅ Browser console errors (F12)
2. ✅ Python console output
3. ✅ Arduino Serial Monitor output
4. ✅ Steps to reproduce
5. ✅ Expected vs actual behavior

---

## 🏆 Project Stats

- **Grade:** A (95%)
- **Features:** 28
- **Tests:** 22/22 passing
- **Lines of Code:** 5,000+
- **Documentation:** 5 files
- **Status:** Production Ready ✅

---

## 📱 Quick Tips

1. **Use SPA navigation** - No page reloads
2. **Check status indicators** - Connection, emergency, gamepad
3. **Monitor telemetry** - Distance, accelerometer
4. **Review logs** - Track all actions
5. **Test in simulation** - Arduino not required

---

## 🔗 Useful Links

- **Supabase:** https://supabase.com
- **Gemini API:** https://makersuite.google.com/app/apikey
- **YOLOv8 Docs:** https://docs.ultralytics.com
- **MediaPipe:** https://google.github.io/mediapipe
- **Flask Docs:** https://flask.palletsprojects.com

---

**Author:** Potnuru Sunay  
**Institution:** Universal AI University, Karjat  
**Last Updated:** March 3, 2026

---

**⚠️ Safety First:** Always maintain safe distance from moving parts!
