function showSection(section) {
    document.getElementById('attendance-section').style.display = section === 'attendance' ? 'block' : 'none';
    document.getElementById('students-section').style.display = section === 'students' ? 'block' : 'none';
    document.getElementById('logs-section').style.display = section === 'logs' ? 'block' : 'none';
    document.querySelectorAll('.sidebar-nav a').forEach(a => a.classList.remove('active'));
    document.querySelector(`.sidebar-nav a[onclick="showSection('${section}')"]`).classList.add('active');
    if (section === 'attendance') {
        loadFilters();
        loadAttendance();
    } else if (section === 'students') {
        loadStudentsFilters();
        loadStudents();
    } else if (section === 'logs') {
        loadLogs();
    }
    localStorage.setItem('activeSection', section);
}

// Показать спиннер
function showLoader(loaderId) {
    const loader = document.getElementById(loaderId);
    if (loader) loader.style.display = 'block';
}

// Скрыть спиннер
function hideLoader(loaderId) {
    const loader = document.getElementById(loaderId);
    if (loader) loader.style.display = 'none';
}

// Сохранение фильтров в localStorage
function saveFilters() {
    const groupFilter = document.getElementById('group-filter').value;
    const subjectFilter = document.getElementById('subject-filter').value;
    const dateFilter = document.getElementById('date-filter').value;
    const studentGroupFilter = document.getElementById('student-group-filter').value;

    localStorage.setItem('group-filter', groupFilter);
    localStorage.setItem('subject-filter', subjectFilter);
    localStorage.setItem('date-filter', dateFilter);
    localStorage.setItem('student-group-filter', studentGroupFilter);
}

// Загрузка фильтров для посещаемости
function loadFilters() {
    const dateFilter = document.getElementById('date-filter');
    if (!dateFilter.value) {
        const today = new Date().toISOString().split('T')[0];
        dateFilter.value = today;
        localStorage.setItem('date-filter', today);
    }

    // Восстановить сохранённые фильтры
    const savedGroup = localStorage.getItem('group-filter') || '';
    const savedSubject = localStorage.getItem('subject-filter') || '';
    const savedDate = localStorage.getItem('date-filter') || dateFilter.value;

    dateFilter.value = savedDate;

    Promise.all([
        fetch('http://localhost:5000/groups').then(response => response.json()),
                fetch('http://localhost:5000/subjects').then(response => response.json())
    ])
    .then(([groupData, subjectData]) => {
        const groupSelect = document.getElementById('group-filter');
        groupSelect.innerHTML = '<option value="">Выберите группу</option>';
        groupData.groups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.group_id;
            option.textContent = group.group_name;
            if (group.group_id == savedGroup) option.selected = true;
            groupSelect.appendChild(option);
        });

        const subjectSelect = document.getElementById('subject-filter');
        subjectSelect.innerHTML = '<option value="">Выберите предмет</option>';
        subjectData.subjects.forEach(subject => {
            const option = document.createElement('option');
            option.value = subject.subject_id;
            option.textContent = subject.subject_name;
            if (subject.subject_id == savedSubject) option.selected = true;
            subjectSelect.appendChild(option);
        });

        // Автоматически применить фильтры, если они все заполнены
        if (savedGroup && savedSubject && savedDate) {
            loadAttendance();
        }
    })
    .catch(error => console.error('Error loading filters:', error));
}

// Загрузка фильтров для студентов
function loadStudentsFilters() {
    const savedStudentGroup = localStorage.getItem('student-group-filter') || '';

    fetch('http://localhost:5000/groups')
    .then(response => {
        if (!response.ok) throw new Error('Failed to load groups');
        return response.json();
    })
    .then(data => {
        const groupSelect = document.getElementById('student-group-filter');
        groupSelect.innerHTML = '<option value="">Все группы</option>';
        data.groups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.group_id;
            option.textContent = group.group_name;
            if (group.group_id == savedStudentGroup) option.selected = true;
            groupSelect.appendChild(option);
        });

        // Автоматически применить фильтр, если он заполнен
        if (savedStudentGroup) {
            loadStudents();
        }
    })
    .catch(error => console.error('Error loading groups for student filters:', error));
}

