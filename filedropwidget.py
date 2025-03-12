import whisper
import queue
import threading
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QPushButton,
    QComboBox, QFileDialog, QListWidget, QListWidgetItem,
    QHBoxLayout,
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt, QTranslator
from typing import Union
import sys
from pathlib import Path
import re


def get_asset_path(relative_path: Union[Path, str]):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bundle_dir = Path(sys._MEIPASS)
    else:
        bundle_dir = Path(__file__).parent

    return bundle_dir / relative_path


class VideoDropWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.queue = queue.Queue()
        self.processing = False
        self.model = None

        self.lang_label = QLabel("🌐")
        self.lang_selector = QComboBox()
        self.lang_selector.addItems(["한국어", "English", "中文", "日本語"])
        self.lang_selector.setFixedSize(120, 30)
        self.lang_selector.currentIndexChanged.connect(self.change_language)

        lang_menu_layout = QHBoxLayout()
        lang_menu_layout.addWidget(self.lang_label)
        lang_menu_layout.addWidget(self.lang_selector)
        lang_menu_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.translator = QTranslator()
        self.label = QLabel(self.tr("Whisper 모델 로드 중... ⏳"), self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.list_widget = QListWidget(self)

        self.set_path_button = QPushButton(self.tr("저장할 폴더 선택"), self)
        self.set_path_button.clicked.connect(self.select_save_folder)

        self.save_path_label = QLabel(self.tr("저장 경로: (미설정)"), self)
        self.save_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.addLayout(lang_menu_layout)
        layout.addStretch(1)
        layout.addWidget(self.label)
        layout.addWidget(self.set_path_button)
        layout.addWidget(self.save_path_label)
        layout.addWidget(self.list_widget)

        self.setLayout(layout)
        self.setWindowTitle("Voice2Text")
        self.resize(500, 350)

        self.default_save_path = None
        self.transcriptions = {}

        threading.Thread(target=self.load_whisper_model, daemon=True).start()

    def change_language(self, index: int):
        lang_map = {
            0: 'ko',
            1: 'en',
            2: 'zh',
            3: 'ja'
        }

        lang_code = lang_map.get(index, 'en')
        self.apply_translation(lang_code)

    def apply_translation(self, lang_code):
        lang_path = get_asset_path(f"locales/translations_{lang_code}.qm")
        self.translator.load(str(lang_path))
        QApplication.instance().installTranslator(self.translator)
        self.label.setText('')
        self.set_path_button.setText(self.tr("저장할 폴더 선택"))
        self.save_path_label.setText(self.tr("저장 경로: (미설정)"))

    def load_whisper_model(self):
        self.model = whisper.load_model("turbo")
        self.label.setText(self.tr("Whisper 모델 로드 완료! 파일을 드래그하세요. 🎬"))

    def select_save_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.tr("추출한 텍스트를 저장할 폴더 선택"))
        if folder:
            self.default_save_path = folder
            self.save_path_label.setText(self.tr('저장 경로') + f": {folder}")
            self.label.setText(self.tr("Whisper 모델 로드 완료! 파일을 드래그하세요. 🎬"))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if self.default_save_path is None:
            self.label.setText(self.tr("⚠ 저장할 폴더를 먼저 선택하세요!"))
            return

        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if file_path.endswith((".mp4", ".avi", ".mkv", '.mp3', '.wav', '.ogg')):
                item = QListWidgetItem(self.tr('대기 중') + f": {file_path}")
                self.list_widget.addItem(item)
                self.queue.put((file_path, item))

        if not self.processing:
            self.process_next()

    def process_next(self):
        if not self.queue.empty():
            self.processing = True
            file_path, item = self.queue.get()
            item.setText(self.tr('변환 중') + f": {file_path} ⏳")

            thread = threading.Thread(target=self.process_video, args=(file_path, item))
            thread.start()
        else:
            self.processing = False

    def process_video(self, file_path, item):
        if not self.default_save_path:
            self.label.setText(self.tr("⚠ 저장할 폴더를 먼저 선택하세요!"))
            self.processing = False
            return

        print(f"Transport to Whisper: {file_path}")
        text = re.sub(r'([.!?。！？])', r'\1\n', self.whisper_transcribe(file_path))
        item.setText(self.tr("완료") + f": {file_path} ✅")

        self.save_transcription(file_path, text)
        self.process_next()

    def whisper_transcribe(self, file_path):
        if self.model is None:
            self.label.setText(self.tr("모델 로딩 중... 잠시만 기다려 주세요."))
            while self.model is None:
                pass

        result = self.model.transcribe(file_path)
        return result["text"]

    def save_transcription(self, file_path, text):
        file_name = file_path.split("/")[-1].rsplit(".", 1)[0]
        save_path = f"{self.default_save_path}/{file_name}.txt"

        try:
            with open(save_path, "w", encoding="utf-8") as file:
                file.write(text)
            print(f"Saved: {save_path}")
        except Exception as e:
            print(f"Save failed: {e}")
            self.label.setText(self.tr('⚠ 저장 오류 발생') + f": {e}")
