from flask import Flask, request, jsonify
import face_recognition
import psycopg2
import numpy as np
import os
import logging
from typing import List

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


# Функция для извлечения энкодингов лиц из изображения
def extract_face_encodings(image_path: str) -> List[np.ndarray]:
    try:
        if not os.path.exists(image_path):
            logger.error(f"Изображение не найдено: {image_path}")
            raise ValueError("Файл изображения не найден")

        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)

        if len(encodings) == 0:
            logger.warning(f"Лица не найдены в изображении: {image_path}")
            raise ValueError("Лица не найдены на изображении")

        logger.info(f"Найдено {len(encodings)} лиц в изображении: {image_path}")
        return encodings
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения {image_path}: {e}")
        raise


# Маршрут для обработки изображения
@app.route('/process_image', methods=['POST'])
def process_image():
    if 'image' not in request.files:
        logger.error("Изображение не предоставлено в запросе")
        return jsonify({'error': 'Изображение не предоставлено'}), 400

    file = request.files['image']
    recognition_dir = "recognition"
    os.makedirs(recognition_dir, exist_ok=True)
    image_path = os.path.join(recognition_dir, file.filename)

    try:
        file.save(image_path)
    except Exception as e:
        logger.error(f"Ошибка сохранения файла {file.filename}: {e}")
        return jsonify({'error': f"Не удалось сохранить изображение: {str(e)}"}), 500

    try:
        # Извлечение энкодингов
        encodings = extract_face_encodings(image_path)

        # Подключение к БД
        conn = get_db_connection()
        cursor = conn.cursor()

        # Извлечение энкодингов из БД
        cursor.execute("SELECT id, name, face_encoding, image_id FROM faces")
        rows = cursor.fetchall()

        results = []
        # Сравнение каждого лица
        for i, encoding in enumerate(encodings):
            face_results = {'face_number': i + 1, 'matches': []}
            for row in rows:
                db_encoding = np.array(row[2])  # FLOAT[] преобразуется в numpy массив
                match = face_recognition.compare_faces([db_encoding], encoding, tolerance=0.5)[0]
                if match:
                    face_results['matches'].append({
                        'id': row[0],
                        'name': row[1],
                        'image_id': row[3]
                    })
            results.append(face_results)

        conn.close()

        # Удаление файла после успешного распознавания
        try:
            os.remove(image_path)
            logger.info(f"Файл {image_path} удалён после распознавания")
        except Exception as e:
            logger.error(f"Ошибка удаления файла {image_path}: {e}")

        return jsonify({'results': results}), 200

    except ValueError as e:
        os.remove(image_path) if os.path.exists(image_path) else None
        return jsonify({'error': str(e)}), 400
    except psycopg2.Error as e:
        os.remove(image_path) if os.path.exists(image_path) else None
        logger.error(f"Ошибка базы данных: {e}")
        return jsonify({'error': f"Ошибка базы данных: {str(e)}"}), 500
    except Exception as e:
        os.remove(image_path) if os.path.exists(image_path) else None
        logger.error(f"Неизвестная ошибка: {e}")
        return jsonify({'error': f"Внутренняя ошибка сервера: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)