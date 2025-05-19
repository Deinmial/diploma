import face_recognition
import psycopg2
import numpy as np
import os
import logging
from typing import List
from psycopg2.extras import Json
from datetime import datetime

# Настройка логирования
logger = logging.getLogger(__name__)


# Подключение к базе данных
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname="attendance",
            user="dmitry",
            password="dmitry",
            host="localhost",
            port="5432"
        )
        psycopg2.extras.register_default_jsonb(conn, globally=False, loads=lambda x: x)
        return conn
    except psycopg2.Error as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        raise ValueError(f"Не удалось подключиться к базе данных: {str(e)}")


# Извлечение эмбеддингов лиц
def extract_face_encodings(image_path: str) -> List[np.ndarray]:
    try:
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        logger.info(f"Найдено {len(encodings)} лиц в изображении: {image_path}")
        return encodings
    except Exception as e:
        logger.error(f"Ошибка извлечения эмбеддингов из {image_path}: {e}")
        return []


# Сохранение эмбеддингов лиц
def save_face_encodings(student_id: int, encoding: np.ndarray, image_id: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO faces (student_id, face_encoding, image_id) VALUES (%s, %s, %s)",
            (student_id, Json(encoding.tolist()), image_id)
        )
        conn.commit()
        logger.info(f"Сохранён эмбеддинг для student_id={student_id}, image_id={image_id}")
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения эмбеддинга для student_id={student_id}: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


# Проверка существования image_id
def check_image_id_exists(image_id: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS (SELECT 1 FROM faces WHERE image_id = %s)", (image_id,))
        exists = cursor.fetchone()[0]
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Ошибка проверки image_id {image_id}: {e}")
        return False


# Обработка одного изображения
def process_single_image(image_path: str, student_id: int, image_id: str) -> bool:
    if check_image_id_exists(image_id):
        logger.warning(f"image_id {image_id} уже существует")
        return False

    encodings = extract_face_encodings(image_path)
    if len(encodings) != 1:
        logger.warning(f"Ожидалось ровно одно лицо в {image_path}, найдено {len(encodings)}")
        return False

    return save_face_encodings(student_id, encodings[0], image_id)


# Проверка наличия фото студента
def has_student_photo(student_id: int) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS (SELECT 1 FROM faces WHERE student_id = %s)", (student_id,))
        exists = cursor.fetchone()[0]
        conn.close()
        return exists
    except Exception as e:
        logger.error(f"Ошибка проверки фото для student_id={student_id}: {e}")
        return False


# Удаление фото студента
def delete_student_photos(student_id: int) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Получение image_id для удаления файлов
        cursor.execute("SELECT image_id FROM faces WHERE student_id = %s", (student_id,))
        image_ids = [row[0] for row in cursor.fetchall()]

        # Удаление записей из faces
        cursor.execute("DELETE FROM faces WHERE student_id = %s", (student_id,))

        # Удаление файлов из Uploads
        uploads_dir = "uploads"
        for image_id in image_ids:
            image_path = os.path.join(uploads_dir, f"{image_id}.png")
            if os.path.exists(image_path):
                os.remove(image_path)
                logger.info(f"Удалён файл студента: {image_path}")
            else:
                logger.warning(f"Файл не найден: {image_path}")

        conn.commit()
        conn.close()
        logger.info(f"Удалены фото для student_id={student_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления фото для student_id={student_id}: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


# Удаление отсутствующих изображений
def delete_missing_images():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT image_id FROM faces")
        image_ids = [row[0] for row in cursor.fetchall()]
        deleted_count = 0
        uploads_dir = "uploads"
        for image_id in image_ids:
            image_path = os.path.join(uploads_dir, f"{image_id}.png")
            if not os.path.exists(image_path):
                cursor.execute("DELETE FROM faces WHERE image_id = %s", (image_id,))
                deleted_count += 1
                logger.info(f"Удалена запись faces для отсутствующего image_id={image_id}")
        conn.commit()
        conn.close()
        logger.info(f"Удалено {deleted_count} записей для отсутствующих изображений")
    except Exception as e:
        logger.error(f"Ошибка удаления отсутствующих изображений: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


# Обработка директории
def process_directory(directory: str, student_id: int = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        processed_count = 0
        uploads_dir = "uploads"
        os.makedirs(uploads_dir, exist_ok=True)

        for filename in os.listdir(directory):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_path = os.path.join(directory, filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_id = f"{timestamp}_{os.path.splitext(filename)[0]}"
                new_image_path = os.path.join(uploads_dir, f"{image_id}.png")

                # Копирование файла в Uploads
                from shutil import copyfile
                copyfile(image_path, new_image_path)
                logger.info(f"Скопировано изображение: {new_image_path}")

                if student_id and process_single_image(new_image_path, student_id, image_id):
                    processed_count += 1
                    logger.info(f"Обработано изображение: {new_image_path}")
                elif not student_id:
                    logger.warning(f"Пропущено изображение {new_image_path}: не указан student_id")

        conn.commit()
        conn.close()
        logger.info(f"Обработано {processed_count} изображений в директории {directory}")
    except Exception as e:
        logger.error(f"Ошибка обработки директории {directory}: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()