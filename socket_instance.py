from flask_socketio import SocketIO, join_room

socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet')

@socketio.on('connect')
def handle_connect():
    print('✅ Client connected')

@socketio.on('join')
def on_join(data):
    empId = data.get('empId')
    panelId = data.get('panelId')
    if empId:
        join_room(empId)
        print(f'🚪 User {empId} joined their room')

    if panelId:
        join_room(f"panel_{panelId}")
        print(f'👥 User {empId} also joined panel room panel_{panelId}')

@socketio.on('disconnect')
def handle_disconnect():
    print('❌ Client disconnected')
