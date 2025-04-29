from flask import Flask, request, jsonify
from flask_cors import CORS
import face_recognition
import psycopg2
import numpy as np
import os
import logging
from logging.handlers import RotatingFileHandler
from typing import List
from PIL import Image
from datetime import datetime
import threading
import time
from main_encoding import extract_face_encodings, save_face_encodings, process_single_image, has_student_photo, delete_student_photos

# Настройка логирования с ротацией
log_file = "face_encoding.log"
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Ротация: 10 МБ на файл, до 5 резервных файлов
file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
# Вывод в консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost"}})

# Инициализация базы данных: создание таблиц, если они не существуют
def init_db():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Создание таблиц с IF NOT EXISTS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_id SERIAL PRIMARY KEY,
                group_name TEXT NOT NULL UNIQUE
            );
        """)
        logger.info("Таблица groups проверена/создана")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                subject_id SERIAL PRIMARY KEY,
                subject_name TEXT NOT NULL UNIQUE
            );
        """)
        logger.info("Таблица subjects проверена/создана")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id SERIAL PRIMARY KEY,
                full_name TEXT NOT NULL,
                group_id INTEGER REFERENCES groups(group_id)
            );
        """)
        logger.info("Таблица students проверена/создана")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                face_id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(student_id),
                face_encoding FLOAT[] NOT NULL,
                image_id TEXT NOT NULL
            );
        """)
        logger.info("Таблица faces проверена/создана")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(student_id),
                subject_id INTEGER REFERENCES subjects(subject_id),
                attendance_date DATE NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('present', 'absent')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Таблица attendance проверена/создана")

        conn.commit()
        logger.info("Инициализация базы данных завершена")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# Функция для отложенного удаления файлов
def delayed_delete(file_paths, delay_seconds):
    logger.info(f"Запуск отложенного удаления для файлов: {file_paths} с задержкой {delay_seconds} секунд")
    try:
        time.sleep(delay_seconds)
        for file_path in file_paths:
            if os.path.exists(file_path):
                logger.info(f"Попытка удаления файла: {file_path}")
                os.remove(file_path)
                logger.info(f"Файл {file_path} удалён после задержки")
            else:
                logger.warning(f"Файл {file_path} не существует при попытке удаления")
    except Exception as e:
        logger.error(f"Ошибка при отложенном удалении файлов: {e}")

# Подключение к PostgreSQL
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname="attendance",
            user="dmitry",
            password="dmitry",
            host="localhost",
            port="5432"
        )
        return conn
    except psycopg2.Error as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        raise ValueError(f"Не удалось подключиться к базе данных: {str(e)}")

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

