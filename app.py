from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import cv2
import base64
import time
import mediapipe as mp
import pyttsx3
from math import dist
import mysql.connector
from mysql.connector import Error
import uuid
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

# Configuración de la conexión con MySQL
def create_connection():
    print("Intentando establecer una conexión...")
    try:
        # Intentamos conectarnos a MySQL
        connection = mysql.connector.connect(
            host='127.0.0.1',  # Cambia esto si usas un servidor remoto
            database='detencion_senas',
            user='root',
            password=''
        )
        # Comprobamos si la conexión es exitosa
        if connection.is_connected():
            print("Conexión establecida y exitosa a la base de datos MySQL.")
            return connection
        else:
            print("La conexión se estableció, pero no está completamente conectada.")
            return None
    except Error as e:
        print("Error al conectar con MySQL:", e)
        # Detalle del error
        if e.errno == 1049:
            print("Error: La base de datos 'detencion_senas' no existe.")
        elif e.errno == 1045:
            print("Error: Usuario o contraseña incorrectos.")
        elif e.errno == 2003:
            print("Error: MySQL no está disponible en la IP especificada.")
        else:
            print("Error desconocido:", e)
        return None

# Función para obtener usuario por correo
def get_user_by_email(email):
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM usuarios WHERE correo = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        return user
    return None

# Función para guardar el token de recuperación
def save_reset_token(user_id, token):
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        query = "UPDATE usuarios SET reset_token = %s WHERE id = %s"
        cursor.execute(query, (token, user_id))
        connection.commit()
        cursor.close()
        connection.close()

# Función para enviar el correo con el token
def send_email(to_email, token):
    from_email = "luisantonyhg@gmail.com"
    app_password = "tpkkbxxohfbextwf"  # Tu contraseña de aplicación de Google

    msg = MIMEText(f'Tu código de recuperación es: {token}')
    msg['Subject'] = 'Recuperación de contraseña'
    msg['From'] = from_email
    msg['To'] = to_email

    # Configuración del servidor SMTP usando SMTP_SSL para el puerto 465
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(from_email, app_password)
        server.sendmail(from_email, to_email, msg.as_string())

# Ruta para solicitar recuperación de contraseña
@app.route('/request_password_reset', methods=['POST'])
def request_password_reset():
    data = request.json
    email = data.get('email')

    # Verifica si el correo existe
    user = get_user_by_email(email)
    if not user:
        return jsonify({"mensaje": "El correo no está registrado"}), 404

    # Genera un token único
    token = str(uuid.uuid4())[:4]
    save_reset_token(user['id'], token)

    # Envía el token al correo del usuario
    send_email(email, token)
    return jsonify({"mensaje": "Correo de recuperación enviado"}), 200

