"""
LUNA WebRTC Signaling Module
Exchanges peer-to-peer candidates and descriptions for low-latency control streams.
"""

from flask import request
from flask_socketio import Namespace, emit, join_room, leave_room
import logging

logger = logging.getLogger("LUNA.WebRTC")


class WebRTCSignalingNamespace(Namespace):
    """
    Socket.IO namespace handler for low-latency WebRTC P2P connection signaling (Resolved Feature 5)
    """
    
    def on_connect(self):
        logger.info(f"[WebRTC] Signaling client connected: {request.sid}")

    def on_disconnect(self):
        logger.info(f"[WebRTC] Signaling client disconnected: {request.sid}")

    def on_join(self, data):
        room = data.get('room', 'remote-lobby')
        join_room(room)
        logger.info(f"[WebRTC] Client {request.sid} joined signaling room: {room}")
        # Notify other peers in the room
        emit('peer_joined', {'sid': request.sid}, room=room, include_self=False)

    def on_offer(self, data):
        room = data.get('room', 'remote-lobby')
        logger.info(f"[WebRTC] Forwarding SDP Offer from {request.sid} to room {room}")
        emit('offer', {
            'sdp': data.get('sdp'),
            'sid': request.sid
        }, room=room, include_self=False)

    def on_answer(self, data):
        room = data.get('room', 'remote-lobby')
        logger.info(f"[WebRTC] Forwarding SDP Answer from {request.sid} to room {room}")
        emit('answer', {
            'sdp': data.get('sdp'),
            'sid': request.sid
        }, room=room, include_self=False)

    def on_ice_candidate(self, data):
        room = data.get('room', 'remote-lobby')
        emit('ice_candidate', {
            'candidate': data.get('candidate'),
            'sid': request.sid
        }, room=room, include_self=False)
