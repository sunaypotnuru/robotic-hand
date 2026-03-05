"""
Test Dual YOLO Implementation
"""

import sys
import os

def test_imports():
    """Test if all modules can be imported"""
    print("=" * 60)
    print("1️⃣  Testing Module Imports")
    print("=" * 60)
    
    tests = []
    
    # Test object detector
    try:
        from web_interface.ai_modules.object_detect import ObjectDetector
        print("✅ ObjectDetector imported")
        tests.append(("ObjectDetector", True))
    except Exception as e:
        print(f"❌ ObjectDetector import failed: {e}")
        tests.append(("ObjectDetector", False))
    
    # Test hand detector
    try:
        from web_interface.ai_modules.hand_detect import HandDetector
        print("✅ HandDetector imported")
        tests.append(("HandDetector", True))
    except Exception as e:
        print(f"❌ HandDetector import failed: {e}")
        tests.append(("HandDetector", False))
    
    # Test gesture classifier
    try:
        from web_interface.ai_modules.gesture_classifier import GestureClassifier
        print("✅ GestureClassifier imported")
        tests.append(("GestureClassifier", True))
    except Exception as e:
        print(f"❌ GestureClassifier import failed: {e}")
        tests.append(("GestureClassifier", False))
    
    # Test vision processor
    try:
        from web_interface.ai_modules.vision_processor import VisionProcessor
        print("✅ VisionProcessor imported")
        tests.append(("VisionProcessor", True))
    except Exception as e:
        print(f"❌ VisionProcessor import failed: {e}")
        tests.append(("VisionProcessor", False))
    
    # Test hand tracker (fallback)
    try:
        from web_interface.ai_modules.hand_tracking import HandTracker
        print("✅ HandTracker (MediaPipe fallback) imported")
        tests.append(("HandTracker", True))
    except Exception as e:
        print(f"❌ HandTracker import failed: {e}")
        tests.append(("HandTracker", False))
    
    return tests

def test_initialization():
    """Test if detectors can be initialized"""
    print("\n" + "=" * 60)
    print("2️⃣  Testing Detector Initialization")
    print("=" * 60)
    
    tests = []
    
    # Test object detector
    try:
        from web_interface.ai_modules.object_detect import ObjectDetector
        od = ObjectDetector()
        if od.model is not None:
            print("✅ ObjectDetector initialized successfully")
            tests.append(("ObjectDetector init", True))
        else:
            print("⚠️  ObjectDetector initialized but model is None")
            tests.append(("ObjectDetector init", False))
    except Exception as e:
        print(f"❌ ObjectDetector initialization failed: {e}")
        tests.append(("ObjectDetector init", False))
    
    # Test hand detector
    try:
        from web_interface.ai_modules.hand_detect import HandDetector
        hd = HandDetector()
        if hd.model is not None:
            print("✅ HandDetector initialized successfully")
            tests.append(("HandDetector init", True))
        else:
            print("⚠️  HandDetector initialized but model is None (will use MediaPipe)")
            tests.append(("HandDetector init", False))
    except Exception as e:
        print(f"❌ HandDetector initialization failed: {e}")
        tests.append(("HandDetector init", False))
    
    # Test gesture classifier
    try:
        from web_interface.ai_modules.gesture_classifier import GestureClassifier
        gc = GestureClassifier()
        print("✅ GestureClassifier initialized successfully")
        tests.append(("GestureClassifier init", True))
    except Exception as e:
        print(f"❌ GestureClassifier initialization failed: {e}")
        tests.append(("GestureClassifier init", False))
    
    # Test vision processor
    try:
        from web_interface.ai_modules.vision_processor import VisionProcessor
        vp = VisionProcessor()
        vp.initialize()
        print("✅ VisionProcessor initialized successfully")
        tests.append(("VisionProcessor init", True))
    except Exception as e:
        print(f"❌ VisionProcessor initialization failed: {e}")
        tests.append(("VisionProcessor init", False))
    
    return tests