// Загрузка групп для модального окна добавления студента
function loadGroupsForStudentModal() {
    fetch('http://localhost:5000/groups')
    .then(response => {
        if (!response.ok) throw new Error('Failed to load groups');
        return response.json();
    })
    .then(data => {
        const groupSelect = document.getElementById('student-group');
        groupSelect.innerHTML = '<option value="">Без группы</option>';
        data.groups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.group_id;
            option.textContent = group.group_name;
            groupSelect.appendChild(option);
        });
    })
    .catch(error => console.error('Error loading groups for student modal:', error));
}

// Загрузка таблицы посещаемости
function loadAttendance() {
    const groupId = document.getElementById('group-filter').value;
    const subjectId = document.getElementById('subject-filter').value;
    const date = document.getElementById('date-filter').value;

    const uploadBtn = document.getElementById('upload-photo-btn');
    const confirmBtn = document.getElementById('confirm-attendance-btn');

    if (!groupId || !subjectId || !date) {
        document.getElementById('attendance-table-body').innerHTML = '<tr><td colspan="6">Выберите группу, предмет и дату</td></tr>';
        uploadBtn.disabled = true;
        confirmBtn.disabled = true;
        hideLoader('attendance-loader');
        return;
    }

    showLoader('attendance-loader');
    let url = `http://localhost:5000/attendance?group_id=${groupId}&subject_id=${subjectId}&date=${date}`;

    fetch(url)
    .then(response => {
        if (!response.ok) throw new Error('Failed to load attendance');
        return response.json();
    })
    .then(data => {
        const tbody = document.getElementById('attendance-table-body');
        tbody.innerHTML = '';
        if (data.error) {
            tbody.innerHTML = `<tr><td colspan="6">${data.error}</td></tr>`;
            uploadBtn.disabled = true;
            confirmBtn.disabled = true;
            return;
        }
        data.attendance.forEach((record, index) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
            <td>${index + 1}</td>
            <td>${record.full_name}</td>
            <td>${record.group_name}</td>
            <td>${record.date}</td>
            <td>${record.subject_name}</td>
            <td>
            <div class="status-switch">
            <button class="status-switch-btn status-present ${record.status === 'present' ? 'active' : ''}"
            onclick="updateStatus(${record.student_id}, '${record.status}', ${record.attendance_id || 'null'}, '${record.date}', ${subjectId}, ${groupId}, 'present')">
            Присутствует
            </button>
            <button class="status-switch-btn status-absent ${record.status === 'absent' ? 'active' : ''}"
            onclick="updateStatus(${record.student_id}, '${record.status}', ${record.attendance_id || 'null'}, '${record.date}', ${subjectId}, ${groupId}, 'absent')">
            Отсутствует
            </button>
            </div>
            </td>
            `;
            tbody.appendChild(tr);
        });
        uploadBtn.disabled = false;
        confirmBtn.disabled = false;
    })
    .catch(error => {
        console.error('Error loading attendance:', error);
        document.getElementById('attendance-table-body').innerHTML = '<tr><td colspan="6">Ошибка загрузки данных</td></tr>';
        uploadBtn.disabled = true;
        confirmBtn.disabled = true;
    })
    .finally(() => hideLoader('attendance-loader'));
}

// Загрузка таблицы студентов
function loadStudents() {
    const groupId = document.getElementById('student-group-filter').value;
    let url = 'http://localhost:5000/students';
    if (groupId) url += `?group_id=${groupId}`;

    showLoader('students-loader');
    fetch(url)
    .then(response => response.json())
    .then(data => {
        const tbody = document.getElementById('students-table-body');
        tbody.innerHTML = '';
        data.students.forEach((student, index) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
            <td>${index + 1}</td>
            <td>${student.full_name}</td>
            <td>${student.group_name}</td>
            <td>${student.has_photo ? `<img src="/uploads/${student.image_id}.png" class="student-photo" alt="Фото студента">` : 'Нет фото'}</td>
            <td>
            ${student.has_photo ? `<button class="btn btn-danger" onclick="deleteStudentPhoto(${student.student_id})">Удалить фото</button>` : `<button class="btn btn-primary" onclick="openUploadPhotoModal(${student.student_id})">Загрузить фото</button>`}
            <button class="btn btn-danger" onclick="deleteStudent(${student.student_id}, '${student.full_name.replace(/'/g, "\\'")}')">Удалить студента</button>
            </td>
            `;
            tbody.appendChild(tr);
        });
    })
    .catch(error => {
        console.error('Error loading students:', error);
        document.getElementById('students-table-body').innerHTML = '<tr><td colspan="5">Ошибка загрузки данных</td></tr>';
    })
    .finally(() => hideLoader('students-loader'));
}

