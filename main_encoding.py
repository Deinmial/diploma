import face_recognition
import psycopg2
import numpy as np
import os
import logging
from typing import List
import json

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
        raise


# Функция для извлечения энкодингов лиц из изображения
def extract_face_encodings(image_path: str) -> List[np.ndarray]:
    try:
        if not os.path.exists(image_path):
            logger.error(f"Изображение не найдено: {image_path}")
            return []

        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)

        if len(encodings) == 0:
            logger.warning(f"Лица не найдены в изображении: {image_path}")
            return []

        logger.info(f"Найдено {len(encodings)} лиц в изображении: {image_path}")
        return encodings
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения {image_path}: {e}")
        return []


# Функция для проверки, существует ли image_id в БД
def check_image_id_exists(image_id: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS (SELECT 1 FROM faces WHERE image_id = %s)", (image_id,))
        exists = cursor.fetchone()[0]
        conn.close()
        return exists
    except psycopg2.Error as e:
        logger.error(f"Ошибка при проверке image_id в БД: {e}")
        return False


# Функция для проверки, есть ли фото у студента
def has_student_photo(student_id: int) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS (SELECT 1 FROM faces WHERE student_id = %s)", (student_id,))
        exists = cursor.fetchone()[0]
        conn.close()
        return exists
    except psycopg2.Error as e:
        logger.error(f"Ошибка при проверке наличия фото для student_id {student_id}: {e}")
        return False


# Функция для удаления записей и файлов для студента
def delete_student_photos(student_id: int, uploads_dir: str = "uploads") -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT image_id FROM faces WHERE student_id = %s", (student_id,))
        image_ids = [row[0] for row in cursor.fetchall()]

        # Удаление записей из БД
        cursor.execute("DELETE FROM faces WHERE student_id = %s", (student_id,))
        conn.commit()
        conn.close()

        # Удаление файлов
        for image_id in image_ids:
            image_path = os.path.join(uploads_dir, f"{image_id}.png")
            if os.path.exists(image_path):
                os.remove(image_path)
                logger.info(f"Удалён файл: {image_path}")
            else:
                logger.warning(f"Файл не найден: {image_path}")

        logger.info(f"Удалены все фото для student_id: {student_id}")
        return True
    except psycopg2.Error as e:
        logger.error(f"Ошибка при удалении записей из БД для student_id {student_id}: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        logger.error(f"Общая ошибка при удалении фото для student_id {student_id}: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


# Функция для сохранения энкодингов в БД для конкретного студента
def save_face_encodings(student_id: int, encodings: List[np.ndarray], image_path: str, image_id: str) -> bool:
    if check_image_id_exists(image_id):
        logger.info(f"Изображение с image_id {image_id} уже обработано")
        return True

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for i, encoding in enumerate(encodings):
            encoding_list = encoding.tolist()
            cursor.execute(
                """
                INSERT INTO faces (student_id, face_encoding, image_id)
                VALUES (%s, %s, %s)
                RETURNING face_id
                """,
                (student_id, encoding_list, image_id)
            )
            face_id = cursor.fetchone()[0]
            logger.info(f"Сохранено лицо face_id: {face_id}, student_id: {student_id}, image_id: {image_id}")

        conn.commit()
        conn.close()
        return True
    except psycopg2.Error as e:
        logger.error(f"Ошибка при сохранении в БД: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        logger.error(f"Общая ошибка: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


# Функция для обработки одного изображения
def process_single_image(image_path: str, student_id: int, image_id: str) -> bool:
    encodings = extract_face_encodings(image_path)
    if not encodings:
        logger.warning(f"Не удалось извлечь энкодинги из {image_path}")
        return False

    success = save_face_encodings(student_id, encodings, image_path, image_id)
    if success:
        logger.info(f"Успешно обработано изображение: {image_path} для student_id: {student_id}")
    else:
        logger.warning(f"Не удалось сохранить энкодинги для: {image_path}")
    return success


# Функция для отслеживания обработанных файлов
def load_processed_files(tracking_file: str = "processed_files.json") -> set:
    if os.path.exists(tracking_file):
        try:
            with open(tracking_file, 'r') as f:
                return set(json.load(f))
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка чтения {tracking_file}: {e}, создаём новый файл")
            return set()
    return set()


def save_processed_file(filename: str, tracking_file: str = "processed_files.json") -> None:
    processed = load_processed_files(tracking_file)
    processed.add(filename)
    try:
        with open(tracking_file, 'w') as f:
            json.dump(list(processed), f)
    except Exception as e:
        logger.error(f"Ошибка записи в {tracking_file}: {e}")


# Функция для удаления записей из БД, если файл отсутствует
def delete_missing_images(directory: str = "uploads", tracking_file: str = "processed_files.json") -> None:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Получить все image_id из БД
        cursor.execute("SELECT DISTINCT image_id FROM faces")
        db_image_ids = {row[0] for row in cursor.fetchall()}

        # Получить все файлы в директории
        existing_files = {os.path.splitext(f)[0] for f in os.listdir(directory)
                          if f.lower().endswith(('.jpg', '.jpeg', '.png'))}

        # Найти image_id, которых нет в директории
        missing_ids = db_image_ids - existing_files

        # Удалить записи для отсутствующих файлов
        for image_id in missing_ids:
            cursor.execute("DELETE FROM faces WHERE image_id = %s", (image_id,))
            logger.info(f"Удалены записи для image_id: {image_id}")

        conn.commit()
        conn.close()

        # Обновить processed_files.json, удалив отсутствующие файлы
        processed_files = load_processed_files(tracking_file)
        processed_files = {f for f in processed_files if os.path.splitext(f)[0] in existing_files}
        try:
            with open(tracking_file, 'w') as f:
                json.dump(list(processed_files), f)
            logger.info("Файл processed_files.json обновлён")
        except Exception as e:
            logger.error(f"Ошибка обновления {tracking_file}: {e}")
    except psycopg2.Error as e:
        logger.error(f"Ошибка при удалении записей из БД: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        logger.error(f"Общая ошибка при удалении: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()


# Функция для обработки изображений в директории
def process_directory(
        directory: str = "uploads",
        tracking_file: str = "processed_files.json"
) -> None:
    if not os.path.isdir(directory):
        logger.error(f"Директория не найдена: {directory}")
        return

    # Удаление записей для отсутствующих файлов
    delete_missing_images(directory, tracking_file)

    # Загрузка списка уже обработанных файлов
    processed_files = load_processed_files(tracking_file)

    for filename in os.listdir(directory):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')) and filename not in processed_files:
            image_path = os.path.join(directory, filename)
            image_id = os.path.splitext(filename)[0]

            # Пропускаем, так как для обработки директории нужен student_id
            logger.warning(f"Пропущено изображение {image_path}: требуется student_id для обработки")
            continue


if __name__ == '__main__':
    # Создание таблиц (если ещё не созданы)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id SERIAL PRIMARY KEY,
                full_name TEXT NOT NULL,
                group_id INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                face_id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(student_id),
                face_encoding FLOAT[] NOT NULL,
                image_id TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Таблицы students и faces созданы или уже существуют")
    except psycopg2.Error as e:
        logger.error(f"Ошибка при создании таблиц: {e}")

    # Обработка всех изображений в директории uploads/
    process_directory(
        directory="uploads",
        tracking_file="processed_files.json"
    )