from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QMainWindow, QDialog, QMessageBox
)
from PySide6.QtCore import Qt
import psycopg2
import sys
import configparser
import sqlite3

config = configparser.ConfigParser()
config.read('config.ini')

DATABASE_TYPE = config.get('Database', 'type')
# Параметры для пагинации
ITEMS_PER_PAGE = 10

SQLITE_CREATE_SCRIPT = """
-- Таблица справочника факультетов
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL
);

-- Таблица справочника типов курсов
CREATE TABLE IF NOT EXISTS course_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_name TEXT NOT NULL,
    description TEXT
);

-- Основная таблица курсов
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    department_id INTEGER,
    course_type_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    FOREIGN KEY (course_type_id) REFERENCES course_types(id) ON DELETE RESTRICT
);
"""

POSTGRESQL_CREATE_SCRIPT = """
-- Таблица справочника факультетов
CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code VARCHAR(5) NOT NULL
);

-- Таблица справочника типов курсов
CREATE TABLE IF NOT EXISTS course_types (
    id SERIAL PRIMARY KEY,
    type_name TEXT NOT NULL,
    description TEXT
);

-- Основная таблица курсов
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    department_id INT REFERENCES departments(id),
    course_type_id INT REFERENCES course_types(id)
);
"""

INSERT_SCRIPT = """
INSERT INTO departments 
(name, code) 
VALUES
('Математика', 'MATH'),
('Информатика', 'CS'),
('Физика', 'PHYS'),
('Биология', 'BIO'),
('Инженерия', 'ENG');

INSERT INTO course_types 
(type_name, description) 
VALUES
('Онлайн', 'Курсы, проводимые онлайн'),
('Оффлайн', 'Курсы, проводимые на кампусе'),
('Смешанный', 'Курсы, сочетающие онлайн и оффлайн форматы'),
('Практикум', 'Практическое обучение и тренировки'),
('Семинар', 'Малые групповые обсуждения или лекции');
"""

# Функция для подключения к базе данных
def get_db_connection():
    if DATABASE_TYPE =='sqlite':
        conn = sqlite3.connect(config.get('Database', 'filename'))
        # В sqlite необходимо включать явно поддержку внешних ключей
        conn.execute("PRAGMA foreign_keys = 1")
    elif DATABASE_TYPE == 'postgresql':
        conn = psycopg2.connect(
            dbname=config.get('Database', 'database'),
            user=config.get('Database', 'user'),
            password=config.get('Database', 'password'),
            host=config.get('Database', 'host'),
            port=config.get('Database', 'port')
        )
    else:
        raise ValueError("Unsupported database type")
    return conn

def get_param_placeholder():
    if DATABASE_TYPE =='sqlite':
        return "?"
    elif DATABASE_TYPE == 'postgresql':
        return "%s"
    else:
        raise ValueError("Unsupported database type")

# Функция для получения списка курсов с фильтрацией
def fetch_courses(filter_type=None, filter_department=None, search_query=None, offset=0, limit=ITEMS_PER_PAGE):
    query = """
        SELECT courses.id, courses.name, departments.code, course_types.type_name
        FROM courses
        JOIN departments ON departments.id = courses.department_id
        JOIN course_types ON course_types.id = courses.course_type_id
    """
    conditions = []
    params = []

    p = get_param_placeholder()

    if filter_type and filter_type != "All":
        conditions.append(f"courses.course_type_id = {p}")
        params.append(filter_type)

    if filter_department and filter_department != "All":
        conditions.append(f"courses.department_id = {p}")
        params.append(filter_department)

    if search_query:
        conditions.append(f"courses.name ILIKE {p}")
        params.append(f"%{search_query}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += f" ORDER BY courses.id LIMIT {p} OFFSET {p}"
    params.extend([limit, offset])

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, tuple(params))
    return cur.fetchall()