# Función para verificar si el token es válido
def verify_token(token):
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT id FROM usuarios WHERE reset_token = %s"
        cursor.execute(query, (token,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        return user['id'] if user else None
    return None

# Ruta para verificar el token
@app.route('/verify_token', methods=['POST'])
def verify_token_route():
    data = request.json
    token = data.get('token')

    user_id = verify_token(token)
    if not user_id:
        return jsonify({"mensaje": "Token no válido o expirado"}), 400
    return jsonify({"mensaje": "Token válido", "user_id": user_id}), 200

# Función para actualizar la contraseña
def update_user_password(user_id, new_password):
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        query = "UPDATE usuarios SET contraseña = %s, reset_token = NULL WHERE id = %s"
        cursor.execute(query, (new_password, user_id))
        connection.commit()
        cursor.close()
        connection.close()

# Ruta para restablecer la contraseña
@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.json
    user_id = data.get('user_id')
    new_password = data.get('new_password')

    # Actualiza la contraseña en la base de datos
    update_user_password(user_id, new_password)
    return jsonify({"mensaje": "Contraseña actualizada con éxito"}), 200
    
@app.route('/test_connection', methods=['GET'])
def test_connection():
    connection = create_connection()
    if connection and connection.is_connected():
        connection.close()
        return jsonify({"mensaje": "Conexión a la base de datos exitosa"}), 200
    else:
        return jsonify({"mensaje": "Error al conectar con la base de datos"}), 500

# Ruta de inicio de sesión
@app.route('/login', methods=['POST'])
def login_user():
    data = request.json
    correo = data.get('correo')
    contraseña = data.get('contraseña')

    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM usuarios WHERE correo = %s AND contraseña = %s"
        values = (correo, contraseña)
        try:
            cursor.execute(query, values)
            user = cursor.fetchone()
            if user:
                return jsonify({"mensaje": "Inicio de sesión exitoso", "usuario": user}), 200
            else:
                return jsonify({"mensaje": "Correo o contraseña incorrectos"}), 401
        except Error as e:
            print("Error al verificar el usuario:", e)
            return jsonify({"mensaje": "Error al verificar el usuario"}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        return jsonify({"mensaje": "Error al conectar con la base de datos"}), 500

# Ruta para registrar un nuevo usuario
@app.route('/register', methods=['POST'])
def register_user():
    data = request.json
    nombre = data.get('nombre')
    correo = data.get('correo')
    contraseña = data.get('contrasena')

    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        query = "INSERT INTO usuarios (nombre, correo, contraseña) VALUES (%s, %s, %s)"
        values = (nombre, correo, contraseña)
        try:
            cursor.execute(query, values)
            connection.commit()
            return jsonify({"mensaje": "Usuario registrado exitosamente"}), 200
        except Error as e:
            print("Error al registrar usuario:", e)
            return jsonify({"mensaje": "Error al registrar el usuario"}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        return jsonify({"mensaje": "Error al conectar con la base de datos"}), 500

@app.route('/registrardetection', methods=['POST'])
def add_detection():
    data = request.json
    usuario_id = data.get('usuario_id')
    tipo_detencion = data.get('tipo_detencion')
    descripcion = data.get('descripcion')
    imagen_url = data.get('imagen_url')

    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        query = "INSERT INTO detenciones (usuario_id, tipo_detencion, descripcion, imagen_url) VALUES (%s, %s, %s, %s)"
        values = (usuario_id, tipo_detencion, descripcion, imagen_url)
        try:
            cursor.execute(query, values)
            connection.commit()
            return jsonify({"mensaje": "Detección registrada exitosamente"}), 200
        except Error as e:
            print("Error al registrar detección:", e)
            return jsonify({"mensaje": "Error al registrar la detección"}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        return jsonify({"mensaje": "Error al conectar con la base de datos"}), 500

@app.route('/get_user_detections', methods=['POST'])
def get_user_detections():
    data = request.json
    usuario_id = data.get('usuario_id')

    if not usuario_id:
        return jsonify({"mensaje": "usuario_id es requerido"}), 400

    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT d.id AS deteccion_id, d.fecha_detencion, d.tipo_detencion, 
               d.descripcion, d.imagen_url
        FROM detenciones d
        WHERE d.usuario_id = %s
        ORDER BY d.fecha_detencion DESC;
        """
        try:
            cursor.execute(query, (usuario_id,))
            detections = cursor.fetchall()

            if not detections:
                return jsonify({"mensaje": "No se encontraron detecciones para este usuario"}), 404

            # Estructuramos la respuesta
            historial = {
                "usuario_id": usuario_id,
                "detecciones": detections
            }

            return jsonify(historial), 200
        except Error as e:
            print("Error al obtener el historial de detecciones:", e)
            return jsonify({"mensaje": "Error al obtener el historial de detecciones"}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        return jsonify({"mensaje": "Error al conectar con la base de datos"}), 500

@app.route('/get_señas', methods=['GET'])
def get_señas():
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT id, nombre, categoria, descripcion, dificultad, imagen_url, video_url FROM señas ORDER BY orden ASC"
        try:
            cursor.execute(query)
            señas = cursor.fetchall()

            if not señas:
                return jsonify({"mensaje": "No se encontraron señas disponibles"}), 404

            return jsonify({"señas": señas}), 200
        except Error as e:
            print("Error al obtener señas:", e)
            return jsonify({"mensaje": "Error al obtener las señas"}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        return jsonify({"mensaje": "Error al conectar con la base de datos"}), 500

@app.route('/registrar_entrenamiento', methods=['POST'])
def registrar_entrenamiento():
    data = request.json
    usuario_id = data.get('usuario_id')
    seña_id = data.get('seña_id')
    veces_practicada = data.get('veces_practicada', 1)

    if not usuario_id or not seña_id:
        return jsonify({"mensaje": "usuario_id y seña_id son requeridos"}), 400

    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        query = """
        INSERT INTO detalles_entrenamiento (usuario_id, seña_id, veces_practicada) 
        VALUES (%s, %s, %s)
        """
        values = (usuario_id, seña_id, veces_practicada)
        try:
            cursor.execute(query, values)
            connection.commit()
            return jsonify({"mensaje": "Entrenamiento registrado exitosamente"}), 200
        except Error as e:
            print("Error al registrar entrenamiento:", e)
            return jsonify({"mensaje": "Error al registrar el entrenamiento"}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        return jsonify({"mensaje": "Error al conectar con la base de datos"}), 500

if __name__ == '__main__':
    connection = create_connection()
    if connection:
        print("Conexión probada exitosamente.")
    else:
        print("Fallo al intentar conectar a la base de datos.")
    app.run(debug=True, host='0.0.0.0', port=5000)

