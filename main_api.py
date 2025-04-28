from flask import Flask, request, jsonify
import face_recognition
import psycopg2
import numpy as np
import os
import logging
from typing import List
from PIL import Image
from datetime import datetime
import threading
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('face_encoding.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Функция для отложенного удаления файлов
def delayed_delete(file_paths, delay_seconds):
    try:
        time.sleep(delay_seconds)
        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Файл {file_path} удалён после задержки")
    except Exception as e:
        logger.error(f"Ошибка при отложенном удалении файлов: {e}")

# Подключение к PostgreSQL
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname="encoding_photos",
            user="dmitry",
            password="dmitry",
            host="localhost",
            port="5432"
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        raise ValueError(f"Не удалось подключиться к базе данных: {str(e)}")

# Функция для извлечения энкодингов и координат лиц
def extract_face_encodings(image_path: str) -> tuple[List[np.ndarray], List[tuple]]:
    try:
        if not os.path.exists(image_path):
            logger.error(f"Изображение не найдено: {image_path}")
            raise ValueError("Файл изображения не найден")

        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        locations = face_recognition.face_locations(image)

        if len(encodings) == 0:
            logger.warning(f"Лица не найдены в изображении: {image_path}")
            raise ValueError("Лица не найдены на изображении")

        logger.info(f"Найдено {len(encodings)} лиц в изображении: {image_path}")
        return encodings, locations
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения {image_path}: {e}")
        raise

# Функция для сохранения обрезанных лиц
def save_cropped_faces(image_path: str, locations: List[tuple], filename: str) -> List[str]:
    faces_dir = "/opt/lampp/htdocs/faces"
    os.makedirs(faces_dir, exist_ok=True)
    face_paths = []

    try:
        image = Image.open(image_path)
        for i, (top, right, bottom, left) in enumerate(locations):
            face_image = image.crop((left, top, right, bottom))
            face_path = os.path.join(faces_dir, f"{os.path.splitext(filename)[0]}_face_{i+1}.png")
            face_image.save(face_path)
            face_paths.append(face_path)
            logger.info(f"Сохранено обрезанное лицо: {face_path}")
        return face_paths
    except Exception as e:
        logger.error(f"Ошибка при сохранении обрезанных лиц: {e}")
        return []

# Маршрут для обработки изображения
@app.route('/process_image', methods=['POST'])
def process_image():
    if 'image' not in request.files:
        logger.error("Изображение не предоставлено в запросе")
        return jsonify({'error': 'Изображение не предоставлено'}), 400

    file = request.files['image']
    recognition_dir = "recognition"
    os.makedirs(recognition_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = os.path.join(recognition_dir, f"{timestamp}_{file.filename}")

    try:
        file.save(image_path)
        logger.info(f"Сохранено изображение: {image_path}")
    except Exception as e:
        logger.error(f"Ошибка сохранения файла {file.filename}: {e}")
        return jsonify({'error': f"Не удалось сохранить изображение: {str(e)}"}), 500

    try:
        # Извлечение энкодингов и координат лиц
        encodings, locations = extract_face_encodings(image_path)

        # Сохранение обрезанных лиц
        face_paths = save_cropped_faces(image_path, locations, f"{timestamp}_{file.filename}")

        # Подключение к БД
        conn = get_db_connection()
        cursor = conn.cursor()

        # Извлечение энкодингов из БД
        cursor.execute("SELECT id, name, face_encoding, image_id FROM faces")
        rows = cursor.fetchall()

        results = []
        # Сравнение каждого лица
        for i, encoding in enumerate(encodings):
            face_results = {
                'face_number': i + 1,
                'matches': [],
                'face_image_path': face_paths[i] if i < len(face_paths) else None
            }
            for row in rows:
                db_encoding = np.array(row[2])
                match = face_recognition.compare_faces([db_encoding], encoding, tolerance=0.5)[0]
                if match:
                    image_id = row[3]
                    logger.info(f"Файлы в uploads/ перед обработкой: {os.listdir('uploads')}")
                    possible_extensions = ['.png', '.jpg', '.jpeg']
                    matched_image_path = None
                    for ext in possible_extensions:
                        candidate_path = os.path.join('uploads', f"{image_id}{ext}")
                        if os.path.exists(candidate_path):
                            matched_image_path = candidate_path
                            break
                    if not matched_image_path:
                        logger.warning(f"Оригинальное изображение для image_id {image_id} не найдено в uploads/")

                    face_results['matches'].append({
                        'id': row[0],
                        'name': row[1],
                        'image_id': image_id,
                        'image_path': matched_image_path
                    })
            results.append(face_results)

        conn.close()

        # Запуск отложенного удаления (5 минут = 300 секунд)
        all_paths = [image_path] + face_paths
        threading.Thread(target=delayed_delete, args=(all_paths, 300)).start()

        return jsonify({'results': results}), 200

    except ValueError as e:
        logger.info(f"Файл {image_path} не удалён из-за ошибки: {e}")
        return jsonify({'error': str(e)}), 400
    except psycopg2.Error as e:
        logger.error(f"Ошибка базы данных: {e}")
        logger.info(f"Файл {image_path} не удалён из-за ошибки БД")
        return jsonify({'error': f"Ошибка базы данных: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        logger.info(f"Файл {image_path} не удалён из-за неизвестной ошибки")
        return jsonify({'error': f"Внутренняя ошибка сервера: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)