def test_models():
    """Test if model files exist"""
    print("\n" + "=" * 60)
    print("3️⃣  Testing Model Files")
    print("=" * 60)
    
    tests = []
    
    models = [
        ("models/yolov8m.pt", "Object Detection (YOLOv8m)"),
        ("models/yolov8n-hand.pt", "Hand Detection (YOLOv8n-pose)"),
    ]
    
    for path, name in models:
        if os.path.exists(path):
            size = os.path.getsize(path) / (1024 * 1024)  # MB
            print(f"✅ {name:35} | {path:30} | {size:.1f} MB")
            tests.append((name, True))
        else:
            print(f"❌ {name:35} | {path:30} | NOT FOUND")
            tests.append((name, False))
    
    return tests

def test_config():
    """Test configuration"""
    print("\n" + "=" * 60)
    print("4️⃣  Testing Configuration")
    print("=" * 60)
    
    tests = []
    
    try:
        import config
        
        # Check dual YOLO setting
        use_dual = getattr(config, 'USE_DUAL_YOLO', False)
        print(f"{'✅' if use_dual else '⚠️ '} USE_DUAL_YOLO: {use_dual}")
        tests.append(("USE_DUAL_YOLO", use_dual))
        
        # Check model paths
        obj_path = getattr(config, 'YOLO_OBJECT_MODEL_PATH', None)
        print(f"{'✅' if obj_path else '❌'} YOLO_OBJECT_MODEL_PATH: {obj_path}")
        tests.append(("YOLO_OBJECT_MODEL_PATH", obj_path is not None))
        
        hand_path = getattr(config, 'YOLO_HAND_MODEL_PATH', None)
        print(f"{'✅' if hand_path else '❌'} YOLO_HAND_MODEL_PATH: {hand_path}")
        tests.append(("YOLO_HAND_MODEL_PATH", hand_path is not None))
        
        # Check thresholds
        obj_conf = getattr(config, 'OBJECT_CONFIDENCE_THRESHOLD', None)
        print(f"✅ OBJECT_CONFIDENCE_THRESHOLD: {obj_conf}")
        tests.append(("OBJECT_CONFIDENCE_THRESHOLD", True))
        
        hand_conf = getattr(config, 'HAND_CONFIDENCE_THRESHOLD', None)
        print(f"✅ HAND_CONFIDENCE_THRESHOLD: {hand_conf}")
        tests.append(("HAND_CONFIDENCE_THRESHOLD", True))
        
        # Check gesture commands
        gestures = getattr(config, 'GESTURE_COMMANDS', {})
        print(f"✅ GESTURE_COMMANDS: {len(gestures)} gestures configured")
        tests.append(("GESTURE_COMMANDS", len(gestures) > 0))
        
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        tests.append(("Config", False))
    
    return tests

def print_summary(all_tests):
    """Print test summary"""
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    total = len(all_tests)
    passed = sum(1 for _, result in all_tests if result)
    failed = total - passed
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    if failed > 0:
        print("\n❌ Failed Tests:")
        for name, result in all_tests:
            if not result:
                print(f"   - {name}")
    
    print("\n" + "=" * 60)
    
    if failed == 0:
        print("🎉 All tests passed! Dual YOLO system is ready!")
        print("\n📝 Next Steps:")
        print("   1. Run: python app.py")
        print("   2. Open: http://localhost:5000")
        print("   3. Enable object detection and hand tracking")
        print("   4. Test gesture recognition")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("\n💡 Troubleshooting:")
        print("   - Run: python download_models.py")
        print("   - Check: pip install ultralytics>=8.1.0")
        print("   - Verify: models/ directory exists")
        print("   - Review: config.py settings")
        return False

def main():
    """Run all tests"""
    print("\n🤖 LUNA Dual YOLO System - Test Suite")
    print("=" * 60)
    
    all_tests = []
    
    # Run tests
    all_tests.extend(test_imports())
    all_tests.extend(test_initialization())
    all_tests.extend(test_models())
    all_tests.extend(test_config())
    
    # Print summary
    success = print_summary(all_tests)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
