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
import uuid

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

# Инициализация базы данных
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
                group_id INTEGER REFERENCES groups(group_id),
                attendance_date DATE NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('present', 'absent')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, subject_id, group_id, attendance_date)
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
            face_id = str(uuid.uuid4())
            face_path = os.path.join(faces_dir, f"{face_id}.png")
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

    if not all([group_id, subject_id, date]):
        logger.error("Отсутствуют обязательные параметры: group_id, subject_id, date")
        return jsonify({'error': 'Отсутствуют обязательные параметры'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT a.attendance_id, s.student_id, s.full_name, g.group_name, a.attendance_date, 
                   sub.subject_name, a.status
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id 
                AND a.subject_id = %s AND a.attendance_date = %s AND a.group_id = %s
            LEFT JOIN groups g ON s.group_id = g.group_id
            CROSS JOIN (SELECT subject_name FROM subjects WHERE subject_id = %s) sub
            WHERE s.group_id = %s
            ORDER BY s.full_name
        """
        params = [subject_id, date, group_id, subject_id, group_id]
        cursor.execute(query, params)
        attendance = [
            {
                'attendance_id': row[0],
                'student_id': row[1],
                'full_name': row[2],
                'group_name': row[3],
                'date': row[4].strftime('%Y-%m-%d') if row[4] else date,
                'subject_name': row[5],
                'status': row[6] or 'absent'
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return jsonify({'attendance': attendance}), 200
    except Exception as e:
        logger.error(f"Ошибка получения посещаемости: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для создания или обновления статуса посещаемости
@app.route('/attendance', methods=['POST'])
def update_or_create_attendance():
    data = request.json
    student_id = data.get('student_id')
    subject_id = data.get('subject_id')
    group_id = data.get('group_id')
    attendance_date = data.get('attendance_date')
    status = data.get('status')

    if not all([student_id, subject_id, group_id, attendance_date, status]):
        logger.error("Отсутствуют обязательные параметры для update_or_create_attendance")
        return jsonify({'error': 'Отсутствуют обязательные параметры'}), 400

    if status not in ['present', 'absent']:
        return jsonify({'error': 'Недопустимый статус'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO attendance (student_id, subject_id, group_id, attendance_date, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (student_id, subject_id, group_id, attendance_date)
            DO UPDATE SET status = EXCLUDED.status
            RETURNING attendance_id
        """, (student_id, subject_id, group_id, attendance_date, status))
        attendance_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        logger.info(f"Обновлена/создана посещаемость: student_id={student_id}, date={attendance_date}, status={status}, attendance_id={attendance_id}")
        return jsonify({'status': 'success', 'attendance_id': attendance_id}), 200
    except Exception as e:
        logger.error(f"Ошибка обновления/создания посещаемости: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для обработки изображения посещаемости
@app.route('/process_image', methods=['POST'])
def process_image():
    if 'image' not in request.files or 'subject_id' not in request.form or 'date' not in request.form or 'group_id' not in request.form:
        logger.error("Отсутствуют обязательные параметры: image, subject_id, date, group_id")
        return jsonify({'error': 'Отсутствуют обязательные параметры'}), 400

    subject_id = request.form['subject_id']
    attendance_date = request.form['date']
    group_id = request.form['group_id']
    file = request.files['image']
    recognition_dir = "recognition"
    os.makedirs(recognition_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = os.path.join(recognition_dir, f"{timestamp}_{file.filename}")

    try:
        file.save(image_path)
        logger.info(f"Сохранено изображение: {image_path}")
        encodings = extract_face_encodings(image_path)
        locations = face_recognition.face_locations(face_recognition.load_image_file(image_path))

        if not encodings:
            logger.warning(f"Лица не найдены в изображении: {image_path}")
            os.remove(image_path)
            return jsonify({'error': 'Лица не найдены на изображении'}), 400

        # Сохранение обрезанных лиц
        face_paths = save_cropped_faces(image_path, locations, f"{timestamp}_{file.filename}")

        # Подключение к БД
        conn = get_db_connection()
        cursor = conn.cursor()

        # Извлечение энкодингов из БД
        cursor.execute("""
            SELECT f.face_id, f.face_encoding, s.student_id, s.full_name, s.group_id
            FROM faces f
            JOIN students s ON f.student_id = s.student_id
        """)
        rows = cursor.fetchall()

        results = []
        # Сравнение каждого лица
        for i, encoding in enumerate(encodings):
            face_id = os.path.splitext(os.path.basename(face_paths[i]))[0] if i < len(face_paths) else str(uuid.uuid4())
            face_result = {
                'face_id': face_id,
                'face_image_path': face_paths[i] if i < len(face_paths) else None,
                'status': 'unknown',
                'matches': []
            }
            for row in rows:
                db_encoding = np.array(row[1])
                match = face_recognition.compare_faces([db_encoding], encoding, tolerance=0.5)[0]
                if match:
                    student_group_id = row[4]
                    distance = float(face_recognition.face_distance([db_encoding], encoding)[0])
                    face_result['matches'].append({
                        'student_id': row[2],
                        'full_name': row[3],
                        'distance': distance
                    })
                    if str(student_group_id) == group_id:
                        face_result['status'] = 'present'
                    else:
                        face_result['status'] = 'other_group'
            results.append(face_result)

        conn.close()

        # Запуск отложенного удаления (60 секунд)
        all_paths = [image_path] + face_paths
        logger.info(f"Запуск отложенного удаления для путей: {all_paths}")
        threading.Thread(target=delayed_delete, args=(all_paths, 60)).start()

        return jsonify({'results': results}), 200
    except Exception as e:
        logger.error(f"Ошибка обработки изображения: {e}")
        if os.path.exists(image_path):
            os.remove(image_path)
        return jsonify({'error': str(e)}), 500

# Маршрут для отметки посещаемости одного студента
@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.get_json()
    student_id = data.get('student_id')
    subject_id = data.get('subject_id')
    attendance_date = data.get('attendance_date')
    group_id = data.get('group_id')
    status = data.get('status', 'present')

    if not all([student_id, subject_id, attendance_date, group_id]):
        logger.error("Отсутствуют обязательные параметры для mark_attendance")
        return jsonify({'error': 'Отсутствуют обязательные параметры'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO attendance (student_id, subject_id, group_id, attendance_date, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (student_id, subject_id, group_id, attendance_date)
            DO UPDATE SET status = EXCLUDED.status
            RETURNING attendance_id
        """, (student_id, subject_id, group_id, attendance_date, status))
        attendance_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        logger.info(f"Отмечена посещаемость: student_id={student_id}, date={attendance_date}, status={status}")
        return jsonify({'status': 'success', 'attendance_id': attendance_id}), 200
    except Exception as e:
        logger.error(f"Ошибка при отметке посещаемости: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для массовой отметки посещаемости
@app.route('/bulk_mark_attendance', methods=['POST'])
def bulk_mark_attendance():
    data = request.get_json()
    records = data.get('records', [])
    if not records:
        logger.error("Отсутствуют записи для массовой отметки")
        return jsonify({'error': 'Отсутствуют записи'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for record in records:
            cursor.execute("""
                INSERT INTO attendance (student_id, subject_id, group_id, attendance_date, status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (student_id, subject_id, group_id, attendance_date)
                DO UPDATE SET status = EXCLUDED.status
            """, (
                record['student_id'],
                record['subject_id'],
                record['group_id'],
                record['attendance_date'],
                record['status']
            ))
        conn.commit()
        conn.close()
        logger.info(f"Массово отмечено {len(records)} записей посещаемости")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"Ошибка при массовой отметке посещаемости: {e}")
        return jsonify({'error': str(e)}), 500

# Маршрут для получения логов
@app.route('/logs', methods=['GET'])
def get_logs():
    log_file = "/home/dmitry/PycharmProjects/diploma/face_encoding.log"
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