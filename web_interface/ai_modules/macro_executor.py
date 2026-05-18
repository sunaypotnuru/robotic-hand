"""
LUNA Macro Executor Module
Handles multi-step sequences with state monitoring, Socket.IO updates, and emergency cancellation hooks.
"""

import threading
import time
import logging

logger = logging.getLogger("LUNA.Macro")


class MacroExecutor:
    """
    State-machine for executing atomic robotic macros (move, grab, release, wait) (Resolved Feature 3)
    """
    
    def __init__(self, socketio=None, command_sender=None):
        """
        Initialize Macro Executor
        
        Args:
            socketio: Active Flask-SocketIO server instance
            command_sender: Callback to direct motor operations in the motion loop
        """
        self.socketio = socketio
        self.command_sender = command_sender
        self.is_running = False
        self.current_step = 0
        self.actions = []
        self.lock = threading.Lock()
        self.thread = None
        self.cancel_requested = False

    def start_macro(self, actions_list):
        """Start executing a macro sequence"""
        with self.lock:
            if self.is_running:
                logger.warning("⚠️ A macro sequence is currently running. Cancelling active macro first.")
                self.cancel_macro()
            
            self.actions = actions_list
            self.current_step = 0
            self.is_running = True
            self.cancel_requested = False
            self.thread = threading.Thread(target=self._run_macro, daemon=True)
            self.thread.start()

    def cancel_macro(self):
        """Cancel the active macro immediately (e.g., on Emergency Stop)"""
        with self.lock:
            if self.is_running:
                self.cancel_requested = True
                self.is_running = False
                logger.info("🛑 Macro execution cancelled successfully by safety trigger.")

    def _run_macro(self):
        logger.info(f"🚀 Initializing macro execution: {len(self.actions)} steps detected.")
        if self.socketio:
            self.socketio.emit('macro_status', {'state': 'started', 'total_steps': len(self.actions)})

        for idx, action in enumerate(self.actions):
            if self.cancel_requested:
                break
            
            self.current_step = idx
            action_type = action.get("type", "").lower()
            target = action.get("target", None)
            duration = float(action.get("duration", 1.0))
            
            logger.info(f"[MACRO STEP {idx}] Active Action: {action_type} | Target: {target}")
            if self.socketio:
                self.socketio.emit('macro_step', {
                    'step': idx,
                    'action': action_type,
                    'target': target,
                    'total_steps': len(self.actions)
                })

            # Execute individual action using movement dispatcher
            try:
                if action_type == "move":
                    if self.command_sender and target:
                        self.command_sender(action_type, target, duration)
                elif action_type == "grab":
                    if self.command_sender:
                        self.command_sender(action_type, None, duration)
                elif action_type == "release":
                    if self.command_sender:
                        self.command_sender(action_type, None, duration)
                elif action_type == "wait":
                    if self.command_sender:
                        self.command_sender(action_type, None, duration)
                    # Non-blocking sleep intervals to allow instant emergency stop responses
                    start_time = time.time()
                    while time.time() - start_time < duration:
                        if self.cancel_requested:
                            break
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"❌ Error executing macro instruction index {idx}: {e}")

            time.sleep(0.4)  # Small stabilization delay between command frames

        self.is_running = False
        state = 'completed' if not self.cancel_requested else 'cancelled'
        logger.info(f"🏁 Macro sequence execution: {state.upper()}.")
        if self.socketio:
            self.socketio.emit('macro_status', {
                'state': state,
                'completed_steps': self.current_step + 1 if state == 'completed' else self.current_step
            })
