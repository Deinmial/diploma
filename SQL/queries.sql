-- Таблица групп
CREATE TABLE groups (
    group_id SERIAL PRIMARY KEY,
    group_name TEXT NOT NULL UNIQUE
);

-- Таблица предметов
CREATE TABLE subjects (
    subject_id SERIAL PRIMARY KEY,
    subject_name TEXT NOT NULL UNIQUE
);

-- Таблица студентов
CREATE TABLE students (
    student_id SERIAL PRIMARY KEY,
    full_name TEXT NOT NULL,
    group_id INTEGER REFERENCES groups(group_id)
);

-- Таблица лиц (связана со студентами)
CREATE TABLE faces (
    face_id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(student_id),
    face_encoding FLOAT[] NOT NULL,
    image_id TEXT NOT NULL
);

-- Таблица посещаемости
CREATE TABLE attendance (
    attendance_id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(student_id),
    subject_id INTEGER REFERENCES subjects(subject_id),
    attendance_date DATE NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('present', 'absent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);