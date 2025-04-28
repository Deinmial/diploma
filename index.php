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
					<li><a href="#">Логи</a></li>
				</ul>
			</aside>

			<main class="main-content">
				<!-- Раздел Посещаемость -->
				<div id="attendance-section">
					<div class="page-header">
						<h1 class="page-title">Журнал посещаемости</h1>
						<div class="action-buttons">
							<button class="btn btn-primary" onclick="openAttendanceModal()">Отметить присутствие</button>
						</div>
					</div>

					<div class="filter-controls">
						<select id="group-filter">
							<option value="">Все группы</option>
						</select>
						<select id="subject-filter">
							<option value="">Все предметы</option>
						</select>
						<input type="date" id="date-filter">
						<button class="btn" onclick="applyFilters()">Применить</button>
					</div>

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

					<!-- Модальное окно для посещаемости -->
					<div id="attendance-modal" style="display: none;">
						<div class="modal-content">
							<h2>Отметить присутствие</h2>
							<form id="attendance-form">
								<label>Предмет:</label>
								<select id="modal-subject" required></select>
								<label>Дата:</label>
								<input type="date" id="modal-date" value="<?php echo date('Y-m-d'); ?>" required>
								<label>Изображение:</label>
								<input type="file" id="modal-image" accept="image/*" required>
								<button type="submit" class="btn btn-primary">Отправить</button>
								<button type="button" class="btn" onclick="closeAttendanceModal()">Отмена</button>
							</form>
							<div id="face-results"></div>
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
						</div>
					</div>
				</div>
			</main>
		</div>
	</div>

	<script src="assets/main.js"></script>
</body>
</html>