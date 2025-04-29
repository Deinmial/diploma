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
        console.log('Showing students section');
        loadStudentsFilters();
        loadStudents();
    } else if (section === 'logs') {
        console.log('Showing logs section');
        loadLogs();
    }
    localStorage.setItem('activeSection', section);
}

// Загрузка фильтров для посещаемости
function loadFilters() {
    fetch('http://localhost:5000/groups')
    .then(response => {
        if (!response.ok) throw new Error('Failed to load groups');
        return response.json();
    })
    .then(data => {
        console.log('Groups for filters:', data);
        const groupSelect = document.getElementById('group-filter');
        groupSelect.innerHTML = '<option value="">Все группы</option>';
        data.groups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.group_id;
            option.textContent = group.group_name;
            groupSelect.appendChild(option);
        });
    })
    .catch(error => console.error('Error loading groups for filters:', error));

    fetch('http://localhost:5000/subjects')
    .then(response => {
        if (!response.ok) throw new Error('Failed to load subjects');
        return response.json();
    })
    .then(data => {
        console.log('Subjects:', data);
        const subjectSelect = document.getElementById('subject-filter');
        const modalSubjectSelect = document.getElementById('modal-subject');
        subjectSelect.innerHTML = '<option value="">Все предметы</option>';
        modalSubjectSelect.innerHTML = '';
        data.subjects.forEach(subject => {
            const option = document.createElement('option');
            option.value = subject.subject_id;
            option.textContent = subject.subject_name;
            subjectSelect.appendChild(option);
            modalSubjectSelect.appendChild(option.cloneNode(true));
        });
    })
    .catch(error => console.error('Error loading subjects:', error));
}

// Загрузка фильтров для студентов
function loadStudentsFilters() {
    fetch('http://localhost:5000/groups')
    .then(response => {
        if (!response.ok) throw new Error('Failed to load groups');
        return response.json();
    })
    .then(data => {
        console.log('Groups for student filters:', data);
        const groupSelect = document.getElementById('student-group-filter');
        groupSelect.innerHTML = '<option value="">Все группы</option>';
        data.groups.forEach(group => {
            const option = document.createElement('option');
            option.value = group.group_id;
            option.textContent = group.group_name;
            groupSelect.appendChild(option);
        });
    })
    .catch(error => console.error('Error loading groups for student filters:', error));
}

// Загрузка групп для модального окна добавления студента
function loadGroupsForStudentModal() {
    console.log('Loading groups for student modal...');
    fetch('http://localhost:5000/groups')
    .then(response => {
        console.log('Groups response status:', response.status);
        if (!response.ok) throw new Error('Failed to load groups');
        return response.json();
    })
    .then(data => {
        console.log('Groups data:', data);
        const groupSelect = document.getElementById('student-group');
        if (!groupSelect) {
            console.error('Element #student-group not found');
            return;
        }
        groupSelect.innerHTML = '<option value="">Без группы</option>';
        if (data.groups && Array.isArray(data.groups)) {
            data.groups.forEach(group => {
                const option = document.createElement('option');
                option.value = group.group_id;
                option.textContent = group.group_name;
                groupSelect.appendChild(option);
            });
        } else {
            console.warn('No groups found in response');
        }
    })
    .catch(error => console.error('Error loading groups for student modal:', error));
}

