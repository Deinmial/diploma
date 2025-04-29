<?php
    $teacher_name = "Иванов Иван Иванович";
?>

<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Система учета посещаемости</title>
    <link rel="stylesheet" href="assets/main.css">
</head>
<body>
    <header>
        <div class="container header-content">
            <div class="logo">Посещаемость студентов</div>
            <div class="user-info">
                <span>Преподаватель: <?php echo htmlspecialchars($teacher_name); ?></span>
                <div class="user-avatar"><?php echo substr($teacher_name, 0, 2); ?></div>
            </div>
        </div>
    </header>

    <div class="container">
        <div class="dashboard">
            <aside class="sidebar">
                <ul class="sidebar-nav">
                    <li><a href="#" class="active" onclick="showSection('attendance')">Посещаемость</a></li>
                    <li><a href="#" onclick="showSection('students')">Студенты</a></li>
                    <li><a href="#" onclick="showSection('logs')">Логи</a></li>
                </ul>
            </aside>

            <main class="main-content">
                <!-- Раздел Посещаемость -->
                <div id="attendance-section">
                    <div class="page-header">
                        <h1 class="page-title">Журнал посещаемости</h1>
                        <div class="action-buttons">
                            <button id="upload-photo-btn" class="btn btn-primary" onclick="openAttendanceModal()" disabled>Загрузить фото студентов</button>
                            <button id="confirm-attendance-btn" class="btn btn-primary" onclick="confirmAttendance()" disabled>Подтвердить посещаемость</button>
                        </div>
                    </div>

                    <div class="filter-controls">
                        <select id="group-filter" required>
                            <option value="">Выберите группу</option>
                        </select>
                        <select id="subject-filter" required>
                            <option value="">Выберите предмет</option>
                        </select>
                        <input type="date" id="date-filter" value="<?php echo date('Y-m-d'); ?>" required>
                        <button class="btn btn-primary" onclick="applyFilters()">Применить фильтр</button>
                    </div>

                    <div class="loader" id="attendance-loader" style="display: none;"></div>
                    <table class="attendance-table">
                        <thead>
                            <tr>
                                <th>№</th>
                                <th>Студент</th>
                                <th>Группа</th>
                                <th>Дата</th>
                                <th>Предмет</th>
                                <th>Статус</th>
                            </tr>
                        </thead>
                        <tbody id="attendance-table-body"></tbody>
                    </table>

                    <!-- Модальное окно для загрузки фото -->
                    <div id="attendance-modal" style="display: none;">
                        <div class="modal-content">
                            <h2>Загрузить фото студентов</h2>
                            <form id="attendance-form">
                                <label>Группа:</label>
                                <input type="text" id="modal-group" readonly>
                                <label>Предмет:</label>
                                <input type="text" id="modal-subject" readonly>
                                <label>Дата:</label>
                                <input type="text" id="modal-date" readonly>
                                <label>Изображение:</label>
                                <input type="file" id="modal-image" accept="image/*" required>
                                <button type="submit" class="btn btn-primary">Загрузить</button>
                                <button type="button" class="btn" onclick="closeAttendanceModal()">Отмена</button>
                            </form>
                            <div class="loader" id="modal-loader" style="display: none;"></div>
                            <div id="face-results" class="face-results"></div>
                            <button id="confirm-modal-attendance" class="btn btn-primary" style="display: none;">Подтвердить</button>
                        </div>
                    </div>
                </div>

                <!-- Раздел Студенты -->
                <div id="students-section" style="display: none;">
                    <div class="page-header">
                        <h1 class="page-title">Управление студентами</h1>
                        <div class="action-buttons">
                            <button class="btn btn-primary" onclick="openAddStudentModal()">Добавить студента</button>
                        </div>
                    </div>
                    <div class="filter-controls">
                        <select id="student-group-filter">
                            <option value="">Все группы</option>
                        </select>
                        <button class="btn btn-primary" onclick="applyStudentFilters()">Применить фильтр</button>
                    </div>
                    <div class="loader" id="students-loader" style="display: none;"></div>
                    <table class="students-table">
                        <thead>
                            <tr>
                                <th>№</th>
                                <th>ФИО</th>
                                <th>Группа</th>
                                <th>Фото</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody id="students-table-body"></tbody>
                    </table>

                    <!-- Модальное окно для добавления студента -->
                    <div id="add-student-modal" style="display: none;">
                        <div class="modal-content">
                            <h2>Добавить студента</h2>
                            <form id="add-student-form">
                                <label>ФИО:</label>
                                <input type="text" id="student-name" required>
                                <label>Группа:</label>
                                <select id="student-group">
                                    <option value="">Без группы</option>
                                </select>
                                <button type="submit" class="btn btn-primary">Сохранить</button>
                                <button type="button" class="btn" onclick="closeAddStudentModal()">Отмена</button>
                            </form>
                            <div class="loader" id="add-student-loader" style="display: none;"></div>
                        </div>
                    </div>

                    <!-- Модальное окно для загрузки фото -->
                    <div id="upload-photo-modal" style="display: none;">
                        <div class="modal-content">
                            <h2>Загрузить фото студента</h2>
                            <form id="upload-photo-form">
                                <input type="hidden" id="photo-student-id">
                                <label>Фотография:</label>
                                <input type="file" id="student-photo" accept="image/*" required>
                                <button type="submit" class="btn btn-primary">Загрузить</button>
                                <button type="button" class="btn" onclick="closeUploadPhotoModal()">Отмена</button>
                            </form>
                            <div class="loader" id="upload-photo-loader" style="display: none;"></div>
                        </div>
                    </div>
                </div>

                <!-- Раздел Логи -->
                <div id="logs-section" style="display: none;">
                    <div class="page-header">
                        <h1 class="page-title">Логи системы</h1>
                    </div>
                    <div class="loader" id="logs-loader" style="display: none;"></div>
                    <table class="logs-table">
                        <thead>
                            <tr>
                                <th>№</th>
                                <th>Время</th>
                                <th>Уровень</th>
                                <th>Сообщение</th>
                            </tr>
                        </thead>
                        <tbody id="logs-table-body"></tbody>
                    </table>
                </div>
            </main>
        </div>
    </div>

    <script src="assets/main.js"></script>
</body>
</html>