// Загрузка логов
function loadLogs() {
    showLoader('logs-loader');
    fetch('http://localhost:5000/logs')
    .then(response => {
        if (!response.ok) throw new Error('Failed to load logs');
        return response.json();
    })
    .then(data => {
        const tbody = document.getElementById('logs-table-body');
        tbody.innerHTML = '';
        if (data.error) {
            tbody.innerHTML = `<tr><td colspan="4">${data.error}</td></tr>`;
            return;
        }

        const parsedLogs = data.logs.map(log => {
            const parts = log.match(/^(\S+ \S+,\d{3}) - (\w+) - (.+)$/);
            if (!parts) {
                return {
                    timestamp: '',
                    level: 'UNKNOWN',
                    message: log,
                    raw: log
                };
            }
            return {
                timestamp: parts[1].replace(',', '.'),
                                         level: parts[2],
                                         message: parts[3],
                                         raw: log
            };
        });

        parsedLogs.sort((a, b) => {
            const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
            const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
            if (timeA !== timeB) {
                return timeB - timeA;
            }
            const levelPriority = { 'ERROR': 3, 'WARNING': 2, 'INFO': 1, 'UNKNOWN': 0 };
            return (levelPriority[b.level] || 0) - (levelPriority[a.level] || 0);
        });

        parsedLogs.forEach((log, index) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
            <td>${index + 1}</td>
            <td>${log.timestamp.replace('.', ',') || 'Неизвестно'}</td>
            <td class="log-level-${log.level.toLowerCase()}">${log.level}</td>
            <td>${log.message}</td>
            `;
            tbody.appendChild(tr);
        });
    })
    .catch(error => {
        console.error('Error loading logs:', error);
        document.getElementById('logs-table-body').innerHTML = '<tr><td colspan="4">Ошибка загрузки данных</td></tr>';
    })
    .finally(() => hideLoader('logs-loader'));
}

// Применение фильтров посещаемости
function applyFilters() {
    saveFilters();
    loadAttendance();
}

// Применение фильтров студентов
function applyStudentFilters() {
    saveFilters();
    loadStudents();
}

// Обновление статуса посещаемости
function updateStatus(studentId, currentStatus, attendanceId, date, subjectId, groupId, newStatus) {
    if (currentStatus === newStatus) {
        return;
    }

    const payload = {
        student_id: studentId,
        subject_id: parseInt(subjectId),
        group_id: parseInt(groupId),
        attendance_date: date,
        status: newStatus
    };

    fetch('http://localhost:5000/attendance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            loadAttendance();
        } else {
            alert('Ошибка: ' + data.error);
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
    });
}

// Подтверждение всей посещаемости
function confirmAttendance() {
    const groupId = document.getElementById('group-filter').value;
    const subjectId = document.getElementById('subject-filter').value;
    const date = document.getElementById('date-filter').value;

    if (!groupId || !subjectId || !date) {
        alert('Выберите группу, предмет и дату');
        return;
    }

    showLoader('attendance-loader');
    fetch(`http://localhost:5000/attendance?group_id=${groupId}&subject_id=${subjectId}&date=${date}`)
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert('Ошибка: ' + data.error);
            return;
        }
        const attendanceRecords = data.attendance.map(record => ({
            student_id: record.student_id,
            subject_id: parseInt(subjectId),
                                                                 attendance_date: date,
                                                                 status: record.status,
                                                                 group_id: parseInt(groupId)
        }));

        fetch('http://localhost:5000/bulk_mark_attendance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ records: attendanceRecords })
        })
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success') {
                alert('Посещаемость успешно подтверждена');
                loadAttendance();
            } else {
                alert('Ошибка: ' + result.error);
            }
        })
        .catch(error => {
            alert('Ошибка: ' + error.message);
        });
    })
    .finally(() => hideLoader('attendance-loader'));
}