# Маршрут для получения списка групп
@app.route('/groups', methods=['GET'])
def get_groups():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT group_id, group_name FROM groups")
        groups = [{'group_id': row[0], 'group_name': row[1]} for row in cursor.fetchall()]
        conn.close()
        return jsonify({'groups': groups}), 200
    except Exception as e:
        logger.error(f"Ошибка получения групп: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для получения списка предметов
@app.route('/subjects', methods=['GET'])
def get_subjects():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT subject_id, subject_name FROM subjects")
        subjects = [{'subject_id': row[0], 'subject_name': row[1]} for row in cursor.fetchall()]
        conn.close()
        return jsonify({'subjects': subjects}), 200
    except Exception as e:
        logger.error(f"Ошибка получения предметов: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для получения списка студентов
@app.route('/students', methods=['GET'])
def get_students():
    group_id = request.args.get('group_id')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT s.student_id, s.full_name, g.group_name, f.image_id
            FROM students s
            LEFT JOIN groups g ON s.group_id = g.group_id
            LEFT JOIN faces f ON s.student_id = f.student_id
        """
        params = []
        if group_id:
            query += " WHERE s.group_id = %s"
            params.append(group_id)
        query += " ORDER BY s.full_name ASC"
        cursor.execute(query, params)
        students = [
            {
                'student_id': row[0],
                'full_name': row[1],
                'group_name': row[2] or 'Без группы',
                'has_photo': bool(row[3]),
                'image_id': row[3]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return jsonify({'students': students}), 200
    except Exception as e:
        logger.error(f"Ошибка получения студентов: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для добавления студента
@app.route('/students', methods=['POST'])
def add_student():
    data = request.json
    full_name = data.get('full_name')
    group_id = data.get('group_id')

    if not full_name:
        return jsonify({'error': 'Имя студента обязательно'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (full_name, group_id) VALUES (%s, %s) RETURNING student_id",
            (full_name, group_id or None)
        )
        student_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return jsonify({'student_id': student_id, 'status': 'success'}), 201
    except psycopg2.Error as e:
        logger.error(f"Ошибка добавления студента: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для удаления студента
@app.route('/students/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Удаление связанных записей в attendance
        cursor.execute("DELETE FROM attendance WHERE student_id = %s", (student_id,))
        # Удаление связанных записей в faces
        delete_student_photos(student_id)
        # Удаление студента
        cursor.execute("DELETE FROM students WHERE student_id = %s", (student_id,))

        conn.commit()
        conn.close()
        return jsonify({'status': 'success'}), 200
    except psycopg2.Error as e:
        logger.error(f"Ошибка удаления студента student_id {student_id}: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return jsonify({'error': str(e)}), 500

# Маршрут для загрузки фото студента
@app.route('/upload_student_photo', methods=['POST'])
def upload_student_photo():
    if 'image' not in request.files or 'student_id' not in request.form:
        logger.error("Изображение или student_id не предоставлены")
        return jsonify({'error': 'Требуется изображение и student_id'}), 400

    file = request.files['image']
    student_id = request.form['student_id']
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_id = f"{timestamp}_{os.path.splitext(file.filename)[0]}"
    uploads_dir = "uploads"
    os.makedirs(uploads_dir, exist_ok=True)
    image_path = os.path.join(uploads_dir, f"{image_id}.png")

    try:
        file.save(image_path)
        logger.info(f"Сохранено изображение: {image_path}")

        # Проверка количества лиц
        encodings = extract_face_encodings(image_path)
        if len(encodings) == 0:
            os.remove(image_path)
            logger.warning(f"Лицо не найдено в изображении: {image_path}")
            return jsonify({'error': 'Лицо не найдено на изображении'}), 400
        if len(encodings) > 1:
            os.remove(image_path)
            logger.warning(f"Найдено более одного лица в изображении: {image_path}")
            return jsonify({'error': 'На изображении должно быть ровно одно лицо'}), 400

        # Обработка изображения
        success = process_single_image(image_path, int(student_id), image_id)
        if success:
            return jsonify({'status': 'success', 'image_id': image_id}), 200
        else:
            os.remove(image_path)
            return jsonify({'error': 'Не удалось обработать изображение'}), 400
    except Exception as e:
        logger.error(f"Ошибка обработки изображения: {e}")
        if os.path.exists(image_path):
            os.remove(image_path)
        return jsonify({'error': str(e)}), 500

# Маршрут для удаления фото студента
@app.route('/delete_student_photo/<int:student_id>', methods=['DELETE'])
def delete_student_photo(student_id):
    try:
        success = delete_student_photos(student_id)
        if success:
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'error': 'Не удалось удалить фото'}), 400
    except Exception as e:
        logger.error(f"Ошибка удаления фото для student_id {student_id}: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для получения записей посещаемости
@app.route('/attendance', methods=['GET'])
def get_attendance():
    group_id = request.args.get('group_id')
    subject_id = request.args.get('subject_id')
    date = request.args.get('date')

    query = """
        SELECT a.attendance_id, s.full_name, g.group_name, a.attendance_date, sub.subject_name, a.status
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        JOIN groups g ON s.group_id = g.group_id
        JOIN subjects sub ON a.subject_id = sub.subject_id
        WHERE 1=1
    """
    params = []

    if group_id:
        query += " AND g.group_id = %s"
        params.append(group_id)
    if subject_id:
        query += " AND sub.subject_id = %s"
        params.append(subject_id)
    if date:
        query += " AND a.attendance_date = %s"
        params.append(date)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        attendance = [
            {
                'attendance_id': row[0],
                'full_name': row[1],
                'group_name': row[2],
                'date': row[3].strftime('%Y-%m-%d'),
                'subject_name': row[4],
                'status': row[5]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return jsonify({'attendance': attendance}), 200
    except Exception as e:
        logger.error(f"Ошибка получения посещаемости: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для обновления статуса посещаемости
@app.route('/attendance/<int:attendance_id>', methods=['PUT'])
def update_attendance(attendance_id):
    data = request.json
    status = data.get('status')

    if status not in ['present', 'absent']:
        return jsonify({'error': 'Недопустимый статус'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE attendance SET status = %s WHERE attendance_id = %s",
            (status, attendance_id)
        )
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"Ошибка обновления посещаемости: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для обработки изображения посещаемости
@app.route('/process_image', methods=['POST'])
def process_image():
    if 'image' not in request.files:
        logger.error("Изображение не предоставлено в запросе")
        return jsonify({'error': 'Изображение не предоставлено'}), 400

    subject_id = request.form.get('subject_id')
    attendance_date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

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
        encodings = extract_face_encodings(image_path)
        locations = face_recognition.face_locations(face_recognition.load_image_file(image_path))

        if not encodings:
            return jsonify({'error': 'Лица не найдены на изображении'}), 400

        # Сохранение обрезанных лиц
        face_paths = save_cropped_faces(image_path, locations, f"{timestamp}_{file.filename}")

        # Подключение к БД
        conn = get_db_connection()
        cursor = conn.cursor()

        # Извлечение энкодингов из БД
        cursor.execute("SELECT f.face_id, f.face_encoding, s.student_id, s.full_name FROM faces f JOIN students s ON f.student_id = s.student_id")
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
                db_encoding = np.array(row[1])
                match = face_recognition.compare_faces([db_encoding], encoding, tolerance=0.5)[0]
                if match:
                    student_id = row[2]
                    full_name = row[3]
                    face_results['matches'].append({
                        'student_id': student_id,
                        'full_name': full_name
                    })
                    # Запись в таблицу посещаемости
                    cursor.execute(
                        """
                        INSERT INTO attendance (student_id, subject_id, attendance_date, status)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (student_id, subject_id, attendance_date, 'present')
                    )
            conn.commit()
            results.append(face_results)

        conn.close()

        # Запуск отложенного удаления (60 секунд)
        all_paths = [image_path] + face_paths
        logger.info(f"Запуск отложенного удаления для путей: {all_paths}")
        threading.Thread(target=delayed_delete, args=(all_paths, 60)).start()

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

# Маршрут для получения логов
@app.route('/logs', methods=['GET'])
def get_logs():
    log_file = "face_encoding.log"
    try:
        logs = []
        # Чтение основного файла и резервных файлов (face_encoding.log.1, .2, ..., .5)
        log_files = [log_file] + [f"{log_file}.{i}" for i in range(1, 6)]
        for file in log_files:
            if os.path.exists(file):
                with open(file, 'r', encoding='utf-8') as f:
                    logs.extend([line.strip() for line in f if line.strip()])
        if not logs:
            logger.warning("Логи не найдены")
            return jsonify({'logs': [], 'error': 'Логи не найдены'}), 200
        return jsonify({'logs': logs}), 200
    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()  # Инициализация таблиц при запуске
    app.run(host='0.0.0.0', port=5000)