def count_courses(filter_type=None, filter_department=None, search_query=None):
    query = """
        SELECT COUNT(*)
        FROM courses
        JOIN departments ON departments.id = courses.department_id
        JOIN course_types ON course_types.id = courses.course_type_id
    """
    conditions = []
    params = []

    p = get_param_placeholder()

    if filter_type and filter_type != "All":
        conditions.append(f"courses.course_type_id = {p}")
        params.append(filter_type)

    if filter_department and filter_department != "All":
        conditions.append(f"courses.department_id = {p}")
        params.append(filter_department)

    if search_query:
        conditions.append(f"courses.name ILIKE {p}")
        params.append(f"%{search_query}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, tuple(params))
    return cur.fetchone()[0]

def fetch_course_by_id(course_id):
    p = get_param_placeholder()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT courses.name, courses.description, departments.name AS department, course_types.type_name
        FROM courses
        JOIN departments ON courses.department_id = departments.id
        JOIN course_types ON courses.course_type_id = course_types.id
        WHERE courses.id = {p}
    """, (course_id,))
    return cur.fetchone()

def delete_course(course_id):
    p = get_param_placeholder()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM courses WHERE id = {p}", (course_id,))
    conn.commit()

def create_course(name, description, department_id, course_type_id):
    conn = get_db_connection()
    cur = conn.cursor()
    p = get_param_placeholder()
    cur.execute(f"""
                INSERT INTO courses (name, description, department_id, course_type_id)
                VALUES ({p}, {p}, {p}, {p})
            """, (name, description, department_id, course_type_id))
    conn.commit()

def update_course(course_id, name, description, department_id, course_type_id):
    conn = get_db_connection()
    cur = conn.cursor()
    p = get_param_placeholder()
    cur.execute(f"""
                UPDATE courses
                SET name = {p}, description = {p}, department_id = {p}, course_type_id = {p}
                WHERE id = {p}
            """, (name, description, department_id, course_type_id, course_id))
    conn.commit()

# Функция для получения списка типов курсов
def fetch_course_types():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, type_name FROM course_types")
    return cur.fetchall()


# Функция для получения списка департаментов
def fetch_departments():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM departments")
    return cur.fetchall()

class AddEditCourseDialog(QDialog):
    def __init__(self, parent=None, course_id=None):
        super().__init__(parent)
        self.course_id = course_id
        self.setWindowTitle("Добавить/Изменить курс")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout()

        self.name_label = QLabel("Название курса:")
        self.name_entry = QLineEdit()
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_entry)

        self.description_label = QLabel("Описание курса:")
        self.description_entry = QLineEdit()
        layout.addWidget(self.description_label)
        layout.addWidget(self.description_entry)

        self.department_label = QLabel("Факультет:")
        self.department_combobox = QComboBox()
        for d in fetch_departments():
            self.department_combobox.addItem(d[1], d[0])
        layout.addWidget(self.department_label)
        layout.addWidget(self.department_combobox)

        self.course_type_label = QLabel("Тип курса:")
        self.course_type_combobox = QComboBox()
        for c in fetch_course_types():
            self.course_type_combobox.addItem(c[1], c[0])
        layout.addWidget(self.course_type_label)
        layout.addWidget(self.course_type_combobox)

        self.save_button = QPushButton("Сохранить")
        self.save_button.clicked.connect(self.save_course)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

        # Если передан course_id, загружаем данные курса
        if self.course_id:
            self.load_course()

    def load_course(self):
        # Загружаем данные курса по ID
        course_data = fetch_course_by_id(self.course_id)
        if course_data:
            self.name_entry.setText(course_data[0])  # Название курса
            self.description_entry.setText(course_data[1])  # Описание курса
            self.department_combobox.setCurrentText(course_data[2])  # Департамент
            self.course_type_combobox.setCurrentText(course_data[3])  # Тип курса

    def save_course(self):
        name = self.name_entry.text()
        description = self.description_entry.text()
        department_id = self.department_combobox.currentData(Qt.UserRole)
        course_type_id = self.course_type_combobox.currentData(Qt.UserRole)
        if self.course_id:
            # Обновляем курс
            update_course(self.course_id, name, description, department_id, course_type_id)
        else:
            # Добавляем новый курс
            create_course(name, description, department_id, course_type_id)
        self.accept()

class CourseDetailsDialog(QDialog):
    def __init__(self, parent=None, course_id=None):
        super().__init__(parent)
        self.course_id = course_id
        self.setWindowTitle("Карточка курса")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout()

        self.name_label = QLabel("Название курса:")
        self.name_value = QLabel()
        layout.addWidget(self.name_label)
        layout.addWidget(self.name_value)

        self.description_label = QLabel("Описание курса:")
        self.description_value = QLabel()
        layout.addWidget(self.description_label)
        layout.addWidget(self.description_value)

        self.department_label = QLabel("Факультет:")
        self.department_value = QLabel()
        layout.addWidget(self.department_label)
        layout.addWidget(self.department_value)

        self.course_type_label = QLabel("Тип курса:")
        self.course_type_value = QLabel()
        layout.addWidget(self.course_type_label)
        layout.addWidget(self.course_type_value)

        self.setLayout(layout)

        if self.course_id:
            self.load_course_details()

    def load_course_details(self):
        # Получаем данные о курсе по его ID
        course_data = fetch_course_by_id(self.course_id)
        if course_data:
            self.name_value.setText(course_data[0])  # Название курса
            self.description_value.setText(course_data[1])  # Описание курса
            self.department_value.setText(course_data[2])  # Департамент
            self.course_type_value.setText(course_data[3])  # Тип курса


class CourseManager(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Course Manager")
        self.setGeometry(100, 100, 800, 600)

        self.current_page = 1  # Номер текущей страницы

        main_layout = QVBoxLayout()

        # Поля для фильтрации
        filter_layout = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Поиск по названию курса")
        filter_layout.addWidget(self.search_entry)

        self.course_type_combobox = QComboBox()
        self.course_type_combobox.addItem("All")
        for c in fetch_course_types():
            self.course_type_combobox.addItem(c[1], c[0])
        filter_layout.addWidget(self.course_type_combobox)

        self.department_combobox = QComboBox()
        self.department_combobox.addItem("All")
        for d in fetch_departments():
            self.department_combobox.addItem(d[1], d[0])
        filter_layout.addWidget(self.department_combobox)

        self.update_button = QPushButton("Обновить список")
        self.update_button.clicked.connect(self.update_course_list)
        filter_layout.addWidget(self.update_button)

        main_layout.addLayout(filter_layout)

        # Таблица курсов
        self.course_table = QTableWidget(0, 3)
        self.course_table.setHorizontalHeaderLabels(["Название курса", "Департамент", "Тип курса"])
        self.course_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.course_table)

        # Кнопки пагинации
        pagination_layout = QHBoxLayout()
        self.prev_button = QPushButton("Предыдущая страница")
        self.prev_button.clicked.connect(self.prev_page)
        self.prev_button.setEnabled(False)  # Изначально отключена

        self.page_label = QLabel(f"Страница {self.current_page}")

        self.next_button = QPushButton("Следующая страница")
        self.next_button.clicked.connect(self.next_page)

        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_button)
        main_layout.addLayout(pagination_layout)

        # Кнопки управления
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Добавить курс")
        self.add_button.clicked.connect(self.add_course)
        button_layout.addWidget(self.add_button)

        self.edit_button = QPushButton("Изменить курс")
        self.edit_button.clicked.connect(self.edit_course)
        button_layout.addWidget(self.edit_button)

        self.show_button = QPushButton("Показать карточку курса")
        self.show_button.clicked.connect(self.show_course_details)
        button_layout.addWidget(self.show_button)

        self.delete_button = QPushButton("Удалить курс")
        self.delete_button.clicked.connect(self.delete_course)
        button_layout.addWidget(self.delete_button)

        main_layout.addLayout(button_layout)

        # Создаем центральный виджет и назначаем ему макет
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Обновляем таблицу курсов при загрузке
        self.update_course_list()

    def add_course(self):
        dialog = AddEditCourseDialog(self)
        if dialog.exec():
            self.update_course_list()

    def edit_course(self):
        selected_row = self.course_table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Warning", "Выберите курс для редактирования.")
            return

        # Получаем скрытый ID из выбранной строки
        course_id = self.course_table.item(selected_row, 0).data(Qt.UserRole)

        # Открываем диалог редактирования курса
        dialog = AddEditCourseDialog(self, course_id=course_id)
        if dialog.exec():
            self.update_course_list()

    def show_course_details(self):
        selected_row = self.course_table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Warning", "Выберите курс для просмотра.")
            return

        # Получаем скрытый ID из выбранной строки
        course_id = self.course_table.item(selected_row, 0).data(Qt.UserRole)

        # Открываем диалог с полной информацией о курсе
        dialog = CourseDetailsDialog(self, course_id=course_id)
        dialog.exec()

    def delete_course(self):
        selected_row = self.course_table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Warning", "Выберите курс для удаления.")
            return

        # Получаем скрытый ID из выбранной строки
        course_id = self.course_table.item(selected_row, 0).data(Qt.UserRole)

        # Подтверждение удаления
        confirm = QMessageBox.question(self, "Подтверждение удаления", "Вы уверены, что хотите удалить этот курс?",
                                       QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            # Удаляем курс из базы данных
            delete_course(course_id)
            self.update_course_list()


    def update_course_list(self):
        self.course_table.setRowCount(0)

        filter_type = self.course_type_combobox.currentData(Qt.UserRole)
        filter_department = self.department_combobox.currentData(Qt.UserRole)
        search_query = self.search_entry.text()

        total_courses = count_courses(filter_type, filter_department, search_query)
        total_pages = (total_courses + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE  # Всего страниц

        # Получаем курсы для текущей страницы
        offset = (self.current_page - 1) * ITEMS_PER_PAGE
        courses = fetch_courses(filter_type, filter_department, search_query, offset)

        for row, course in enumerate(courses):
            self.course_table.insertRow(row)

            # Скрытое хранение course_id
            item_name = QTableWidgetItem(course[1])
            item_name.setData(Qt.UserRole, course[0])
            item_name.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)  # Отключаем редактирование
            self.course_table.setItem(row, 0, item_name)

            # Департамент
            item_department = QTableWidgetItem(course[2])
            item_department.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)  # Отключаем редактирование
            self.course_table.setItem(row, 1, item_department)

            # Тип курса
            item_course_type = QTableWidgetItem(course[3])
            item_course_type.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)  # Отключаем редактирование
            self.course_table.setItem(row, 2, item_course_type)

        # Обновляем информацию о страницах и кнопках
        self.page_label.setText(f"Страница {self.current_page} из {total_pages}")
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < total_pages)

    def next_page(self):
        self.current_page += 1
        self.update_course_list()

    def prev_page(self):
        self.current_page -= 1
        self.update_course_list()

if __name__ == "__main__":
    connection = get_db_connection()
    if config.get('App', 'init') != 'true':
        cursor = connection.cursor()
        if DATABASE_TYPE == "postgrsql":
            cursor.executescript(POSTGRESQL_CREATE_SCRIPT)
        elif DATABASE_TYPE == "sqlite":
            cursor.executescript(SQLITE_CREATE_SCRIPT)
        cursor.executescript(INSERT_SCRIPT)
        connection.commit()
        config.set('App', 'init', 'true')
        with open('config.ini', 'w') as config_file:
            config.write(config_file)
    app = QApplication(sys.argv)
    window = CourseManager()
    window.show()
    sys.exit(app.exec())
