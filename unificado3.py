from flask import Flask, request, jsonify
import base64
import cv2
import numpy as np
import mediapipe as mp
import math

app = Flask(__name__)

# Inicializar MediaPipe
mp_hands = mp.solutions.hands
mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils

# Constantes de tolerancia
TOLERANCIA_DISTANCIA = 0.05
TOLERANCIA_HORIZONTAL = 0.15
TOLERANCIA_VERTICAL = 0.1
TOLERANCIA_DISTANCIA_HOLA = 0.05
TOLERANCIA_DISTANCIA_CHAU = 0.05
TOLERANCIA_DISTANCIA_MENTON_DEDO = 0.05

# Puntos clave del rostro
PUNTOS_CLAVE = {
    "ojo_iz": 33,
    "ojo_de": 263,
    "nariz": 1,
    "menton": 152
}

def calculate_finger_angles(landmarks):
    # Obtener coordenadas de puntos clave para los dedos
    thumb_tip = landmarks[4]
    index_tip = landmarks[8]
    middle_tip = landmarks[12]
    ring_tip = landmarks[16]
    pinky_tip = landmarks[20]
    
    # Punto base de la palma
    palm_base = landmarks[0]
    
    # Verificar si los dedos están cerrados (excepto el pulgar)
    fingers_closed = all([
        middle_tip.y > landmarks[9].y,  # Dedo medio cerrado
        ring_tip.y > landmarks[13].y,   # Dedo anular cerrado
        pinky_tip.y > landmarks[17].y   # Dedo meñique cerrado
    ])
    
    # Verificar si el pulgar está pegado a la palma
    thumb_closed = thumb_tip.x < landmarks[2].x
    
    return fingers_closed and thumb_closed

def is_letter_a(hand_landmarks, ancho_imagen=None, alto_imagen=None):
    if not hand_landmarks:
        return False
        
    landmarks = []
    for landmark in hand_landmarks.landmark:
        landmarks.append(landmark)
    
    # Verificar la posición característica de la letra A
    return calculate_finger_angles(landmarks)

def detectar_letra_b(marcadores_mano, ancho_imagen, alto_imagen):
    y_base_indice = marcadores_mano.landmark[6].y * alto_imagen
    y_punta_indice = marcadores_mano.landmark[8].y * alto_imagen
    y_base_medio = marcadores_mano.landmark[10].y * alto_imagen
    y_punta_medio = marcadores_mano.landmark[12].y * alto_imagen
    y_base_anular = marcadores_mano.landmark[14].y * alto_imagen
    y_punta_anular = marcadores_mano.landmark[16].y * alto_imagen
    y_base_meñique = marcadores_mano.landmark[18].y * alto_imagen
    y_punta_meñique = marcadores_mano.landmark[20].y * alto_imagen

    dedos_extendidos = (
        y_base_indice > y_punta_indice and
        y_base_medio > y_punta_medio and
        y_base_anular > y_punta_anular and
        y_base_meñique > y_punta_meñique
    )
    dedos_escalonados = y_punta_medio < y_punta_anular

    y_punta_pulgar = marcadores_mano.landmark[4].y * alto_imagen
    y_base_mano = marcadores_mano.landmark[13].y * alto_imagen

    pulgar_recogido = abs(y_punta_pulgar - y_base_mano) < 5

    return dedos_extendidos and dedos_escalonados and pulgar_recogido


def detectar_palabra_amor(hand_landmarks, ancho_imagen, alto_imagen):
    """Detecta el gesto de la palabra 'amor' en lenguaje de señas peruano."""
    # Coordenadas de los puntos clave
    y_punta_indice = hand_landmarks.landmark[8].y * alto_imagen
    y_base_indice = hand_landmarks.landmark[6].y * alto_imagen
    y_punta_medio = hand_landmarks.landmark[10].y * alto_imagen
    y_base_medio = hand_landmarks.landmark[9].y * alto_imagen
    y_punta_anular = hand_landmarks.landmark[14].y * alto_imagen
    y_base_anular = hand_landmarks.landmark[13].y * alto_imagen
    y_punta_meñique = hand_landmarks.landmark[20].y * alto_imagen
    y_base_meñique = hand_landmarks.landmark[18].y * alto_imagen

    x_punta_pulgar = hand_landmarks.landmark[4].x * ancho_imagen
    x_centro_mano = hand_landmarks.landmark[9].x * ancho_imagen  # Punto de referencia central de la mano

    # Condiciones para el gesto de "amor"
    meñique_extendido = y_punta_meñique < y_base_meñique        
    indice_extendido = y_punta_indice < y_base_indice
    medio_recogido = abs(y_punta_medio - y_base_medio) < TOLERANCIA_DISTANCIA * alto_imagen
    anular_recogido = abs(y_punta_anular - y_base_anular) < TOLERANCIA_DISTANCIA * alto_imagen
    pulgar_lateral = abs(x_punta_pulgar - x_centro_mano) > 0.1 * ancho_imagen  # Pulgar separado hacia un lado

    # Verificar todas las condiciones juntas
    return indice_extendido and meñique_extendido and medio_recogido and anular_recogido and pulgar_lateral

def detectar_palabra_chocardedos(mano_izquierda, mano_derecha, ancho_imagen, alto_imagen):
    """Detecta el gesto de la palabra 'hola' cuando las puntas de los índices de ambas manos están unidas."""

    # Coordenadas de las puntas de los índices de ambas manos
    x_punta_indice_izq = mano_izquierda.landmark[8].x * ancho_imagen
    y_punta_indice_izq = mano_izquierda.landmark[8].y * alto_imagen

    x_punta_indice_der = mano_derecha.landmark[8].x * ancho_imagen
    y_punta_indice_der = mano_derecha.landmark[8].y * alto_imagen

    # Calcular la distancia entre las puntas de los índices
    distancia = math.dist((x_punta_indice_izq, y_punta_indice_izq), (x_punta_indice_der, y_punta_indice_der))

    # Verificar si la distancia es menor que la tolerancia para detectar el gesto
    return distancia < TOLERANCIA_DISTANCIA_HOLA * ancho_imagen

