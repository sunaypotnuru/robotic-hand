"""
LUNA - Automatic Dependency Fixer
Fixes common issues with MediaPipe, Google packages, etc.
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and show progress"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Success!")
            if result.stdout:
                print(result.stdout[:500])  # Show first 500 chars
            return True
        else:
            print(f"⚠️  Warning: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("🤖 LUNA Dependency Fixer")
    print("="*60)
    print("\nThis script will fix common dependency issues:")
    print("  1. MediaPipe module error")
    print("  2. Google generativeai package deprecation")
    print("  3. Optional: Install Whisper for voice recognition")
    
    print("\n" + "="*60)
    response = input("\nDo you want to proceed? (y/n): ").lower()
    
    if response != 'y':
        print("❌ Cancelled by user")
        return
    
    results = []
    
    # Fix 1: MediaPipe
    print("\n" + "="*60)
    print("Fix #1: MediaPipe")
    print("="*60)
    
    result1 = run_command(
        f"{sys.executable} -m pip uninstall mediapipe -y",
        "Uninstalling old MediaPipe"
    )
    
    result2 = run_command(
        f"{sys.executable} -m pip install mediapipe==0.10.9",
        "Installing MediaPipe 0.10.9"
    )
    
    results.append(("MediaPipe", result1 and result2))
    
    # Fix 2: Google Package
    print("\n" + "="*60)
    print("Fix #2: Google Generative AI Package")
    print("="*60)
    
    result3 = run_command(
        f"{sys.executable} -m pip uninstall google-generativeai -y",
        "Uninstalling deprecated google-generativeai"
    )
    
    result4 = run_command(
        f"{sys.executable} -m pip install google-genai",
        "Installing new google-genai package"
    )
    
    results.append(("Google Package", result3 and result4))
    
    # Fix 3: Whisper (Optional)
    print("\n" + "="*60)
    print("Fix #3: Whisper (Optional)")
    print("="*60)
    print("Whisper provides better offline voice recognition.")
    print("Current: Google Speech Recognition (works fine)")
    
    response = input("\nInstall Whisper? (y/n): ").lower()
    
    if response == 'y':
        result5 = run_command(
            f"{sys.executable} -m pip install openai-whisper",
            "Installing OpenAI Whisper"
        )
        results.append(("Whisper", result5))
    else:
        print("⏭️  Skipping Whisper installation")
        results.append(("Whisper", None))
    
    # Summary
    print("\n" + "="*60)
    print("📊 Summary")
    print("="*60)
    
    for name, result in results:
        if result is True:
            print(f"✅ {name}: Fixed")
        elif result is False:
            print(f"⚠️  {name}: Had issues (check logs above)")
        else:
            print(f"⏭️  {name}: Skipped")
    
    # Check Gemini API Key
    print("\n" + "="*60)
    print("🔑 Gemini API Key Check")
    print("="*60)
    
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            content = f.read()
            if "AIzaSyCkgQRy4tvAGCdtcfQpHPE1GmQjeTvubkY" in content:
                print("⚠️  WARNING: Your Gemini API key is EXPIRED!")
                print("\n📝 To fix:")
                print("   1. Go to: https://makersuite.google.com/app/apikey")
                print("   2. Create new API key")
                print("   3. Update .env file with new key")
                print("   4. Restart app: python app.py")
            else:
                print("✅ Gemini API key looks different (might be valid)")
    else:
        print("⚠️  .env file not found")
    
    print("\n" + "="*60)
    print("🎉 Dependency fixes complete!")
    print("="*60)
    print("\n📝 Next Steps:")
    print("   1. Update Gemini API key in .env (if expired)")
    print("   2. Restart app: python app.py")
    print("   3. Open browser: http://localhost:5000")
    print("\n✅ Your LUNA system should now work properly!")

if __name__ == "__main__":
    main()