// Удаление студента
function deleteStudent(studentId, fullName) {
    if (!confirm(`Вы уверены, что хотите удалить студента ${fullName}? Это действие нельзя отменить.`)) {
        return;
    }
    showLoader('students-loader');
    fetch(`http://localhost:5000/students/${studentId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            loadStudents();
            alert('Студент удалён!');
        } else {
            alert('Ошибка: ' + data.error);
        }
    })
    .finally(() => hideLoader('students-loader'));
}

// Удаление фото студента
function deleteStudentPhoto(studentId) {
    if (!confirm('Вы уверены, что хотите удалить фото студента?')) {
        return;
    }
    showLoader('students-loader');
    fetch(`http://localhost:5000/delete_student_photo/${studentId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            loadStudents();
            alert('Фото удалено!');
        } else {
            alert('Ошибка: ' + data.error);
        }
    })
    .finally(() => hideLoader('students-loader'));
}

// Открытие модального окна для посещаемости
function openAttendanceModal() {
    const groupId = document.getElementById('group-filter').value;
    const subjectId = document.getElementById('subject-filter').value;
    const date = document.getElementById('date-filter').value;

    if (!groupId || !subjectId || !date) {
        alert('Выберите группу, предмет и дату в фильтре');
        return;
    }

    const [year, month, day] = date.split('-');
    const formattedDate = `${day}-${month}-${year}`;

    document.getElementById('modal-date').value = formattedDate;
    document.getElementById('modal-group').value = document.getElementById('group-filter').options[document.getElementById('group-filter').selectedIndex].text;
    document.getElementById('modal-subject').value = document.getElementById('subject-filter').options[document.getElementById('subject-filter').selectedIndex].text;

    document.getElementById('attendance-modal').style.display = 'flex';
}

// Закрытие модального окна для посещаемости
function closeAttendanceModal() {
    const modal = document.getElementById('attendance-modal');
    modal.style.opacity = '0';
    setTimeout(() => {
        modal.style.display = 'none';
        modal.style.opacity = '1';
        document.getElementById('face-results').innerHTML = '';
        document.getElementById('confirm-modal-attendance').style.display = 'none';
        document.getElementById('modal-image').value = '';
        document.getElementById('modal-date').value = '';
        document.getElementById('modal-group').value = '';
        document.getElementById('modal-subject').value = '';
        hideLoader('modal-loader');
    }, 300);
}

// Открытие модального окна для добавления студента
function openAddStudentModal() {
    loadGroupsForStudentModal();
    document.getElementById('add-student-modal').style.display = 'flex';
}

// Закрытие модального окна для добавления студента
function closeAddStudentModal() {
    const modal = document.getElementById('add-student-modal');
    modal.style.opacity = '0';
    setTimeout(() => {
        modal.style.display = 'none';
        modal.style.opacity = '1';
        document.getElementById('student-name').value = '';
        document.getElementById('student-group').value = '';
    }, 300);
}

// Открытие модального окна для загрузки фото
function openUploadPhotoModal(studentId) {
    document.getElementById('photo-student-id').value = studentId;
    document.getElementById('upload-photo-modal').style.display = 'flex';
}

// Закрытие модального окна для загрузки фото
function closeUploadPhotoModal() {
    const modal = document.getElementById('upload-photo-modal');
    modal.style.opacity = '0';
    setTimeout(() => {
        modal.style.display = 'none';
        modal.style.opacity = '1';
        document.getElementById('student-photo').value = '';
    }, 300);
}

// Унифицированная обработка закрытия модальных окон
const modals = ['add-student-modal', 'attendance-modal', 'upload-photo-modal'];
modals.forEach(modalId => {
    const modal = document.getElementById(modalId);
    modal.addEventListener('click', function(event) {
        const modalContent = modal.querySelector('.modal-content');
        if (!modalContent.contains(event.target)) {
            if (modalId === 'add-student-modal') closeAddStudentModal();
            if (modalId === 'attendance-modal') closeAttendanceModal();
            if (modalId === 'upload-photo-modal') closeUploadPhotoModal();
        }
    });
});

// Закрытие всех модальных окон по клавише Esc
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        modals.forEach(modalId => {
            const modal = document.getElementById(modalId);
            if (modal.style.display === 'flex') {
                if (modalId === 'add-student-modal') closeAddStudentModal();
                if (modalId === 'attendance-modal') closeAttendanceModal();
                if (modalId === 'upload-photo-modal') closeUploadPhotoModal();
            }
        });
    }
});

