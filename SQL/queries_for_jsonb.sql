-- Скрипт для изменения столбца face_encoding на JSONB и создания GIN-индекса

-- 1. Изменение типа столбца face_encoding на JSONB
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_name = 'faces' AND column_name = 'face_encoding'
        AND data_type = 'ARRAY'
    ) THEN
        -- Преобразование FLOAT[] в JSONB
        ALTER TABLE faces
        ALTER COLUMN face_encoding TYPE JSONB
        USING (array_to_json(face_encoding)::JSONB);
    ELSE
        RAISE NOTICE 'Столбец face_encoding уже имеет тип JSONB или не существует';
    END IF;
END $$;

-- 2. Проверка существования индекса и его создание
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_indexes
        WHERE schemaname = 'public'
        AND tablename = 'faces'
        AND indexname = 'faces_encoding_gin'
    ) THEN
        -- Создание GIN-индекса на столбце face_encoding
        CREATE INDEX faces_encoding_gin
        ON faces
        USING GIN (face_encoding);

        -- Добавление комментария к индексу
        COMMENT ON INDEX faces_encoding_gin
        IS 'GIN-индекс для ускорения поиска по эмбеддингам лиц в столбце face_encoding (JSONB)';
    ELSE
        RAISE NOTICE 'Индекс faces_encoding_gin уже существует';
    END IF;
END $$;

-- 3. Проверка структуры таблицы и индексов
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'faces' AND column_name = 'face_encoding';

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'faces';