def detectar_dedo_medio_en_menton(hand_landmarks, menton, ancho_imagen, alto_imagen):
    """Detecta el gesto de 'comer' cuando el dedo medio se acerca al mentón."""
    # Coordenadas del dedo medio (punto 10)
    x_dedo_medio = hand_landmarks.landmark[10].x * ancho_imagen
    y_dedo_medio = hand_landmarks.landmark[10].y * alto_imagen

    # Coordenadas del mentón (punto 152)
    x_menton = menton.x * ancho_imagen
    y_menton = menton.y * alto_imagen

    # Calcular la distancia entre el dedo medio y el mentón
    distancia = math.dist((x_dedo_medio, y_dedo_medio), (x_menton, y_menton))

    # Retorna True si la distancia es menor que la tolerancia
    return distancia < TOLERANCIA_DISTANCIA_MENTON_DEDO * ancho_imagen

# Diccionario de funciones de detección
FUNCIONES_DETECCION = {
    "A": is_letter_a,
    "AMOR": detectar_palabra_amor,
    "COMER": detectar_dedo_medio_en_menton,
    "B": detectar_letra_b
}

def procesar_mediapipe(image):
    drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1)
    
    with mp_hands.Hands(static_image_mode=True, max_num_hands=2, min_detection_confidence=0.5) as hands, \
         mp_face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, min_detection_confidence=0.5) as face_mesh:
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Procesar manos
        hand_results = hands.process(image_rgb)
        # Procesar rostro
        face_results = face_mesh.process(image_rgb)
        
        # Crear una copia de la imagen para dibujar
        annotated_image = image.copy()
        
        detected_gestos = []
        
        # Variables para detección de "hola" mediante "chocar dedos"
        mano_izquierda = None
        mano_derecha = None

        # Obtener puntos clave del rostro
        menton = None
        if face_results.multi_face_landmarks:
            for landmarks_rostro in face_results.multi_face_landmarks:
                menton = landmarks_rostro.landmark[PUNTOS_CLAVE["menton"]]
                break  # Solo se procesa la primera cara

        # Dibujar landmarks faciales
        if face_results.multi_face_landmarks:
            for face_landmarks in face_results.multi_face_landmarks:
                mp_drawing.draw_landmarks(
                    image=annotated_image,
                    landmark_list=face_landmarks,
                    connections=mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=drawing_spec,
                    connection_drawing_spec=drawing_spec)

        # Dibujar landmarks de las manos y detectar gestos
        if hand_results.multi_hand_landmarks:
            for i, hand_landmarks in enumerate(hand_results.multi_hand_landmarks):
                hand_type = hand_results.multi_handedness[i].classification[0].label  # "Left" or "Right"
                
                # Asignar la mano detectada como izquierda o derecha
                if hand_type == "Left":
                    mano_izquierda = hand_landmarks
                else:
                    mano_derecha = hand_landmarks

                # Dibujar los landmarks de la mano
                mp_drawing.draw_landmarks(
                    annotated_image,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    landmark_drawing_spec=drawing_spec,
                    connection_drawing_spec=drawing_spec)
                
                # Obtener dimensiones de la imagen
                alto_imagen, ancho_imagen, _ = image.shape
                
                # Iterar sobre cada gesto y verificar si se detecta
                for gesto, detector in FUNCIONES_DETECCION.items():
                    if gesto == "HOLA_CHOCAR_DEDOS":
                        continue  # Este gesto requiere ambas manos
                    elif gesto == "COMER":
                        if menton:
                            if detector(hand_landmarks, menton, ancho_imagen, alto_imagen):
                                if gesto not in detected_gestos:
                                    detected_gestos.append(gesto)
                                    cv2.putText(annotated_image, gesto, (50, 150),
                                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    else:
                        if detector(hand_landmarks, ancho_imagen, alto_imagen):
                            if gesto not in detected_gestos:
                                detected_gestos.append(gesto)
                                cv2.putText(annotated_image, gesto, (50, 50),
                                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Detectar "HOLA_CHOCAR_DEDOS" si ambas manos están presentes
        if mano_izquierda and mano_derecha:
            if detectar_palabra_chocardedos(mano_izquierda, mano_derecha, ancho_imagen, alto_imagen):
                if "HOLA_CHOCAR_DEDOS" not in detected_gestos:
                    detected_gestos.append("HOLA_CHOCAR_DEDOS")
                    cv2.putText(annotated_image, "HOLA", (50, 100),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Verificar si se detectaron gestos
        if detected_gestos:
            resultado = "Gestos detectados: " + ", ".join(detected_gestos)
            return resultado, annotated_image
        else:
            return "No se detectaron gestos conocidos", annotated_image

@app.route('/process_image', methods=['POST'])
def process_image():
    try:
        data = request.json
        image_data = base64.b64decode(data['image'])
        np_image = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_image, cv2.IMREAD_COLOR)

        resultado, processed_image = procesar_mediapipe(image)
        
        # Convertir la imagen procesada de nuevo a base64
        _, buffer = cv2.imencode('.jpg', processed_image)
        processed_image_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'resultado': resultado,
            'processed_image': processed_image_b64
        })
    except Exception as e:
        return jsonify({
            'resultado': f"Error en el procesamiento: {str(e)}",
            'processed_image': None
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000, debug=True)