// Обработка формы добавления студента
document.getElementById('add-student-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const fullName = document.getElementById('student-name').value;
    const groupId = document.getElementById('student-group').value || null;

    showLoader('add-student-loader'); // Показываем спиннер

    fetch('http://localhost:5000/students', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, group_id: groupId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            loadStudents();
            closeAddStudentModal();
            alert('Студент добавлен!');
        } else {
            alert('Ошибка: ' + data.error);
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
    })
    .finally(() => hideLoader('add-student-loader')); // Скрываем спиннер
});

// Обработка формы загрузки фото
document.getElementById('upload-photo-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const studentId = document.getElementById('photo-student-id').value;
    const photo = document.getElementById('student-photo').files[0];

    const formData = new FormData();
    formData.append('image', photo);
    formData.append('student_id', studentId);

    showLoader('upload-photo-loader'); // Показываем спиннер

    fetch('http://localhost:5000/upload_student_photo', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            closeUploadPhotoModal();
            loadStudents();
            alert('Фото успешно загружено!');
        } else {
            alert('Ошибка: ' + data.error);
        }
    })
    .catch(error => {
        alert('Ошибка загрузки фото: ' + error.message);
    })
    .finally(() => hideLoader('upload-photo-loader')); // Скрываем спиннер
});

// Обработка формы загрузки изображения для посещаемости
let lastProcessedResults = null;

document.getElementById('attendance-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const groupId = document.getElementById('group-filter').value;
    const subjectId = document.getElementById('subject-filter').value;
    const date = document.getElementById('date-filter').value;
    const image = document.getElementById('modal-image').files[0];

    if (!groupId || !subjectId || !date || !image) {
        alert('Заполните все поля фильтра и выберите изображение');
        return;
    }

    const formData = new FormData();
    formData.append('image', image);
    formData.append('subject_id', subjectId);
    formData.append('date', date);
    formData.append('group_id', groupId);

    showLoader('modal-loader');
    fetch('http://localhost:5000/process_image', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        const resultsDiv = document.getElementById('face-results');
        resultsDiv.innerHTML = '';
        if (data.error) {
            resultsDiv.innerHTML = `<p>Ошибка: ${data.error}</p>`;
        } else {
            lastProcessedResults = data.results;
            data.results.forEach(result => {
                const div = document.createElement('div');
                div.className = 'face-result';
                let statusText = '';
                if (result.status === 'present') {
                    statusText = 'Присутствовал';
                } else if (result.status === 'unknown') {
                    statusText = 'Неизвестный';
                } else if (result.status === 'other_group') {
                    statusText = 'Другая группа';
                }
                div.innerHTML = `
                <img src="${result.face_image_path.replace('/opt/lampp/htdocs/', '/')}" class="face-image">
                <p>${result.matches.length > 0 ? result.matches[0].full_name : 'Неизвестный'}</p>
                <p>Статус: ${statusText}</p>
                `;
                resultsDiv.appendChild(div);
            });
            document.getElementById('confirm-modal-attendance').style.display = 'block';
        }
    })
    .catch(error => {
        alert('Ошибка обработки изображения: ' + error.message);
    })
    .finally(() => hideLoader('modal-loader'));
});

// Подтверждение посещаемости из модального окна
document.getElementById('confirm-modal-attendance').addEventListener('click', function() {
    const groupId = document.getElementById('group-filter').value;
    const subjectId = document.getElementById('subject-filter').value;
    const date = document.getElementById('date-filter').value;

    if (!lastProcessedResults) {
        alert('Нет данных для подтверждения');
        return;
    }

    showLoader('modal-loader');
    const promises = lastProcessedResults
    .filter(result => result.status === 'present' && result.matches.length > 0)
    .map(result => {
        return fetch('http://localhost:5000/mark_attendance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: result.matches[0].student_id,
                subject_id: subjectId,
                attendance_date: date,
                group_id: groupId,
                status: 'present'
            })
        }).then(response => response.json());
    });

    Promise.all(promises)
    .then(results => {
        const errors = results.filter(r => r.status !== 'success').map(r => r.error);
        if (errors.length > 0) {
            alert('Ошибки при отметке: ' + errors.join(', '));
        } else {
            alert('Посещаемость успешно отмечена');
            closeAttendanceModal();
            loadAttendance();
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
    })
    .finally(() => hideLoader('modal-loader'));
});

// Инициализация: открываем сохранённую вкладку или по умолчанию 'attendance'
const savedSection = localStorage.getItem('activeSection') || 'attendance';
showSection(savedSection);
