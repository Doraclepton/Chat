import sys
import paho.mqtt.client as mqtt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QLabel)
from PyQt6.QtCore import pyqtSignal, QObject

# Настройки
BROKER = "broker.emqx.io"
PORT = 1883
TOPIC = "python/global_chat_secure_2026_v2"  # Уникальный топик


class Signals(QObject):
    msg_received = pyqtSignal(str)
    kick_signal = pyqtSignal()


class ChatApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat")
        self.resize(500, 600)
        self.user_name = ""
        self.online_users = set()

        # --- UI ---
        main_layout = QVBoxLayout()
        self.auth_layout = QHBoxLayout()
        self.name_input = QLineEdit(placeholderText="Ваше имя...")
        self.login_btn = QPushButton("Войти")
        self.auth_layout.addWidget(self.name_input)
        self.auth_layout.addWidget(self.login_btn)

        self.log = QTextEdit(readOnly=True)
        self.msg_input = QLineEdit(placeholderText="Сообщение", enabled=False)
        self.send_btn = QPushButton("Отправить", enabled=False)

        msg_bar = QHBoxLayout()
        msg_bar.addWidget(self.msg_input)
        msg_bar.addWidget(self.send_btn)

        main_layout.addLayout(self.auth_layout)
        main_layout.addWidget(self.log)
        main_layout.addLayout(msg_bar)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # --- Signals & MQTT ---
        self.signals = Signals()
        # Теперь метод точно существует и виден
        self.signals.msg_received.connect(self.display_message)
        self.signals.kick_signal.connect(self.close)

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_message = self.on_mqtt_message

        self.login_btn.clicked.connect(self.login)
        self.send_btn.clicked.connect(self.process_output)
        self.msg_input.returnPressed.connect(self.process_output)

    def login(self):
        name = self.name_input.text().strip()
        if name:
            self.user_name = name
            self.name_input.setEnabled(False)
            self.login_btn.setEnabled(False)
            self.msg_input.setEnabled(True)
            self.send_btn.setEnabled(True)

            try:
                self.client.connect(BROKER, PORT, 60)
                self.client.subscribe(TOPIC)
                self.client.loop_start()
                self.client.publish(TOPIC, f"__JOIN__:{self.user_name}")
            except Exception as e:
                self.log.append(f"Ошибка связи: {e}")

    def on_mqtt_message(self, client, userdata, message):
        raw_data = message.payload.decode()

        if raw_data.startswith("__JOIN__:"):
            name = raw_data.split(":")[1]
            self.online_users.add(name)
            self.signals.msg_received.emit(f"<i>📢 {name} вошел в чат</i>")
            if name != self.user_name:
                self.client.publish(TOPIC, f"__ALIVE__:{self.user_name}")

        elif raw_data.startswith("__ALIVE__:"):
            name = raw_data.split(":")[1]
            self.online_users.add(name)

        elif raw_data.startswith("__EXIT__:"):
            name = raw_data.split(":")[1]
            if name in self.online_users: self.online_users.remove(name)
            self.signals.msg_received.emit(f"<i>❌ {name} покинул чат</i>")

        elif raw_data.startswith("__KICK__:"):
            parts = raw_data.split(":")
            target = parts[1]
            admin = parts[2]
            if target == self.user_name:
                self.signals.kick_signal.emit()
            self.signals.msg_received.emit(f"<b style='color:red;'>⚡ {target} был выгнан пользователем {admin}</b>")

        else:
            self.signals.msg_received.emit(raw_data)

    def process_output(self):
        text = self.msg_input.text().strip()
        if not text: return

        if text.lower() == "list players":
            users = ", ".join(self.online_users) if self.online_users else self.user_name
            self.log.append(f"<br><b>[SYSTEM]: В сети: {users}</b>")

        elif text.lower().startswith("kick "):
            try:
                target = text.split(" ", 1)[1]
                self.client.publish(TOPIC, f"__KICK__:{target}:{self.user_name}")
            except IndexError:
                self.log.append("<i>Ошибка: укажите имя после kick</i>")

        else:
            full_msg = f"<b>{self.user_name}</b>: {text}"
            self.client.publish(TOPIC, full_msg)

        self.msg_input.clear()

    # Тот самый метод, который вызывал ошибку
    def display_message(self, text):
        self.log.append(text)

    def closeEvent(self, event):
        if self.user_name:
            self.client.publish(TOPIC, f"__EXIT__:{self.user_name}")
            self.client.loop_stop()
            self.client.disconnect()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatApp()
    window.show()
    sys.exit(app.exec())
