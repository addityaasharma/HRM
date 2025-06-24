from flask_socketio import SocketIO, join_room, emit

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

        emit('user_connected', {
            'message': f'User {empId} connected.',
            'empId': empId
        }, room=empId)

    if panelId:
        room_name = f"panel_{panelId}"
        join_room(room_name)
        print(f'👥 User {empId} also joined panel room {room_name}')

        emit('user_connected_panel', {
            'message': f'User {empId} joined panel room.',
            'empId': empId,
            'panel': panelId
        }, room=room_name)

@socketio.on('disconnect')
def handle_disconnect():
    print('❌ Client disconnected')