// Загрузка таблицы посещаемости
function loadAttendance() {
    const groupId = document.getElementById('group-filter').value;
    const subjectId = document.getElementById('subject-filter').value;
    const date = document.getElementById('date-filter').value;

    let url = 'http://localhost:5000/attendance';
    const params = new URLSearchParams();
    if (groupId) params.append('group_id', groupId);
    if (subjectId) params.append('subject_id', subjectId);
    if (date) params.append('date', date);
    if (params.toString()) url += `?${params.toString()}`;

    fetch(url)
    .then(response => response.json())
    .then(data => {
        const tbody = document.getElementById('attendance-table-body');
        tbody.innerHTML = '';
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
            onclick="updateStatus(${record.attendance_id}, 'present')">
            Присутствует
            </button>
            <button class="status-switch-btn status-absent ${record.status === 'absent' ? 'active' : ''}"
            onclick="updateStatus(${record.attendance_id}, 'absent')">
            Отсутствует
            </button>
            </div>
            </td>
            `;
            tbody.appendChild(tr);
        });
    });
}

// Загрузка таблицы студентов
function loadStudents() {
    const groupId = document.getElementById('student-group-filter').value;
    let url = 'http://localhost:5000/students';
    if (groupId) url += `?group_id=${groupId}`;

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
    });
}

// Загрузка логов
function loadLogs() {
    console.log('Starting loadLogs');
    fetch('http://localhost:5000/logs')
    .then(response => {
        if (!response.ok) throw new Error('Failed to load logs');
        return response.json();
    })
    .then(data => {
        console.log('Logs received:', data);
        const tbody = document.getElementById('logs-table-body');
        tbody.innerHTML = '';
        if (data.error) {
            tbody.innerHTML = `<tr><td colspan="4">${data.error}</td></tr>`;
            return;
        }

        // Парсинг логов
        const parsedLogs = data.logs.map(log => {
            const parts = log.match(/^(\S+ \S+,\d{3}) - (\w+) - (.+)$/);
            if (!parts) {
                console.warn('Failed to parse log:', log);
                return {
                    timestamp: '',
                    level: 'UNKNOWN',
                    message: log,
                    raw: log
                };
            }
            return {
                timestamp: parts[1].replace(',', '.'), // Заменяем запятую на точку для Date
                                         level: parts[2],
                                         message: parts[3],
                                         raw: log
            };
        });

        // Сортировка: по времени (убывание), затем по уровню (ERROR > WARNING > INFO)
        parsedLogs.sort((a, b) => {
            const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
            const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
            if (timeA !== timeB) {
                return timeB - timeA; // Новые записи сверху
            }
            const levelPriority = { 'ERROR': 3, 'WARNING': 2, 'INFO': 1, 'UNKNOWN': 0 };
            return (levelPriority[b.level] || 0) - (levelPriority[a.level] || 0);
        });

        console.log('Sorted logs:', parsedLogs);

        // Отображение отсортированных логов
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
    .catch(error => console.error('Error loading logs:', error));
}

// Применение фильтров посещаемости
function applyFilters() {
    loadAttendance();
}

// Применение фильтров студентов
function applyStudentFilters() {
    loadStudents();
}

// Обновление статуса посещаемости
function updateStatus(attendanceId, status) {
    fetch(`http://localhost:5000/attendance/${attendanceId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            loadAttendance();
        } else {
            alert('Ошибка: ' + data.error);
        }
    });
}

// Удаление студента
function deleteStudent(studentId, fullName) {
    if (!confirm(`Вы уверены, что хотите удалить студента ${fullName}? Это действие нельзя отменить.`)) {
        return;
    }
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
    });
}

// Удаление фото студента
function deleteStudentPhoto(studentId) {
    if (!confirm('Вы уверены, что хотите удалить фото студента?')) {
        return;
    }
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
    });
}

// Открытие модального окна для посещаемости
function openAttendanceModal() {
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
    });
});

// Обработка формы загрузки фото
document.getElementById('upload-photo-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const studentId = document.getElementById('photo-student-id').value;
    const photo = document.getElementById('student-photo').files[0];

    const formData = new FormData();
    formData.append('image', photo);
    formData.append('student_id', studentId);

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
    });
});

// Обработка формы загрузки изображения для посещаемости
document.getElementById('attendance-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const subjectId = document.getElementById('modal-subject').value;
    const date = document.getElementById('modal-date').value;
    const image = document.getElementById('modal-image').files[0];

    const formData = new FormData();
    formData.append('image', image);
    formData.append('subject_id', subjectId);
    formData.append('date', date);

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
            data.results.forEach(result => {
                if (result.face_image_path) {
                    const img = document.createElement('img');
                    img.src = result.face_image_path.replace('/opt/lampp/htdocs/faces/', '/faces/');
                    img.className = 'face-image';
                    resultsDiv.appendChild(img);
                }
                if (result.matches.length > 0) {
                    const matches = result.matches.map(m => m.full_name).join(', ');
                    resultsDiv.innerHTML += `<p>Распознаны: ${matches}</p>`;
                } else {
                    resultsDiv.innerHTML += `<p>Совпадений не найдено</p>`;
                }
            });
            loadAttendance();
        }
    });
});

// Переключатели статуса
document.querySelectorAll('.status-switch').forEach(switchContainer => {
    const buttons = switchContainer.querySelectorAll('.status-switch-btn');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            buttons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
        });
    });
});

// Инициализация: открываем сохранённую вкладку или по умолчанию 'attendance'
const savedSection = localStorage.getItem('activeSection') || 'attendance';
showSection(savedSection);
