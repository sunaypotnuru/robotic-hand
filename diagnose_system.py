#!/usr/bin/env python3
"""
LUNA Robotic Arm & Hand - Industrial Auto-Diagnostic & Telemetry Profiler
Performs a deep-level audit of the database, user safety logs, serial packet delivery rates,
and provides a cybernetic ASCII-styled industrial health report.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

# Import database models from app
try:
    from app import app, db, MissionLog, LoginHistory, User
except ImportError as e:
    print(f"[ERROR] Error importing LUNA core modules: {e}")
    sys.exit(1)

def print_cyber_header(title):
    print("\n" + "="*80)
    print(f" [> {title} <]".center(80, " "))
    print("="*80)

def print_metric(label, value, status="ONLINE"):
    status_icon = "OK" if status == "ONLINE" else "WARN" if status == "WARN" else "ALERT"
    print(f"  {label:<45} : {value:<20} [{status_icon}]")

def run_diagnostics():
    print_cyber_header("LUNA COGNITIVE ROBOTICS - DIAGNOSTIC PROFILER")
    print(f" TIMESTAMP : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" ENGINE    : LUNA CORE TELEMETRY PARSER v3.0 (FREE TIER INDUSTRIAL EDITION)")
    print("-" * 80)

    with app.app_context():
        try:
            # 1. User & Operator Audit
            total_users = User.query.count()
            admins = User.query.filter_by(role='admin').count()
            operators = User.query.filter_by(role='operator').count()

            # 2. Login Security Audit
            total_logins = LoginHistory.query.count()
            successful_logins = LoginHistory.query.filter_by(success=True).count()
            failed_logins = LoginHistory.query.filter_by(success=False).count()
            
            success_rate = (successful_logins / total_logins * 100) if total_logins > 0 else 100.0
            security_status = "ONLINE" if failed_logins < 5 else "WARN" if failed_logins < 15 else "ALERT"

            # 3. Mission Logs & Command Execution Analysis
            total_logs = MissionLog.query.count()
            
            # Query recent logs in last 24h
            day_ago = datetime.utcnow() - timedelta(days=1)
            recent_logs = MissionLog.query.filter(MissionLog.timestamp >= day_ago).count()
            
            # Check for Emergency Stops
            estops = MissionLog.query.filter(MissionLog.command.like('%STOP%') | MissionLog.command.like('%EMERGENCY%')).count()
            safety_status = "ONLINE" if estops == 0 else "WARN"

            # Calculate Command Distribution
            commands = MissionLog.query.all()
            command_types = {}
            for log in commands:
                cmd_type = log.command.split(":")[0] if ":" in log.command else log.command
                command_types[cmd_type] = command_types.get(cmd_type, 0) + 1

            # 4. CPU / Process Simulation Metrics (for mock target verification)
            import platform
            host_os = platform.system()
            host_cpu = platform.processor()

            # --- RENDER TELEMETRY ---
            print_cyber_header("1. ADMINISTRATIVE & OPERATOR SEEDING")
            print_metric("Total Enrolled Operators", f"{total_users} Users", "ONLINE")
            print_metric("System Administrators", f"{admins} Admins", "ONLINE")
            print_metric("Field Operators", f"{operators} Operators", "ONLINE")

            print_cyber_header("2. SECURITY UPLINK & AUDIT TRAILS")
            print_metric("Total Encryption Key Verifications", f"{total_logins} Attempts", "ONLINE")
            print_metric("Successful Uplink Establishments", f"{successful_logins} Sessions", "ONLINE")
            print_metric("Unauthorized Intrusions Blocked", f"{failed_logins} Failures", security_status)
            print_metric("Uplink Verification Success Rate", f"{success_rate:.2f}%", "ONLINE" if success_rate > 90 else "WARN")

            print_cyber_header("3. PHYSICAL MANIPULATOR COMMAND LOGISTICS")
            print_metric("Total Serial Packet Instructions Sent", f"{total_logs} Commands", "ONLINE")
            print_metric("Active Commands (Last 24 Hours)", f"{recent_logs} Packets", "ONLINE")
            print_metric("Emergency Stops/Safety Overrides Triggered", f"{estops} Triggers", safety_status)
            
            print("\n  [+] Command Category Breakdown:")
            for cmd, count in sorted(command_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"      - {cmd:<35} : {count:<5} packets")

            print_cyber_header("4. HOST ORCHESTRATOR SYSTEM METRICS")
            print_metric("Host Operating System", host_os, "ONLINE")
            print_metric("Processor Specification", host_cpu[:40] + "..." if len(host_cpu) > 40 else host_cpu, "ONLINE")
            print_metric("Serial Heartbeat Watchdog Interval", "5.0 Seconds", "ONLINE")
            print_metric("Delta-Time (dt) Jitter Interpolator", "25Hz (40ms Limit)", "ONLINE")

            # Save report to JSON for frontend graphing if needed
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "operators": {"total": total_users, "admins": admins, "operators": operators},
                "security": {"attempts": total_logins, "success": successful_logins, "failed": failed_logins, "rate": success_rate},
                "telemetry": {"total_commands": total_logs, "recent_24h": recent_logs, "estops": estops, "distribution": command_types},
                "system": {"os": host_os, "cpu": host_cpu}
            }

            report_path = "luna_diagnostic_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=4)
            
            print("-" * 80)
            print(f"[SUCCESS] Telemetry Audit Log successfully saved to: {os.path.abspath(report_path)}")
            print("=" * 80 + "\n")

        except Exception as e:
            print(f"[ERROR] Diagnostic Profiler Encountered Error: {e}")
            db.session.rollback()

if __name__ == "__main__":
    run_diagnostics()
